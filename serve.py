from waitress import serve
from app import app  # Importa tu instancia de Flask

if __name__ == "__main__":
    print("Iniciando servidor Waitress en el puerto 8080...")
    # 'threads' define cuántas peticiones simultáneas puede procesar
    serve(app, host='0.0.0.0', port=8080, threads=6)