from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import MetaData

db = SQLAlchemy()

# Define a naming convention for constraints
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=metadata)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    # Relationship to see all clients of this category
    clientes = db.relationship('Cliente', backref='categoria_rel', lazy=True)

    def __repr__(self):
        return f'<Categoria {self.nombre}>'

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), nullable=True) # Optional
    ruc = db.Column(db.String(20), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    tipo_entidad = db.Column(db.String(50), default='CLIENTE') # Vivero, Jardines, etc.
 
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)   
    
    # Contract Type: 'POOL', 'GARDEN', 'BOTH'
    tipo_contrato = db.Column(db.String(20), default='BOTH')
    
    # Status: 'ACTIVE', 'SUSPENDED'
    status = db.Column(db.String(20), default='ACTIVE')
    
    # Detailed Knowledge / Notes
    # Store visit times, billing instructions, contact person, payment terms here
    observaciones_detalladas = db.Column(db.Text)
    
    # Relationship to multiple locations
    ubicaciones = db.relationship('Ubicacion', backref='cliente', lazy=True, cascade="all, delete-orphan")

class Ubicacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    nombre_sucursal = db.Column(db.String(100)) # e.g., "Casa Quinta", "Residencia Principal"
    coordenadas_url = db.Column(db.String(255)) # Google Maps Link or Coords