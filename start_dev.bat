@echo off
echo Iniciando Entorno de DESARROLLO...
:: Activar el entorno virtual
call venv\Scripts\activate

:: Configurar variables de entorno
set FLASK_ENV=development
set APP_SETTINGS=config.DevelopmentConfig

:: Ejecutar migraciones y servidor
flask db upgrade
flask run --debug --host=0.0.0.0 --port=5000

pause