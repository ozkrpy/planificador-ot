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

class Feriado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, unique=True, nullable=False)
    descripcion = db.Column(db.String(100))

    @staticmethod
    def es_laboral(fecha):
        # 1. Verificar si es Domingo (6 en Python date.weekday())
        if fecha.weekday() == 6: 
            return False
        # 2. Verificar si está en la tabla de feriados
        feriado_existe = Feriado.query.filter_by(fecha=fecha).first()
        if feriado_existe:
            return False
        return True
    
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
    tipo_contrato = db.Column(db.String(20), default='PROVEEDORES')
    
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

class Recurrencia(db.Model):
    __tablename__ = 'recurrencias'
    id = db.Column(db.Integer, primary_key=True)
    
    # El cliente dueño del contrato
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    
    # La ubicación específica donde se hará el trabajo
    ubicacion_id = db.Column(db.Integer, db.ForeignKey('ubicacion.id'), nullable=False)
    
    servicio = db.Column(db.String(50)) # Ej: 'Mantenimiento Piscina'
    frecuencia = db.Column(db.String(20), default='SEMANAL') # SEMANAL, QUINCENAL, MENSUAL
    segundo_dia = db.Column(db.Integer, nullable=True) # Para el esquema 2x semana
    ultimo_generado = db.Column(db.Date, nullable=True) # Para control de Quincenal/Mensual
    dia_semana = db.Column(db.Integer) # 0=Lunes, 1=Martes...
    cuadrilla_id = db.Column(db.Integer) # 1 o 2
    activo = db.Column(db.Boolean, default=True)
    hora_sugerida = db.Column(db.Time, nullable=True) # Nueva columna

    # Relaciones para acceder fácil a los datos
    cliente = db.relationship('Cliente', backref='reglas_recurrencia')
    ubicacion = db.relationship('Ubicacion', backref='planificaciones')

class Visita(db.Model):
    __tablename__ = 'visitas'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    cuadrilla = db.Column(db.Integer) # Crew 1 o 2
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time)
    estado = db.Column(db.String(20), default='PENDIENTE') 
    servicio = db.Column(db.String(100))
    hora_sugerida = db.Column(db.Time, nullable=True)
    observaciones = db.Column(db.Text, nullable=True)

    # Link opcional a la recurrencia que la generó
    recurrencia_id = db.Column(db.Integer, db.ForeignKey('recurrencias.id'), nullable=True)
    
    # Añade esto para saber a qué sucursal ir sin tener que buscar en la recurrencia
    ubicacion_id = db.Column(db.Integer, db.ForeignKey('ubicacion.id'))
    
    # Relaciones para que en el HTML hagas: {{ visita.cliente.nombre }}
    cliente = db.relationship('Cliente', backref='visitas_programadas')
    ubicacion = db.relationship('Ubicacion', backref='visitas_en_sitio')
    recurrencia = db.relationship('Recurrencia', backref='instancias_visita')
    detalles = db.relationship('DetalleVisita', backref='visita', lazy=True)

class DetalleVisita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visita_id = db.Column(db.Integer, db.ForeignKey('visitas.id'), nullable=False)
    
    # Datos del Ítem
    descripcion = db.Column(db.String(200), nullable=False)
    cantidad = db.Column(db.Float, default=1.0)
    precio_unitario = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    dummy = db.Column(db.Boolean, default=True)

    # --- NUEVOS CAMPOS DE TIEMPO ---
    date_created = db.Column(db.DateTime, server_default=db.func.now())
    date_modified = db.Column(db.DateTime, onupdate=db.func.now())
    date_finished = db.Column(db.DateTime, nullable=True)
    
    # Estado de Facturación y Pago
    estado_pago = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, PAGADO
    metodo_pago = db.Column(db.String(50), nullable=True) # Transferencia, Efectivo, etc.
    observaciones = db.Column(db.Text, nullable=True)