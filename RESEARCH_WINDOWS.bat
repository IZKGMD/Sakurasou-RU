@echo off
setlocal
cd /d "%~dp0"
echo Sakurasou-RU - PS Vita asset research (read only)
echo.
if not exist "work\original\data.cpk" (
  echo [ERROR] Missing work\original\data.cpk
  echo Copy from your OWN game using VitaShell, Open decrypted, FTP.
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python launcher not found. Install Python 3.10+.
  pause
  exit /b 1
)
py -3 tools\scan_assets.py "work\original\data.cpk" --report "work\reports\archive.json"
if errorlevel 1 (pause & exit /b 1)
echo.
echo CPK header checked. Next: CriPakTool.exe. No original game files were modified.
if not exist "tools\bin\CriPakTool.exe" (
  echo [INFO] Place trusted CriPakTool.exe into tools\bin\, then run again.
  echo Project: https://github.com/esperknight/CriPakTools
  pause
  exit /b 0
)
if exist "work\unpacked" (
  dir /b "work\unpacked" | findstr . >nul
  if not errorlevel 1 (
    echo [INFO] work\unpacked already has files. Not overwriting.
    goto scan
  )
)
py -3 tools\extract_cpk.py "work\original\data.cpk" --tool "tools\bin\CriPakTool.exe" --output "work\unpacked"
if errorlevel 1 (pause & exit /b 1)
:scan
py -3 tools\triage_scripts.py "work\unpacked" --report "work\reports\triage.json"
if errorlevel 1 (pause & exit /b 1)
echo.
echo Finished. Send work\reports\archive.json and triage.json for analysis.
echo Never upload game resource files to a public repo.
pause
