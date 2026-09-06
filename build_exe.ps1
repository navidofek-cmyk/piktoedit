# Sestavi samostatny .exe, ktery bezi i na pocitaci bez Pythonu.
# Pouziti:  ./build_exe.ps1
# Vysledek: dist\PiktoEdit.exe

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m PyInstaller --noconfirm --clean PiktoEdit.spec

Write-Host ""
Write-Host "Hotovo: dist\PiktoEdit.exe" -ForegroundColor Green
Write-Host "Sablony se pri prvnim spusteni rozbali do slozky sablony\ vedle .exe."
