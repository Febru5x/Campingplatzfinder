# Veroeffentlicht den aktuellen Stand auf GitHub Pages.
# Aufruf:  powershell -ExecutionPolicy Bypass -File tools\publish.ps1 [-Full]
param([switch]$Full)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo

# 1. Code/Doku aus der Arbeitskopie spiegeln (Daten bleiben in LOCALAPPDATA)
$src = Join-Path $env:LOCALAPPDATA "Campingplatzfinder\code"
robocopy "$src\pipeline" "$repo\pipeline" /E /XD __pycache__ /R:2 /W:2 /NFL /NDL /NJH /NJS | Out-Null
robocopy "$src\config"   "$repo\config"   /E /R:2 /W:2 /NFL /NDL /NJH /NJS | Out-Null
Copy-Item "$src\STATUS.md","$src\DATENQUELLEN.md" $repo -Force

# 2. Site bauen
$env:PYTHONIOENCODING = "utf-8"
if ($Full) { python -u -m tools.build_site --full } else { python -u -m tools.build_site }
if ($LASTEXITCODE -ne 0) { throw "build_site fehlgeschlagen" }

# 3. Committen + pushen
git add -A
$changes = git status --porcelain
if (-not $changes) { Write-Host "Keine Aenderungen - nichts zu veroeffentlichen."; exit 0 }
git commit -m ("Daten-Update " + (Get-Date -Format "yyyy-MM-dd HH:mm"))
git push
Write-Host "Veroeffentlicht: https://febru5x.github.io/Campingplatzfinder/ (Pages baut in 1-2 Min neu)"
