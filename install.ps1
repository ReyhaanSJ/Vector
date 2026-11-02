<#
  VECTOR installer for Windows 10 / 11.

  Easiest:  double-click "Install VECTOR.bat" in the VECTOR folder.
  Or paste this into PowerShell (works once the GitHub repo is public):
      irm https://raw.githubusercontent.com/ReyhaanSJ/Vector/HEAD/install.ps1 | iex

  It does everything: sets up its own private copy of Python (yours is untouched),
  installs VECTOR, sets up the free local AI (Ollama) or Claude, adds a `vector`
  command plus Desktop and Start Menu shortcuts. Run it again any time to update.

  Unattended options (environment variables), mainly for testing:
    VECTOR_INSTALL_YES=1          accept every default without asking
    VECTOR_INSTALL_AI=ollama|claude|none
    VECTOR_INSTALL_SKIP_MODEL=1   don't download the Ollama model
    VECTOR_INSTALL_VERSION=0.2.0  install that version (default: the newest release)
    VECTOR_INSTALL_KEEP_SETTINGS=1  updating: keep the AI choice and login setting
    VECTOR_INSTALL_LAUNCH=1       open VECTOR when done
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # makes downloads much faster in Windows PowerShell

$Repo    = "ReyhaanSJ/Vector"
$AppDir  = Join-Path $env:LOCALAPPDATA "Programs\VECTOR"
$AppSrc  = Join-Path $AppDir "src"
$Venv    = Join-Path $AppDir ".venv"
$Py      = Join-Path $Venv "Scripts\python.exe"
$Exe     = Join-Path $Venv "Scripts\vector.exe"
$AppExe  = Join-Path $Venv "Scripts\vector-app.exe"
$Auto    = $env:VECTOR_INSTALL_YES -eq "1"
$AiChoice = if ($env:VECTOR_INSTALL_AI) { $env:VECTOR_INSTALL_AI.ToLower() } else { "ask" }

function Say([string]$Text, [string]$Color = "Gray") { Write-Host $Text -ForegroundColor $Color }
function Step([int]$N, [string]$Text) { Write-Host ""; Write-Host "[$N/5] $Text" -ForegroundColor Cyan }
function Fail([string]$Text) {
    Write-Host ""
    Write-Host "Setup stopped: $Text" -ForegroundColor Red
    Write-Host "Take a photo of this window and open an issue on the VECTOR GitHub page." -ForegroundColor Red
    exit 1
}
function AskYes([string]$Question, [bool]$Default = $true) {
    if ($Auto) { return $Default }
    $hint = if ($Default) { "[Enter = yes, n = no]" } else { "[y = yes, Enter = no]" }
    $answer = (Read-Host "$Question $hint").Trim().ToLower()
    if (-not $answer) { return $Default }
    return $answer -in @("y", "yes")
}

