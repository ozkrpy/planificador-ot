@echo off
setlocal
title OT Planning - Produccion (Nginx + Waitress)

:: --- CONFIGURACION DE RUTAS ---
:: Ruta de Nginx (donde esta el .exe)
set NGINX_DIR=C:\Users\ruffineo\AppData\Local\Microsoft\WinGet\Packages\nginxinc.nginx_Microsoft.Winget.Source_8wekyb3d8bbwe\nginx-1.29.8
:: Ruta de tu proyecto (donde esta app.py y venv)
set PROJECT_DIR=C:\PrivateApps\py-ot_planning

echo ====================================================
echo   INICIANDO ENTORNO DE PRODUCCION
echo ====================================================

:: 1. VALIDAR CONFIGURACION Y CERTIFICADOS
echo [1/3] Validando configuracion de Nginx y Certificados SSL...
pushd "%NGINX_DIR%"

:: Verificar si los archivos existen físicamente en la carpeta conf
if not exist "conf\cert.pem" (
    echo [ERROR] No se encuentra el archivo: %NGINX_DIR%\conf\cert.pem
    popd
    pause
    exit
)
if not exist "conf\key.pem" (
    echo [ERROR] No se encuentra el archivo: %NGINX_DIR%\conf\key.pem
    popd
    pause
    exit
)

:: Test de sintaxis de Nginx
nginx.exe -t
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] La prueba de configuracion de Nginx fallo. 
    echo Revisa los mensajes de arriba para corregir el error en nginx.conf.
    popd
    pause
    exit
)

:: Si pasa los tests, verificar si ya esta corriendo o iniciar
tasklist /fi "imagename eq nginx.exe" | find /i "nginx.exe" > nul
if %errorlevel% equ 0 (
    echo [OK] Nginx ya esta en ejecucion.
) else (
    echo [!] Iniciando Nginx...
    start nginx.exe
)
popd

:: 2. PREPARAR PYTHON (Desde la carpeta del proyecto)
echo [2/3] Preparando entorno Python en %PROJECT_DIR%...
cd /d "%PROJECT_DIR%"

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] No se encontro el entorno virtual en %PROJECT_DIR%\venv
    pause
    exit
)

call venv\Scripts\activate
set FLASK_APP=app.py
set FLASK_ENV=production
set APP_SETTINGS=config.ProductionConfig

:: Actualizar base de datos
echo [2.1] Ejecutando migraciones...
flask db upgrade

:: 3. LANZAR WAITRESS
echo [3/3] Lanzando Waitress...
echo ----------------------------------------------------
echo SISTEMA ONLINE (HTTPS configurado en Nginx)
echo ----------------------------------------------------

:: Usamos la ruta completa para serve.py por seguridad
python "%PROJECT_DIR%\serve.py"

pause