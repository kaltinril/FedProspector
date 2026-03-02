@echo off
setlocal enabledelayedexpansion

:: ========================================
::  FedProspector Service Manager
:: ========================================
::
::  Usage:  fed_prospector.bat <command> [service]
::
::  Commands:  start | stop | restart | status | build
::  Services:  all (default) | db | api | ui
::
::  Examples:
::    fed_prospector.bat build          Build API (Release)
::    fed_prospector.bat build api      Build API (Release)
::    fed_prospector.bat start          Start DB + API (no build)
::    fed_prospector.bat stop api       Stop only the API
::    fed_prospector.bat restart db     Restart MySQL
::    fed_prospector.bat status         Show status of all services
::

set "CMD=%~1"
set "SVC=%~2"
if "%CMD%"=="" goto :usage
if "%SVC%"=="" set "SVC=all"

:: Normalize to lowercase
for %%a in (start stop restart status build) do if /I "%CMD%"=="%%a" set "CMD=%%a"
for %%a in (all db api ui) do if /I "%SVC%"=="%%a" set "SVC=%%a"

:: Paths
set "MYSQL_DIR=D:\mysql"
set "MYSQL_BIN=%MYSQL_DIR%\bin"
set "API_PROJECT=%~dp0api\src\FedProspector.Api"
set "API_EXE=FedProspector.Api.exe"

:: Route command
if "%CMD%"=="build"   goto :cmd_build
if "%CMD%"=="start"   goto :cmd_start
if "%CMD%"=="stop"    goto :cmd_stop
if "%CMD%"=="restart" goto :cmd_restart
if "%CMD%"=="status"  goto :cmd_status
goto :usage

:: ----------------------------------------
::  BUILD
:: ----------------------------------------
:cmd_build
if "%SVC%"=="all" (
    call :build_api
) else if "%SVC%"=="api" (
    call :build_api
) else if "%SVC%"=="ui" (
    call :build_ui
) else (
    echo  [BUILD] Unknown target: %SVC%
    goto :usage
)
goto :eof

:: ----------------------------------------
::  START
:: ----------------------------------------
:cmd_start
if "%SVC%"=="all" (
    call :start_db
    call :start_api
) else if "%SVC%"=="db" (
    call :start_db
) else if "%SVC%"=="api" (
    call :start_api
) else if "%SVC%"=="ui" (
    call :start_ui
) else (
    goto :usage
)
goto :eof

:: ----------------------------------------
::  STOP
:: ----------------------------------------
:cmd_stop
if "%SVC%"=="all" (
    call :stop_api
    call :stop_db
) else if "%SVC%"=="db" (
    call :stop_db
) else if "%SVC%"=="api" (
    call :stop_api
) else if "%SVC%"=="ui" (
    call :stop_ui
) else (
    goto :usage
)
goto :eof

:: ----------------------------------------
::  RESTART
:: ----------------------------------------
:cmd_restart
if "%SVC%"=="all" (
    call :stop_api
    call :stop_db
    timeout /t 2 /nobreak >NUL
    call :start_db
    call :start_api
) else if "%SVC%"=="db" (
    call :stop_db
    timeout /t 2 /nobreak >NUL
    call :start_db
) else if "%SVC%"=="api" (
    call :stop_api
    timeout /t 1 /nobreak >NUL
    call :start_api
) else if "%SVC%"=="ui" (
    call :stop_ui
    timeout /t 1 /nobreak >NUL
    call :start_ui
) else (
    goto :usage
)
goto :eof

:: ----------------------------------------
::  STATUS
:: ----------------------------------------
:cmd_status
echo.
echo  FedProspector Service Status
echo  ============================
call :check_db
call :check_api
call :check_ui
echo.
goto :eof

