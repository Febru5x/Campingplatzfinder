# Update-Lauf: alle Regionen auffrischen (ohne KI) und veroeffentlichen.
# Fuer Windows-Aufgabenplanung, z.B. alle 4 Wochen:
#   Programm: powershell.exe
#   Argumente: -ExecutionPolicy Bypass -File "C:\Users\bruen\Campingplatzfinder\tools\refresh.ps1"
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$code = "$env:LOCALAPPDATA\Campingplatzfinder\code"
$log = "$env:LOCALAPPDATA\Campingplatzfinder\refresh_log.txt"

"=== Refresh gestartet $(Get-Date -Format 'yyyy-MM-dd HH:mm') ===" | Out-File $log -Encoding utf8
Set-Location $code
python -u -m pipeline.refresh alle 2>&1 | Tee-Object -FilePath $log -Append
"=== Refresh fertig $(Get-Date -Format 'yyyy-MM-dd HH:mm') ===" | Out-File $log -Append -Encoding utf8

# Veroeffentlichen (Repo mit Tools)
Set-Location "$env:USERPROFILE\Campingplatzfinder"
powershell -ExecutionPolicy Bypass -File tools\publish.ps1 2>&1 | Tee-Object -FilePath $log -Append