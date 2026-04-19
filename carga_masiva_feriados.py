from app import app # Asegúrate de importar tu instancia de app
from models import db, Feriado
from datetime import date

def seed_feriados():
    # Lista de feriados de Paraguay para el año actual (2025/2026)
    # Nota: Los que cambian de fecha (Semana Santa) deben revisarse cada año.
    feriados_lista = [
        {"fecha": date(2026, 1, 1), "desc": "AÑO NUEVO"},
        {"fecha": date(2026, 3, 1), "desc": "DÍA DE LOS HÉROES"},
        {"fecha": date(2026, 4, 2), "desc": "JUEVES SANTO"},
        {"fecha": date(2026, 4, 3), "desc": "VIERNES SANTO"},
        {"fecha": date(2026, 5, 1), "desc": "DÍA DEL TRABAJADOR"},
        {"fecha": date(2026, 5, 14), "desc": "DÍA DE LA INDEPENDENCIA"},
        {"fecha": date(2026, 5, 15), "desc": "DÍA DE LA INDEPENDENCIA"},
        {"fecha": date(2026, 6, 12), "desc": "PAZ DEL CHACO"},
        {"fecha": date(2026, 8, 15), "desc": "FUNDACIÓN DE ASUNCIÓN"},
        {"fecha": date(2026, 9, 29), "desc": "BATALLA DE BOQUERÓN"},
        {"fecha": date(2026, 12, 8), "desc": "VIRGEN DE CAACUPÉ"},
        {"fecha": date(2026, 12, 25), "desc": "NAVIDAD"},
    ]

    with app.app_context():
        print("Iniciando carga de feriados...")
        for f in feriados_lista:
            # Evitamos duplicados
            existente = Feriado.query.filter_by(fecha=f["fecha"]).first()
            if not existente:
                nuevo_feriado = Feriado(
                    fecha=f["fecha"], 
                    descripcion=f["desc"],
                    no_laboral=True
                )
                db.session.add(nuevo_feriado)
                print(f"Añadido: {f['desc']} ({f['fecha']})")
        
        db.session.commit()
        print("¡Carga completada con éxito!")

if __name__ == "__main__":
    seed_feriados()