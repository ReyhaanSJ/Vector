<#
  Removes VECTOR from this computer.
  Start Menu > VECTOR > Uninstall VECTOR runs this.
  Set VECTOR_UNINSTALL_YES=1 to skip the questions (keeps your settings and memory).
#>
$ErrorActionPreference = "Continue"
$Auto = $env:VECTOR_UNINSTALL_YES -eq "1"

function AskYes([string]$Question) {
    if ($Auto) { return $false }
    $answer = (Read-Host "$Question [y = yes, Enter = no]").Trim().ToLower()
    return $answer -in @("y", "yes")
}

Write-Host ""
Write-Host "  Uninstalling VECTOR" -ForegroundColor Cyan
Write-Host ""

$AppDir = Join-Path $env:LOCALAPPDATA "Programs\VECTOR"
$paths = @(
    (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\vector.cmd"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "VECTOR.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "VECTOR"),
    (Join-Path ([Environment]::GetFolderPath("Startup")) "VECTOR.bat"),
    (Join-Path ([Environment]::GetFolderPath("Startup")) "VECTOR.lnk")
)
foreach ($p in $paths) {
    if (Test-Path $p) { Remove-Item -Recurse -Force $p; Write-Host "Removed $p" }
}

# VECTOR may be running; stop it so its files can be deleted.
Get-Process -Name "vector-app", "vector" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
if (Test-Path $AppDir) {
    Remove-Item -Recurse -Force $AppDir
    Write-Host "Removed $AppDir"
}

$data = Join-Path $env:USERPROFILE ".vector"
if ((Test-Path $data) -and (AskYes "Also delete VECTOR's settings and memory ($data)?")) {
    Remove-Item -Recurse -Force $data
    Write-Host "Removed $data"
}

Write-Host ""
Write-Host "VECTOR is uninstalled." -ForegroundColor Green
Write-Host "Ollama (the free AI) is a separate app: remove it in Settings > Apps if you don't need it." -ForegroundColor DarkGray
if (-not $Auto) { Read-Host "Press Enter to close" | Out-Null }
