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
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # makes downloads much faster in Windows PowerShell

$RepoZip = "https://github.com/ReyhaanSJ/Vector/archive/HEAD.zip"
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
    Say "Downloading the latest version..."
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
Step 2 "Setting up Python (a private copy just for VECTOR)"
$Uv = (Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $Uv) {
    Say "Installing uv, the tool that manages VECTOR's Python..."
    try { powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" | Out-Null } catch {}
    foreach ($candidate in @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe"))) {
        if (Test-Path $candidate) { $Uv = $candidate; break }
    }
}
if (-not $Uv) { Fail "couldn't install uv (https://docs.astral.sh/uv/)." }
& $Uv venv $Venv --python 3.13 --allow-existing --quiet
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Py)) { Fail "couldn't create VECTOR's Python environment." }

# ---------------------------------------------------------------- 3. packages
Step 3 "Installing VECTOR (about a minute)"
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
    Say "Downloading the offline speech models (~200 MB, only once)..."
    & $Py -m vector --prepare-voice
    if ($LASTEXITCODE -ne 0) { Say "Couldn't download them now; VECTOR will try again when you first use voice." Yellow }
}
& $Py -m vector --setup | Out-Null

# ---------------------------------------------------------------- 4. AI brain
Step 4 "Choosing VECTOR's AI brain"
$hasKey = [bool]([Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User") -or $env:ANTHROPIC_API_KEY)
if ($AiChoice -eq "ask") {
    if ($Auto) { $AiChoice = if ($hasKey) { "claude" } else { "ollama" } }
    else {
        Say "  1) Free AI that runs on this computer (Ollama). No account or payment needed."
        Say "  2) Claude. Smartest, needs an Anthropic API key (paid)."
        Say "  3) Skip for now"
        $default = if ($hasKey) { "2" } else { "1" }
        $pick = (Read-Host "Pick 1, 2 or 3 [Enter = $default]").Trim()
        if (-not $pick) { $pick = $default }
        $AiChoice = @{ "1" = "ollama"; "2" = "claude"; "3" = "none" }[$pick]
        if (-not $AiChoice) { $AiChoice = "none" }
    }
}

if ($AiChoice -eq "ollama") {
    $Ollama = (Get-Command ollama -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    $ollamaDefault = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (-not $Ollama -and (Test-Path $ollamaDefault)) { $Ollama = $ollamaDefault }
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
            Say "Downloading the AI model (a few GB, only needed once)..."
            & $Ollama pull $Model
            if ($LASTEXITCODE -ne 0) { Say "Download failed. Later, run:  ollama pull $Model" Yellow }
        }
    }
} elseif ($AiChoice -eq "claude") {
    if (-not $hasKey -and -not $Auto) {
        Say "Get a key at https://console.anthropic.com (API keys page)."
        $secure = Read-Host "Paste your API key (it stays hidden)" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        if ($key) {
            [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $key.Trim(), "User")
            Say "Key saved for your Windows account." Green
        }
    }
    & $Py -m vector --set provider=anthropic | Out-Null
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
        $lnk.Save()
    }
    $desktop = [Environment]::GetFolderPath("Desktop")
    Add-Shortcut (Join-Path $desktop "VECTOR.lnk") $AppExe "" "Open VECTOR"
    Add-Shortcut (Join-Path $menu "VECTOR.lnk") $AppExe "" "Open VECTOR"
    Add-Shortcut (Join-Path $menu "VECTOR (terminal).lnk") $Exe "" "VECTOR in a terminal window"
    $uninstaller = Join-Path $AppSrc "scripts\uninstall-windows.ps1"
    Add-Shortcut (Join-Path $menu "Uninstall VECTOR.lnk") "powershell.exe" "-NoProfile -ExecutionPolicy Bypass -File `"$uninstaller`"" "Remove VECTOR from this computer"
}

if (AskYes "Start VECTOR quietly in the background when you log in? (recommended)" $true) {
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
if (-not $Auto -and (AskYes "Open VECTOR now?" $true)) { Start-Process -FilePath $AppExe }
