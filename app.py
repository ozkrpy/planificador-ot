from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from parametros import Config
from models import db, User
from routes import init_routes
from mensajes import TEXTOS

app = Flask(__name__)
app.config.from_object(Config)

@app.template_filter('number_format')
def number_format(value):
    if value is None:
        return "0"
    try:
        # Formato para Guaraníes: puntos como separadores de miles, sin decimales
        return "{:,.0f}".format(value).replace(",", ".")
    except (ValueError, TypeError):
        return value
    
db.init_app(app)
migrate = Migrate(app, db)

@app.route('/favicon.ico')
def favicon():
    return '', 204

# Login Manager Setup
login = LoginManager(app)
login.login_view = 'login' # Where to redirect if @login_required fails

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.context_processor
def inject_textos():
    return dict(txt=TEXTOS)

@app.errorhandler(403)
def forbidden_error(error):
    return "No tienes permisos para realizar esta acción.", 403

init_routes(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')