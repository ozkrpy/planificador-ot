from flask import app, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlsplit # from werkzeug.urls import url_parse
from models import db, User, Cliente, Ubicacion, Categoria
from formularios import LoginForm
from utilitarios import calcular_total
from mensajes import TEXTOS
from functools import wraps
from flask import abort

def init_routes(app):
# SYSTEM USERS AND AUTHENTICATION
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_admin:
                # Return a 403 Forbidden error if not admin
                abort(403)
            return f(*args, **kwargs)
        return decorated_function

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                flash(TEXTOS.get("ALERT_ERROR_LOGIN", "Invalid username or password"), "danger")
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlsplit(next_page).netloc != '':
                next_page = url_for('index')
            return redirect(next_page)
        return render_template('login.html', title='Sign In', form=form)

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('index'))

    @app.route('/ajustes/usuario/nuevo', methods=['POST'])
    @login_required 
    @admin_required
    def nuevo_usuario():
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash("El usuario ya existe", "danger")
        else:
            u = User(username=username)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash(TEXTOS["ALERT_USER_CREADO"], "success")
        return redirect(url_for('parametrico'))

    @app.route('/ajustes/usuario/eliminar/<int:id>')
    @login_required
    @admin_required
    def eliminar_usuario(id):
        # Prevent deleting yourself
        if current_user.id == id:
            flash("No puedes eliminar tu propio usuario", "danger")
            return redirect(url_for('parametrico'))
            
        u = User.query.get_or_404(id)
        db.session.delete(u)
        db.session.commit()
        flash(TEXTOS["ALERT_USER_ELIMINADO"], "success")
        return redirect(url_for('parametrico'))
    
    @app.route('/ajustes/usuario/editar/<int:id>', methods=['GET', 'POST'])
    @login_required
    def editar_usuario(id):
        # Security: Only Admin or the User themselves can edit
        if not current_user.is_admin and current_user.id != id:
            flash(TEXTOS["ERROR_PERMISO"], "danger")
            return redirect(url_for('parametrico'))

        user_to_edit = User.query.get_or_404(id)

        if request.method == 'POST':
            new_username = request.form.get('username')
            new_password = request.form.get('password')

            # Update username
            user_to_edit.username = new_username
            
            # Update password only if provided
            if new_password:
                user_to_edit.set_password(new_password)
            
            db.session.commit()
            flash(TEXTOS["ALERT_USER_ACTUALIZADO"], "success")
            return redirect(url_for('parametrico'))

        return render_template('usuario_editar.html', u=user_to_edit)

    # HOME 
    @app.route('/')
    @login_required
    def index():
        return render_template('index.html')
    
