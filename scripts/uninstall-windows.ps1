<#
  Removes VECTOR from this computer.
  Started by /uninstall in the summon bar, `vector --uninstall`, or Windows Settings > Apps > VECTOR.

  Unattended options:
    VECTOR_UNINSTALL_YES=1         don't ask anything
    VECTOR_UNINSTALL_KEEP_DATA=1   keep settings and memory (default when unattended); 0 = delete them
#>
$ErrorActionPreference = "Continue"
$Auto = $env:VECTOR_UNINSTALL_YES -eq "1"

Write-Host ""
Write-Host "  Uninstalling VECTOR" -ForegroundColor Cyan
Write-Host ""

$data = Join-Path $env:USERPROFILE ".vector"
if ($Auto) {
    $keep = $env:VECTOR_UNINSTALL_KEEP_DATA -ne "0"
} elseif (Test-Path $data) {
    Write-Host "Keep your settings and VECTOR's memory of you, so a reinstall remembers you?"
    $answer = (Read-Host "[Enter = keep, d = delete]").Trim().ToLower()
    $keep = $answer -notin @("d", "delete", "n", "no")
} else {
    $keep = $true
}

# VECTOR may be running; stop it so its files can be deleted.
Get-Process -Name "vector-app", "vector" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

$AppDir = Join-Path $env:LOCALAPPDATA "Programs\VECTOR"
$programs = [Environment]::GetFolderPath("Programs")
$startup = [Environment]::GetFolderPath("Startup")
$paths = @(
    (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\vector.cmd"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "VECTOR.lnk"),
    (Join-Path $programs "VECTOR.lnk"),
    (Join-Path $programs "VECTOR"),            # Start Menu folder from older versions
    (Join-Path $startup "VECTOR.bat"),
    (Join-Path $startup "VECTOR.lnk")
)
foreach ($p in $paths) {
    if (Test-Path $p) { Remove-Item -Recurse -Force $p; Write-Host "Removed $p" }
}
Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VECTOR" -Recurse -ErrorAction SilentlyContinue

if (Test-Path $AppDir) {
    Remove-Item -Recurse -Force $AppDir -ErrorAction SilentlyContinue
    if (Test-Path $AppDir) {
        Write-Host "Some files were in use; they'll be gone after a restart." -ForegroundColor Yellow
    } else {
        Write-Host "Removed $AppDir"
    }
}

if ($keep) {
    if (Test-Path $data) { Write-Host "Kept your data in $data (a reinstall will remember you)." -ForegroundColor Green }
} else {
    if (Test-Path $data) { Remove-Item -Recurse -Force $data; Write-Host "Deleted your data ($data)" }
    foreach ($name in @("VECTOR_GITHUB_TOKEN", "VECTOR_PROVIDER", "VECTOR_MODEL")) {
        [Environment]::SetEnvironmentVariable($name, $null, "User")
    }
}

Write-Host ""
Write-Host "VECTOR is uninstalled." -ForegroundColor Green
Write-Host "Your AI keys (ANTHROPIC_API_KEY / OPENROUTER_API_KEY) were left in place in case other" -ForegroundColor DarkGray
Write-Host "apps use them. Ollama is a separate app: remove it in Settings > Apps if you don't need it." -ForegroundColor DarkGray
if ($Auto) { Start-Sleep -Seconds 5 } else { Read-Host "Press Enter to close" | Out-Null }