:: ========================================
::  DB functions
:: ========================================
:start_db
tasklist /FI "IMAGENAME eq mysqld.exe" 2>NUL | find /I "mysqld.exe" >NUL
if %ERRORLEVEL%==0 (
    echo  [DB]  Already running.
    goto :eof
)
echo  [DB]  Starting MySQL ...
start "MySQL" /MIN "%MYSQL_BIN%\mysqld.exe" --console --secure-file-priv=
:wait_db
"%MYSQL_BIN%\mysqladmin.exe" -u root -proot_2026 ping >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    timeout /t 1 /nobreak >NUL
    goto :wait_db
)
echo  [DB]  MySQL is ready.  (port 3306)
goto :eof

:stop_db
tasklist /FI "IMAGENAME eq mysqld.exe" 2>NUL | find /I "mysqld.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo  [DB]  Not running.
    goto :eof
)
echo  [DB]  Shutting down MySQL ...
"%MYSQL_BIN%\mysqladmin.exe" -u root -proot_2026 shutdown >NUL 2>&1
echo  [DB]  Stopped.
goto :eof

:check_db
tasklist /FI "IMAGENAME eq mysqld.exe" 2>NUL | find /I "mysqld.exe" >NUL
if %ERRORLEVEL%==0 (
    echo  [DB]  Running  (port 3306)
) else (
    echo  [DB]  Stopped
)
goto :eof

:: ========================================
::  API functions
:: ========================================
:start_api
tasklist /FI "IMAGENAME eq %API_EXE%" 2>NUL | find /I "%API_EXE%" >NUL
if %ERRORLEVEL%==0 (
    echo  [API] Already running.
    goto :eof
)
echo  [API] Starting .NET API (no build) ...
start "FedProspector API" /MIN dotnet run --no-build --project "%API_PROJECT%"
:: Wait for API to respond
:wait_api
timeout /t 1 /nobreak >NUL
curl -s -o NUL -w "" http://localhost:5100/health >NUL 2>&1
if %ERRORLEVEL% NEQ 0 goto :wait_api
echo  [API] Ready.  Swagger: http://localhost:5100/swagger
echo                Health:  http://localhost:5100/health
goto :eof

:stop_api
tasklist /FI "IMAGENAME eq %API_EXE%" 2>NUL | find /I "%API_EXE%" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo  [API] Not running.
    goto :eof
)
echo  [API] Stopping ...
taskkill /IM "%API_EXE%" /F >NUL 2>&1
echo  [API] Stopped.
goto :eof

:check_api
tasklist /FI "IMAGENAME eq %API_EXE%" 2>NUL | find /I "%API_EXE%" >NUL
if %ERRORLEVEL%==0 (
    echo  [API] Running  (http://localhost:5100/swagger)
) else (
    echo  [API] Stopped
)
goto :eof

:: ========================================
::  Build functions
:: ========================================
:build_api
echo  [API] Building (Release) ...
dotnet build "%~dp0api\FedProspector.Api.slnx" -c Release --verbosity quiet
if %ERRORLEVEL%==0 (
    echo  [API] Build succeeded.
) else (
    echo  [API] Build FAILED.
)
goto :eof

:build_ui
echo  [UI]  Not yet implemented. (Awaiting frontend framework selection)
goto :eof

:: ========================================
::  UI functions (placeholder)
:: ========================================
:start_ui
echo  [UI]  Not yet implemented. (Awaiting frontend framework selection)
goto :eof

:stop_ui
echo  [UI]  Not yet implemented.
goto :eof

:check_ui
echo  [UI]  Not yet implemented
goto :eof

:: ========================================
::  Usage
:: ========================================
:usage
echo.
echo  Usage:  fed_prospector.bat ^<command^> [service]
echo.
echo  Commands:
echo    build      Build project(s) (Release config)
echo    start      Start service(s) (no build, run build first)
echo    stop       Stop service(s)
echo    restart    Stop then start service(s)
echo    status     Show running status
echo.
echo  Services:
echo    all        DB + API + UI  (default)
echo    db         MySQL only
echo    api        .NET API only
echo    ui         Frontend only  (not yet implemented)
echo.
echo  Examples:
echo    fed_prospector.bat build
echo    fed_prospector.bat start
echo    fed_prospector.bat stop api
echo    fed_prospector.bat restart db
echo    fed_prospector.bat status
echo.
goto :eof
