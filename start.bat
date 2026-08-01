@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "MONETA_APP=Moneta Lite"
if not defined MONETA_HOST set "MONETA_HOST=127.0.0.1"
if not defined MONETA_PORT set "MONETA_PORT=8002"
if not defined MONETA_PYTHON set "MONETA_PYTHON=%CD%\.venv\Scripts\python.exe"
set "MONETA_ROOT=%CD%"
set "MONETA_LOG_DIR=%CD%\logs"
set "MONETA_PID_FILE=%MONETA_LOG_DIR%\moneta.pid"
set "MONETA_STDOUT=%MONETA_LOG_DIR%\moneta.out.log"
set "MONETA_STDERR=%MONETA_LOG_DIR%\moneta.err.log"

if not exist "%MONETA_PYTHON%" (
  echo [ERROR] No existe el entorno virtual: "%MONETA_PYTHON%"
  echo Ejecuta: py -m venv .venv ^&^& .venv\Scripts\python -m pip install -r requirements.txt
  exit /b 2
)

if not exist "%CD%\manage.py" (
  echo [ERROR] No se encontro manage.py en "%CD%".
  exit /b 2
)

if not exist "%CD%\.env" (
  echo [ERROR] Falta .env. Copia .env.example como .env y configura una clave secreta unica.
  exit /b 2
)

if not exist "%MONETA_LOG_DIR%" mkdir "%MONETA_LOG_DIR%"

powershell -NoProfile -Command "$port = 0; if ([int]::TryParse($env:MONETA_PORT, [ref]$port) -and $port -ge 1 -and $port -le 65535) { exit 0 }; exit 1"
if errorlevel 1 (
  echo [ERROR] MONETA_PORT debe ser un numero entre 1 y 65535.
  exit /b 2
)

if exist "%MONETA_PID_FILE%" (
  set /p MONETA_PROCESS_ID=<"%MONETA_PID_FILE%"
  powershell -NoProfile -Command "$processId = 0; if (-not [int]::TryParse($env:MONETA_PROCESS_ID, [ref]$processId)) { exit 1 }; $process = Get-CimInstance Win32_Process -Filter ('ProcessId = {0}' -f $processId) -ErrorAction SilentlyContinue; if (-not $process) { exit 1 }; $expected = [IO.Path]::GetFullPath($env:MONETA_PYTHON); if ([string]::Equals($process.ExecutablePath, $expected, [StringComparison]::OrdinalIgnoreCase) -and $process.CommandLine -match '(?i)manage\.py.+runserver') { exit 0 }; exit 1"
  if not errorlevel 1 (
    echo [OK] %MONETA_APP% ya esta activo.
    exit /b 0
  )
  del /q "%MONETA_PID_FILE%" >nul 2>&1
)

if not defined DJANGO_DEBUG set "DJANGO_DEBUG=1"
if not defined DJANGO_SECURE_SSL_REDIRECT set "DJANGO_SECURE_SSL_REDIRECT=0"

"%MONETA_PYTHON%" manage.py check
if errorlevel 1 (
  echo [ERROR] Django detecto una configuracion invalida.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $arguments = @('manage.py', 'runserver', ('{0}:{1}' -f $env:MONETA_HOST, $env:MONETA_PORT), '--noreload'); $process = Start-Process -FilePath $env:MONETA_PYTHON -ArgumentList $arguments -WorkingDirectory $env:MONETA_ROOT -RedirectStandardOutput $env:MONETA_STDOUT -RedirectStandardError $env:MONETA_STDERR -WindowStyle Hidden -PassThru; Set-Content -LiteralPath $env:MONETA_PID_FILE -Value $process.Id -Encoding Ascii"
if errorlevel 1 (
  echo [ERROR] No se pudo iniciar %MONETA_APP%.
  exit /b 1
)

powershell -NoProfile -Command "Start-Sleep -Seconds 2"
set /p MONETA_PROCESS_ID=<"%MONETA_PID_FILE%"
powershell -NoProfile -Command "$processId = 0; if (-not [int]::TryParse($env:MONETA_PROCESS_ID, [ref]$processId)) { exit 1 }; if (Get-Process -Id $processId -ErrorAction SilentlyContinue) { exit 0 }; exit 1"
if errorlevel 1 (
  echo [ERROR] El servidor termino durante el arranque.
  if exist "%MONETA_STDERR%" type "%MONETA_STDERR%"
  del /q "%MONETA_PID_FILE%" >nul 2>&1
  exit /b 1
)

echo [OK] %MONETA_APP% iniciado en http://%MONETA_HOST%:%MONETA_PORT%/ ^(PID %MONETA_PROCESS_ID%^).
echo Logs: "%MONETA_LOG_DIR%"
exit /b 0