# CLIENTES MODULE
    @app.route('/clientes')
    @login_required
    def clientes():
        query_param = request.args.get('q', '').strip()
        base_query = Cliente.query

        if query_param:
            search = f"%{query_param}%"
            # Buscamos en nombre, RUC, o que el nombre de la categoría coincida exactamente
            base_query = base_query.join(Categoria).filter(
                (Cliente.nombre.ilike(search)) | 
                (Cliente.ruc.ilike(search)) |
                (Categoria.nombre.ilike(query_param)) # Coincidencia de categoría
            )

        lista_clientes = base_query.all()
        lista_categorias = Categoria.query.all()
        
        return render_template('clientes_lista.html', 
                            clientes=lista_clientes, 
                            categorias=lista_categorias
                            )

    @app.route('/clientes/nuevo')
    @login_required
    def clientes_nuevo():
        """Solo muestra el formulario en blanco."""
        categorias_list = Categoria.query.all()
        return render_template('clientes_formulario.html', categorias=categorias_list, c=None)

    @app.route('/clientes/guardar', methods=['GET', 'POST'])
    @login_required
    def clientes_guardar():
        """Solo procesa el envío del formulario."""
        # Captura y limpia la lista de teléfonos enviada como array
        lista_telefonos = request.form.getlist('telefonos[]')
        telefonos_string = ", ".join([t.strip() for t in lista_telefonos if t.strip()])

        """Solo procesa el envío del formulario."""
        nuevo_c = Cliente(
            nombre=request.form.get('nombre'),
            cedula=request.form.get('cedula'),
            ruc=request.form.get('ruc'),
            email=request.form.get('email'),
            telefono=telefonos_string,
            categoria_id=request.form.get('categoria_id'),
            tipo_contrato=request.form.get('tipo_contrato'),
            status=request.form.get('status'),
            observaciones_detalladas=request.form.get('observaciones')
        )
        db.session.add(nuevo_c)
        db.session.flush()
        
        nombres = request.form.getlist('ubi_nombre[]')
        urls = request.form.getlist('ubi_url[]')

        for nombre, url in zip(nombres, urls):
            if url.strip(): # Solo guardar si hay un link
                ubi = Ubicacion(
                    cliente_id=nuevo_c.id, 
                    nombre_sucursal=nombre or "Principal", 
                    coordenadas_url=url
                )
                db.session.add(ubi)
            
        db.session.commit()
        flash("Registro guardado exitosamente.", "success")
        return redirect(url_for('clientes'))

    @app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
    @login_required
    def clientes_editar(id):
        c = Cliente.query.get_or_404(id)
        
        if request.method == 'POST':
            # Update fields
            c.nombre = request.form.get('nombre')
            c.cedula = request.form.get('cedula')
            c.ruc = request.form.get('ruc')
            # c.telefono = request.form.get('telefono')
            # Captura la lista de teléfonos del formulario
            lista_telefonos = request.form.getlist('telefonos[]')
            # Filtra vacíos y une con comas
            c.telefono = ", ".join([t.strip() for t in lista_telefonos if t.strip()])
            c.email = request.form.get('email')
            c.categoria_id = request.form.get('categoria_id')
            c.tipo_contrato = request.form.get('tipo_contrato')
            c.status = request.form.get('status')
            c.observaciones_detalladas = request.form.get('observaciones')
            
            # Handle maps update if necessary (simplified for the primary location)
            Ubicacion.query.filter_by(cliente_id=c.id).delete()
            nombres = request.form.getlist('ubi_nombre[]')
            urls = request.form.getlist('ubi_url[]')

            for nombre, url in zip(nombres, urls):
                if url.strip():
                    nueva_ubi = Ubicacion(cliente_id=c.id, nombre_sucursal=nombre, coordenadas_url=url)
                    db.session.add(nueva_ubi)
            
            db.session.commit()
            flash("Cliente actualizado correctamente", "success")
            return redirect(url_for('clientes'))

        # GET: Show the same form but pre-filled
        categorias_list = Categoria.query.all()
        return render_template('clientes_formulario.html', c=c, categorias=categorias_list)
    
    @app.route('/clientes/eliminar/<int:id>', methods=['POST'])
    @login_required
    def clientes_eliminar(id):
        c = Cliente.query.get_or_404(id)
        
        # Opcional: Eliminar primero las ubicaciones relacionadas si no tienes delete cascade
        from models import Ubicacion
        Ubicacion.query.filter_by(cliente_id=c.id).delete()
        
        db.session.delete(c)
        db.session.commit()
        flash(f"Cliente {c.nombre} eliminado.", "success")
        return redirect(url_for('clientes'))
    
    @app.route('/clientes/categoria/guardar', methods=['POST'])
    @login_required
    @admin_required # Reuse your security layer
    def categoria_guardar():
        nombre = request.form.get('nombre').upper()
        if not Categoria.query.filter_by(nombre=nombre).first():
            nueva_cat = Categoria(nombre=nombre)
            db.session.add(nueva_cat)
            db.session.commit()
            flash("Categoría creada", "success")
        return redirect(url_for('clientes'))

    @app.route('/clientes/categoria/eliminar/<int:id>')
    @login_required
    @admin_required
    def categoria_eliminar(id):
        cat = Categoria.query.get_or_404(id)
        # Check if category is in use
        if cat.clientes:
            flash("No se puede eliminar: existen clientes usando esta categoría", "danger")
        else:
            db.session.delete(cat)
            db.session.commit()
            flash("Categoría eliminada", "success")
        return redirect(url_for('clientes'))


# AGENDAMIENTOS MODULE
    @app.route('/agendamientos')
    @login_required
    def agendamientos():
        return "Module under construction"

# AJUSTES MODULE
    @app.route('/ajustes')
    @login_required
    def parametrico():
        usuarios = User.query.all()
        return render_template('ajustes.html', usuarios=usuarios)

# FACTURACION MODULE
    @app.route('/facturacion')
    @login_required
    def facturacion():
        return "Module under construction"

