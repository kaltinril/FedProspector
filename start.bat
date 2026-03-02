@echo off
setlocal
title FedProspector Startup

echo ========================================
echo  FedProspector Startup
echo ========================================
echo.

:: Check if MySQL is already running
tasklist /FI "IMAGENAME eq mysqld.exe" 2>NUL | find /I "mysqld.exe" >NUL
if %ERRORLEVEL%==0 (
    echo [OK] MySQL is already running.
) else (
    echo [..] Starting MySQL from D:\mysql ...
    start "MySQL" /MIN D:\mysql\bin\mysqld.exe --console --secure-file-priv=
    echo      Waiting for MySQL to be ready...
    :wait_mysql
    D:\mysql\bin\mysqladmin.exe -u root -proot_2026 ping >NUL 2>&1
    if %ERRORLEVEL% NEQ 0 (
        timeout /t 1 /nobreak >NUL
        goto wait_mysql
    )
    echo [OK] MySQL is running.
)

echo.
echo [..] Starting FedProspector API ...
echo      Swagger UI: http://localhost:5100/swagger
echo      Health:     http://localhost:5100/health
echo      Press Ctrl+C to stop the API.
echo.

dotnet run --project "%~dp0api\src\FedProspector.Api"
