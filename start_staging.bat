@echo off
echo Iniciando Nginx y Staging...

:: Iniciar Nginx (si no está corriendo)
tasklist /fi "imagename eq nginx.exe" | find ":" > nul
if errorlevel 1 (
    echo Nginx ya esta corriendo.
) else (
    start /d "C:\Users\ruffineo\AppData\Local\Microsoft\WinGet\Packages\nginxinc.nginx_Microsoft.Winget.Source_8wekyb3d8bbwe\nginx-1.29.8\" nginx.exe
)

:: Configurar entorno y lanzar Flask
set FLASK_ENV=staging
call venv\Scripts\activate
flask run --host=0.0.0.0 --port=5004