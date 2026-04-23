from app import db, app
from models import Recurrencia, Visita, ConfiguracionCuadrilla, Personal, Vehiculo

def clean_transactional_data():
    with app.app_context():
        print("Iniciando limpieza de datos...")
        
        try:
            db.session.query(Visita).delete()
            print("- Historial de visitas limpio.")

            db.session.query(ConfiguracionCuadrilla).delete()
            print("- Configuraciones de cuadrilla reiniciadas.")

            db.session.query(Personal).delete()
            print("- Configuraciones de Personal reiniciadas.")
            
            db.session.query(Vehiculo).delete()
            print("- Configuraciones de Vehículos reiniciadas.")
            
            db.session.query(Recurrencia).delete()
            print("- Configuraciones de recurrencias reiniciadas.")

            db.session.commit()
            print(">>> Limpieza completada con éxito. Los clientes se mantienen intactos.")
            
        except Exception as e:
            db.session.rollback()
            print(f"ERROR: No se pudo limpiar la base de datos: {e}")

if __name__ == "__main__":
    clean_transactional_data()