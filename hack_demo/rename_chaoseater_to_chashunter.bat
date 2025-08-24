@echo off
echo Starting ChaosEater to ChaosHunter rename process...

REM Use PowerShell to do the heavy lifting
powershell -ExecutionPolicy Bypass -File "rename_chaoseater_to_chashunter.ps1"

echo.
echo Batch script completed!
pause