Write-Host ""
Write-Host "  V E C T O R   setup" -ForegroundColor Cyan
Write-Host "  your laptop, on command" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 1. files
Step 1 "Getting VECTOR"
$Source = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml"))) {
    $Source = $PSScriptRoot
} else {
    if ($env:VECTOR_INSTALL_VERSION) {
        $tag = "v" + $env:VECTOR_INSTALL_VERSION.TrimStart("vV")
        $RepoZip = "https://github.com/$Repo/archive/refs/tags/$tag.zip"
        Say "Downloading VECTOR $tag..."
    } else {
        $RepoZip = "https://github.com/$Repo/archive/HEAD.zip"
        try {
            $latest = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -UseBasicParsing
            $RepoZip = "https://github.com/$Repo/archive/refs/tags/$($latest.tag_name).zip"
            Say "Downloading VECTOR $($latest.tag_name)..."
        } catch { Say "Downloading the latest version..." }
    }
    $tmp = Join-Path $env:TEMP ("vector-setup-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $zip = Join-Path $tmp "vector.zip"
    try { Invoke-WebRequest -Uri $RepoZip -OutFile $zip -UseBasicParsing }
    catch { Fail "couldn't download VECTOR ($($_.Exception.Message)). Check your internet connection." }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $found = Get-ChildItem -Path $tmp -Recurse -Filter pyproject.toml | Select-Object -First 1
    if (-not $found) { Fail "the download didn't contain VECTOR." }
    $Source = $found.DirectoryName
}
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
# Updating? Close the running app first so its files can be replaced.
Get-Process -Name "vector-app", "vector" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
if ((Resolve-Path $Source).Path.TrimEnd("\") -ne $AppSrc) {
    robocopy $Source $AppSrc /MIR /XD .venv .git __pycache__ .pytest_cache /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Fail "couldn't copy VECTOR's files to $AppSrc (robocopy code $LASTEXITCODE)." }
}
Say "Installing to $AppDir"

# ---------------------------------------------------------------- 2. python
Step 2 "Setting up Python for VECTOR"
$Uv = (Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1).Source
foreach ($candidate in @((Join-Path $env:USERPROFILE ".local\bin\uv.exe"), (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe"))) {
    if (-not $Uv -and (Test-Path $candidate)) { $Uv = $candidate }
}
if ($Uv) { Say "Already installed: uv" }
else {
    Say "Installing uv, the tool that manages VECTOR's Python..."
    try { powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" | Out-Null } catch {}
    foreach ($candidate in @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe"))) {
        if (Test-Path $candidate) { $Uv = $candidate; break }
    }
}
if (-not $Uv) { Fail "couldn't install uv (https://docs.astral.sh/uv/)." }
# Any Python 3.11-3.13 already on this computer is reused; otherwise uv fetches 3.13.
# (Newer versions like 3.15 are skipped: some voice parts don't support them yet.)
$PyWanted = ">=3.11,<3.14"
$existing = $null
try { $existing = (& $Uv python find $PyWanted 2>$null | Select-Object -First 1) } catch {}
if ($existing -and (Test-Path $existing)) {
    $pyVersion = "Python"
    try { $pyVersion = (& $existing --version) -join "" } catch {}
    Say "Already installed: $pyVersion (reusing it)"
} else {
    Say "Downloading Python 3.13 just for VECTOR (~30 MB, your own Python is left alone)..."
}
& $Uv venv $Venv --python $PyWanted --allow-existing --quiet
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Py)) { Fail "couldn't create VECTOR's Python environment." }

# ---------------------------------------------------------------- 3. packages
Step 3 "Installing VECTOR (parts already installed are skipped)"
Push-Location $AppSrc
try {
    & $Uv pip install --python $Py ".[control,app]" --quiet
    if ($LASTEXITCODE -ne 0) { Fail "installing VECTOR's packages failed." }
    $voiceOk = $true
    & $Uv pip install --python $Py ".[voice]" --quiet
    if ($LASTEXITCODE -ne 0) {
        $voiceOk = $false
        Say "Voice support couldn't be installed. Typing and the summon bar work fine." Yellow
    }
} finally { Pop-Location }
if ($voiceOk -and $env:VECTOR_INSTALL_SKIP_MODEL -ne "1") {
    & $Py -m vector --prepare-voice
    if ($LASTEXITCODE -ne 0) { Say "Couldn't download them now; VECTOR will try again when you first use voice." Yellow }
}
& $Py -m vector --setup | Out-Null

# ---------------------------------------------------------------- 4. AI brain
Step 4 "Choosing VECTOR's AI brain"
$Updating = ($env:VECTOR_INSTALL_KEEP_SETTINGS -eq "1") -and (Test-Path (Join-Path $env:USERPROFILE ".vector\config.toml"))
function Read-Secret([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
function Save-Key([string]$Name, [string]$Value) {
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "Env:$Name" -Value $Value   # so VECTOR opened from this window sees it too
    Say "Key saved for your Windows account." Green
}
$hasKey = [bool]([Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User") -or $env:ANTHROPIC_API_KEY)
$hasOpenRouter = [bool]([Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY", "User") -or $env:OPENROUTER_API_KEY)
if ($Updating) {
    Say "Updating: keeping your AI settings."
    $AiChoice = "keep"
} elseif ($AiChoice -eq "ask") {
    if ($Auto) { $AiChoice = if ($hasKey) { "claude" } elseif ($hasOpenRouter) { "openrouter" } else { "ollama" } }
    else {
        Say "  1) Free AI on this computer (Ollama). Private, works offline, no account."
        Say "  2) Free cloud AI (OpenRouter: the best free model available). Smarter, needs internet"
        Say "     and a free account. Free models have daily limits."
        Say "  3) Claude. The smartest, needs an Anthropic API key (paid)."
        Say "  4) Skip for now"
        $default = if ($hasKey) { "3" } elseif ($hasOpenRouter) { "2" } else { "1" }
        $pick = (Read-Host "Pick 1, 2, 3 or 4 [Enter = $default]").Trim()
        if (-not $pick) { $pick = $default }
        $AiChoice = @{ "1" = "ollama"; "2" = "openrouter"; "3" = "claude"; "4" = "none" }[$pick]
        if (-not $AiChoice) { $AiChoice = "none" }
    }
}

if ($AiChoice -eq "ollama") {
    $Ollama = (Get-Command ollama -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    $ollamaDefault = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (-not $Ollama -and (Test-Path $ollamaDefault)) { $Ollama = $ollamaDefault }
    if ($Ollama) { Say "Already installed: Ollama" }
    if (-not $Ollama) {
        Say "Installing Ollama (the free AI engine)..."
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install -e --id Ollama.Ollama --silent --accept-source-agreements --accept-package-agreements | Out-Null
        }
        if (-not (Test-Path $ollamaDefault)) {
            $setup = Join-Path $env:TEMP "OllamaSetup.exe"
            Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $setup -UseBasicParsing
            Say "Follow the Ollama installer that just opened, then come back here." Yellow
            Start-Process -FilePath $setup -Wait
        }
        if (Test-Path $ollamaDefault) { $Ollama = $ollamaDefault }
    }
    if (-not $Ollama) {
        Say "Ollama isn't installed. Get it from https://ollama.com and run this setup again." Yellow
    } else {
        # Pick a model the graphics card can run quickly.
        $vramMb = 0
        if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
            try { $vramMb = [int](nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | Select-Object -First 1) } catch {}
        }
        $Model = if ($vramMb -ge 6000) { "qwen2.5:7b" } else { "llama3.2" }
        $gpuNote = if ($vramMb -gt 0) { "$([math]::Round($vramMb / 1024)) GB graphics card" } else { "no NVIDIA graphics card found" }
        Say "Using AI model $Model ($gpuNote)."
        & $Py -m vector --set provider=ollama --set "model=$Model" | Out-Null
        if ($env:VECTOR_INSTALL_SKIP_MODEL -ne "1") {
            $running = $true
            try { & $Ollama list *> $null; if ($LASTEXITCODE -ne 0) { $running = $false } } catch { $running = $false }
            if (-not $running) {
                Start-Process -FilePath $Ollama -ArgumentList "serve" -WindowStyle Hidden
                Start-Sleep -Seconds 4
            }
            $models = ""
            try { $models = (& $Ollama list) -join "`n" } catch {}
            $pattern = "(?m)^" + [regex]::Escape($Model) + "(:latest)?\s"
            if ($models -match $pattern) {
                Say "Already downloaded: $Model"
            } else {
                Say "Downloading the AI model $Model (a few GB, only needed once)..."
                & $Ollama pull $Model
                if ($LASTEXITCODE -ne 0) { Say "Download failed. Later, run:  ollama pull $Model" Yellow }
            }
        }
    }
} elseif ($AiChoice -eq "openrouter") {
    if (-not $hasOpenRouter -and -not $Auto) {
        Say "1. Sign up free at https://openrouter.ai"
        Say "2. Make a key at https://openrouter.ai/keys"
        $key = Read-Secret "3. Paste the key here (it stays hidden)"
        if ($key) { Save-Key "OPENROUTER_API_KEY" $key }
    }
    & $Py -m vector --set provider=openrouter --set "model=auto:free" | Out-Null
} elseif ($AiChoice -eq "claude") {
    if (-not $hasKey -and -not $Auto) {
        Say "Get a key at https://console.anthropic.com (API keys page)."
        $key = Read-Secret "Paste your API key (it stays hidden)"
        if ($key) { Save-Key "ANTHROPIC_API_KEY" $key }
    }
    & $Py -m vector --set provider=anthropic --set model= | Out-Null
} elseif ($AiChoice -eq "keep") {
    # nothing to do
} else {
    Say "Skipped. Set it up later by running this setup again."
}

# ---------------------------------------------------------------- 5. shortcuts
Step 5 "Adding the vector command and shortcuts"
$shimDir = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
New-Item -ItemType Directory -Force -Path $shimDir | Out-Null
Set-Content -Path (Join-Path $shimDir "vector.cmd") -Encoding ASCII -Value "@echo off`r`n`"$Exe`" %*"

if ($env:VECTOR_INSTALL_NO_SHORTCUTS -ne "1") {
    $shell = New-Object -ComObject WScript.Shell
    $menu = Join-Path ([Environment]::GetFolderPath("Programs")) "VECTOR"
    New-Item -ItemType Directory -Force -Path $menu | Out-Null
    function Add-Shortcut([string]$Path, [string]$Target, [string]$Arguments, [string]$Description) {
        $lnk = $shell.CreateShortcut($Path)
        $lnk.TargetPath = $Target
        $lnk.Arguments = $Arguments
        $lnk.WorkingDirectory = $env:USERPROFILE
        $lnk.Description = $Description
        $icon = Join-Path $AppSrc "vector\assets\icon.ico"
        if (Test-Path $icon) { $lnk.IconLocation = "$icon,0" }
        $lnk.Save()
    }
    $desktop = [Environment]::GetFolderPath("Desktop")
    Add-Shortcut (Join-Path $desktop "VECTOR.lnk") $AppExe "" "Open VECTOR"
    Add-Shortcut (Join-Path $menu "VECTOR.lnk") $AppExe "" "Open VECTOR"
    Add-Shortcut (Join-Path $menu "VECTOR (terminal).lnk") $Exe "" "VECTOR in a terminal window"
    $uninstaller = Join-Path $AppSrc "scripts\uninstall-windows.ps1"
    Add-Shortcut (Join-Path $menu "Uninstall VECTOR.lnk") "powershell.exe" "-NoProfile -ExecutionPolicy Bypass -File `"$uninstaller`"" "Remove VECTOR from this computer"
}

$loginLink = Join-Path ([Environment]::GetFolderPath("Startup")) "VECTOR.lnk"
if ($Updating) {
    if (Test-Path $loginLink) { & $Py -m vector --startup on | Out-Null }   # refresh the link
} elseif (AskYes "Start VECTOR quietly in the background when you log in? (recommended)" $true) {
    & $Py -m vector --startup on | Out-Null
}

& $Exe --version | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $AppExe)) { Fail "VECTOR was installed but doesn't start." }

Write-Host ""
Write-Host "  All done!" -ForegroundColor Green
Write-Host "  VECTOR runs in the background (look for its icon by the clock):" -ForegroundColor Green
Write-Host "    - press Ctrl+Shift+Space anywhere to type to it" -ForegroundColor Green
if ($voiceOk) { Write-Host "    - or just say `"Vector, what time is it?`"" -ForegroundColor Green }
Write-Host "  Check everything works:  vector --selftest" -ForegroundColor DarkGray
Write-Host "  Remove it later: Start Menu > VECTOR > Uninstall VECTOR" -ForegroundColor DarkGray
Write-Host ""
$version = (& $Exe --version) -replace "VECTOR ", ""
Write-Host "  Installed VECTOR $version" -ForegroundColor DarkGray
if ($env:VECTOR_INSTALL_LAUNCH -eq "1") {
    Start-Process -FilePath $AppExe
    Start-Sleep -Seconds 3   # let people read the result before this window closes
} elseif (-not $Auto -and (AskYes "Open VECTOR now?" $true)) {
    Start-Process -FilePath $AppExe
}
