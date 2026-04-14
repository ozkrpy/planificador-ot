# ACTIVAR ENTORNO PRUEBAS
.\venv\Scripts\Activate.ps1

# SETEAR VARIABLES DE ENTORNO 
$env:FLASK_APP = "app.py"
$env:FLASK_DEBUG = "1" 

# DB 
# Initialize Migrations:
flask db init
# Generate the first schema script:
flask db migrate -m "initial ot_planning setup"
# Create the database file:
flask db upgrade

# EN CASO QUE HAYA UN DESFASAJE Y NO HAGA FALTA HACER MIGRATE/UPGRADE
flask db stamp head

# CREAR UN USUARIO INICIAL EN LA BASE
from app import app, db
from models import User
with app.app_context():
     u = User(username='admin')
     u.set_password('password123')
     db.session.add(u)
     db.session.commit()
 
# SETEAR USUARIO ADMIN 
python -c "
from app import app, db; 
from models import User; 
with app.app_context(): 
     u = User.query.filter_by(username='admin').first(); 
     u.is_admin = True; 
     db.session.commit(); 
     print('Admin privileges granted!')"

# LIMPIAR CLIENTES
python -c "from app import app, db; from models import Cliente, Ubicacion; \
with app.app_context(): \
    Ubicacion.query.delete(); \
    Cliente.query.delete(); \
    db.session.commit(); \
    print('Todos los clientes y ubicaciones han sido eliminados.')"

# ACTUALIZAR MASIVAMENTE
flask shell
from app import app, db
from models import Cliente
# 1. Filtramos los clientes que tienen 'BOTH' (insensible a mayúsculas por seguridad)
target_clients = Cliente.query.filter(Cliente.tipo_contrato.ilike('BOTH'))

# 2. Contamos antes de actualizar para estar seguros
count = target_clients.count()
print(f"Se encontraron {count} registros para actualizar.")

# 3. Realizamos la actualización masiva
target_clients.update({Cliente.tipo_contrato: 'PROVEEDORES'}, synchronize_session=False)

# 4. Guardamos los cambios
db.session.commit()
print("Actualización completada exitosamente.")

# Salir del shell
exit()