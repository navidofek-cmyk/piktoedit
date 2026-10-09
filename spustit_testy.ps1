# Spusti vsechny zkousky editoru.
# Pouziti:  ./spustit_testy.ps1            vsechny
#           ./spustit_testy.ps1 --rychle   bez nahodne zkousky
#           ./spustit_testy.ps1 nuz        jen sady s "nuz" v nazvu

Set-Location $PSScriptRoot
$env:QT_QPA_PLATFORM = "offscreen"
python tests\vse.py @args
exit $LASTEXITCODE
