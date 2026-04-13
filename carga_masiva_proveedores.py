import sys
from app import app, db  # Ajusta según el nombre de tu archivo de inicialización
from models import Cliente, Categoria, Ubicacion

def procesar_carga_masiva(ruta_archivo):
    """
    Procesa un archivo con formato tipo|nombre|telefono|maps|descrip
    """
    # Usamos el contexto de la app para que SQLAlchemy pueda acceder a la DB
    with app.app_context():
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                lineas = f.readlines()
        except FileNotFoundError:
            print(f"Error: El archivo {ruta_archivo} no existe.")
            return

        # Omitir cabecera si existe
        if lineas and "tipo|nombre" in lineas[0].lower():
            lineas = lineas[1:]

        contador = 0
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue
            
            partes = linea.split('|')
            if len(partes) >= 5:
                tipo_nombre = partes[0].strip().upper()
                nombre = partes[1].strip()
                tel = partes[2].strip()
                url_maps = partes[3].strip()
                descripcion = partes[4].strip()

                # 1. Gestión de Categoría
                categoria = Categoria.query.filter_by(nombre=tipo_nombre).first()
                if not categoria:
                    categoria = Categoria(nombre=tipo_nombre)
                    db.session.add(categoria)
                    db.session.flush()

                # 2. Creación del Cliente
                nuevo_cliente = Cliente(
                    nombre=nombre,
                    telefono=tel,
                    categoria_id=categoria.id,
                    observaciones_detalladas=descripcion,
                    status='ACTIVE'
                )
                db.session.add(nuevo_cliente)
                db.session.flush()

                # 3. Ubicación
                if url_maps and url_maps.strip().lower() != 'n/a':
                    nueva_ubi = Ubicacion(
                        cliente_id=nuevo_cliente.id,
                        nombre_sucursal="Principal",
                        coordenadas_url=url_maps.strip()
                    )
                    db.session.add(nueva_ubi)
                
                contador += 1
                print(f"Procesado: {nombre}")

        db.session.commit()
        print(f"\nÉxito: Se cargaron {contador} registros.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        procesar_carga_masiva(sys.argv[1])
    else:
        print("Uso: python bulk_import.py ruta/al/archivo.txt")