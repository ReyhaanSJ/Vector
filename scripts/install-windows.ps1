<#
  VECTOR installer for Windows 10/11.

  From the folder you cloned/downloaded VECTOR into, run:
      powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "  VECTOR installer" -ForegroundColor Cyan
Write-Host ""

# 1. Find Python 3.11+ (prefer 3.13: voice packages have ready-made Windows builds for it)
$py = $null
foreach ($v in @("3.13", "3.12", "3.11", "3")) {
    try {
        $out = & py "-$v" -c "import sys; print(sys.version_info >= (3, 11))" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out -eq "True") { $py = @("py", "-$v"); break }
    } catch {}
}
if (-not $py) {
    Write-Host "Python 3.11+ was not found. Installing Python 3.13 with winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
    Write-Host ""
    Write-Host "Python installed. Close this window, open a NEW PowerShell window and run the installer again." -ForegroundColor Yellow
    exit 1
}
Write-Host "Using Python: $(& $py[0] $py[1] --version)"

# 2. Create a private environment and install VECTOR into it
if (-not (Test-Path ".venv")) { & $py[0] $py[1] -m venv .venv }
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip --quiet
Write-Host "Installing VECTOR..."
& $venvPy -m pip install -e ".[control]" --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "Install failed." -ForegroundColor Red; exit 1 }

Write-Host "Installing voice support..."
& $venvPy -m pip install -e ".[voice]" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Voice packages failed to install (common on very new Python versions)." -ForegroundColor Yellow
    Write-Host "Typing mode still works. For voice, install Python 3.13 and re-run this script." -ForegroundColor Yellow
}

# 3. Put a `vector` command on PATH (WindowsApps is on the user PATH by default)
$shimDir = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
$shim = Join-Path $shimDir "vector.cmd"
Set-Content -Path $shim -Encoding ASCII -Value "@echo off`r`n`"$Root\.venv\Scripts\vector.exe`" %*"
Write-Host "Added the 'vector' command."

# 4. Pick the AI brain
& $venvPy -m vector --setup | Out-Null
Write-Host ""
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "VECTOR works best with Claude. Paste an Anthropic API key (from https://console.anthropic.com)"
    Write-Host "or press Enter to use free local AI with Ollama instead."
    $secure = Read-Host "API key" -AsSecureString
    $key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if ($key) {
        [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $key, "User")
        Write-Host "Saved the key to your user environment." -ForegroundColor Green
    } else {
        [Environment]::SetEnvironmentVariable("VECTOR_PROVIDER", "ollama", "User")
        Write-Host "Using Ollama. Install it from https://ollama.com, then run:  ollama pull llama3.1" -ForegroundColor Yellow
    }
}

# 5. Optional: start with Windows
$auto = Read-Host "Start VECTOR in voice mode every time you log in? (y/N)"
if ($auto -match "^(y|yes)$") { & $venvPy -m vector --startup on }

Write-Host ""
Write-Host "  Done! Open a NEW terminal and run:  vector" -ForegroundColor Cyan
Write-Host "  (or 'vector --voice' to talk to it)" -ForegroundColor Cyan
Write-Host ""
