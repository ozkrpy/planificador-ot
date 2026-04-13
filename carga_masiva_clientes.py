import sys
import os
from app import app, db
from models import Cliente, Categoria, Ubicacion

def procesar_csv_corregido(ruta_archivo):
    """
    Procesa el formato: nombre|telef|ruc|tipo|ubi|corregido|email
    Ajustado para manejar textos largos en la columna de ubicación/notas.
    """
    with app.app_context():
        if not os.path.exists(ruta_archivo):
            print(f"Error: No se encuentra el archivo {ruta_archivo}")
            return

        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            lineas = f.readlines()

        if lineas and "nombre" in lineas[0].lower():
            lineas = lineas[1:]

        contador = 0
        for linea in lineas:
            linea = linea.strip()
            if not linea: continue
            
            partes = linea.split('|')
            
            if len(partes) >= 5:
                nombre_cliente = partes[0].strip()
                telefono = partes[1].strip()
                ruc = partes[2].strip()
                tipo_contrato = partes[3].strip()
                
                # La columna 4 (ubi) contiene el link y a veces notas pegadas
                raw_ubi_nota = partes[4].strip()
                
                # Intentamos separar el link de la descripción si están pegados
                url_maps = ""
                observacion = ""
                
                if "http" in raw_ubi_nota.lower():
                    # Dividimos por el primer espacio después del link para separar la nota
                    split_ubi = raw_ubi_nota.split(' ', 1)
                    url_maps = split_ubi[0].strip()
                    if len(split_ubi) > 1:
                        observacion = split_ubi[1].strip()
                else:
                    observacion = raw_ubi_nota

                # Si la columna 'corregido' tiene datos extras, los sumamos a la observación
                if len(partes) > 5 and partes[5].strip() not in ["-", ""]:
                    observacion += " | " + partes[5].strip()

                email = partes[6].strip() if len(partes) > 6 and partes[6].strip() != "-" else ""

                # 1. Asegurar Categoría
                categoria = Categoria.query.filter_by(nombre='CLIENTE').first()
                if not categoria:
                    categoria = Categoria(nombre='CLIENTE')
                    db.session.add(categoria)
                    db.session.flush()

                # 2. Crear Cliente
                nuevo_c = Cliente(
                    nombre=nombre_cliente,
                    telefono=telefono,
                    ruc=ruc,
                    tipo_contrato=tipo_contrato,
                    email=email,
                    observaciones_detalladas=observacion,
                    status='ACTIVE',
                    categoria_id=categoria.id
                )
                db.session.add(nuevo_c)
                db.session.flush()

                # 3. Crear Ubicación
                if url_maps and "http" in url_maps.lower():
                    nueva_ubi = Ubicacion(
                        cliente_id=nuevo_c.id,
                        nombre_sucursal="Principal",
                        coordenadas_url=url_maps
                    )
                    db.session.add(nueva_ubi)
                
                contador += 1
                print(f"Importado correctamente: {nombre_cliente}")

        db.session.commit()
        print(f"\nProceso finalizado. {contador} registros añadidos sin errores de formato.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        procesar_csv_corregido(sys.argv[1])
    else:
        print("Uso: python bulk_import_v2.py mi_data.csv")