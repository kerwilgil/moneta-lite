@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "MONETA_APP=Moneta Lite"
if not defined MONETA_PYTHON set "MONETA_PYTHON=%CD%\.venv\Scripts\python.exe"
set "MONETA_ROOT=%CD%"
set "MONETA_PID_FILE=%CD%\logs\moneta.pid"

if not exist "%MONETA_PID_FILE%" (
  echo [OK] %MONETA_APP% no esta activo.
  exit /b 0
)

set /p MONETA_PROCESS_ID=<"%MONETA_PID_FILE%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$processId = 0; if (-not [int]::TryParse($env:MONETA_PROCESS_ID, [ref]$processId)) { exit 3 }; $process = Get-CimInstance Win32_Process -Filter ('ProcessId = {0}' -f $processId) -ErrorAction SilentlyContinue; if (-not $process) { exit 3 }; $expected = [IO.Path]::GetFullPath($env:MONETA_PYTHON); if (-not [string]::Equals($process.ExecutablePath, $expected, [StringComparison]::OrdinalIgnoreCase) -or $process.CommandLine -notmatch '(?i)manage\.py.+runserver') { Write-Error 'El PID pertenece a otro proceso; no se detendra.'; exit 4 }; Stop-Process -Id $processId -ErrorAction Stop; Wait-Process -Id $processId -Timeout 10 -ErrorAction SilentlyContinue; exit 0"
set "MONETA_STOP_CODE=%ERRORLEVEL%"

if "%MONETA_STOP_CODE%"=="3" (
  del /q "%MONETA_PID_FILE%" >nul 2>&1
  echo [OK] Se elimino un PID obsoleto; %MONETA_APP% ya estaba detenido.
  exit /b 0
)

if not "%MONETA_STOP_CODE%"=="0" (
  echo [ERROR] No se detuvo ningun proceso. Revisa "%MONETA_PID_FILE%".
  exit /b %MONETA_STOP_CODE%
)

del /q "%MONETA_PID_FILE%" >nul 2>&1
echo [OK] %MONETA_APP% detenido ^(PID %MONETA_PROCESS_ID%^).
exit /b 0
