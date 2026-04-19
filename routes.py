from flask import abort, app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlsplit # from werkzeug.urls import url_parse
from sqlalchemy import func, extract
from models import db, User, Cliente, Ubicacion, Categoria, Recurrencia, Visita, Feriado, DetalleVisita
from formularios import LoginForm
from utilitarios import calcular_total, calcular_proximo_dia
from mensajes import TEXTOS
from functools import wraps
from datetime import date, datetime, timedelta, time


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

        lista_clientes = base_query.order_by(Cliente.nombre).all()
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
        from datetime import date, timedelta
        hoy = date.today()
        fin_semana = hoy + timedelta(days=7) # Definimos el rango de 7 días
        
        # Filtramos visitas en el rango de fechas y ordenamos por fecha
        visitas_c1 = Visita.query.filter(
            Visita.fecha >= hoy, 
            Visita.fecha <= fin_semana, 
            Visita.cuadrilla == 1
        ).order_by(Visita.fecha.asc()).all()
        
        visitas_c2 = Visita.query.filter(
            Visita.fecha >= hoy, 
            Visita.fecha <= fin_semana, 
            Visita.cuadrilla == 2
        ).order_by(Visita.fecha.asc()).all()
        
        clientes = Cliente.query.order_by(Cliente.nombre).all()
        
        return render_template('agendamientos.html', 
                            visitas_c1=visitas_c1, 
                            visitas_c2=visitas_c2, 
                            clientes=clientes,
                            hoy=hoy)


    @app.route('/crear-recurrencia', methods=['POST'])
    @login_required
    def crear_recurrencia():
        # 1. Capturar datos del formulario modal
        cliente_id = request.form.get('cliente_id')
        ubicacion_id = request.form.get('ubicacion_id')
        cuadrilla_id = request.form.get('cuadrilla_id')
        dia_semana = int(request.form.get('dia_semana'))
        servicio_elegido = request.form.get('servicio').upper() # Captura la elección manual del modal
        
        hora_str = request.form.get('hora_sugerida')
        hora_obj = datetime.strptime(hora_str, '%H:%M').time() if hora_str else None

        frecuencia = request.form.get('frecuencia')
        dia1 = int(request.form.get('dia_semana'))  

        try:
            # 2. Crear el registro maestro de Recurrencia
            nueva_regla = Recurrencia(
                cliente_id=cliente_id,
                ubicacion_id=ubicacion_id,
                cuadrilla_id=cuadrilla_id,
                dia_semana=dia_semana,
                hora_sugerida=hora_obj,
                servicio=servicio_elegido, 
                frecuencia='Semanal',
                activo=True
            )
            db.session.add(nueva_regla)
            db.session.flush() # Genera el ID para la visita

            # 3. Calcular la primera visita basada en el día de la semana elegido
            hoy = date.today()
            # dias_faltantes = (dia_semana - hoy.weekday() + 7) % 7

            proxima_fecha = calcular_proximo_dia(date.today(), dia1)
            
            nueva_visita1 = Visita(
                cliente_id=cliente_id,
                ubicacion_id=ubicacion_id,
                cuadrilla=cuadrilla_id,
                fecha=proxima_fecha,
                hora_sugerida=hora_obj,
                servicio=servicio_elegido, # La visita hereda el servicio específico
                estado='PENDIENTE',
                recurrencia_id=nueva_regla.id
            )
            db.session.add(nueva_visita1)
            
            # Si es 2x semana, generamos la segunda visita de la misma semana
            if frecuencia == 'SEMANAL_2X':
                dia_secundario = int(request.form.get('segundo_dia'))
                fecha_v2 = calcular_proximo_dia(date.today(), dia_secundario)
                # Aseguramos que no se encimen si el feriado movió la fecha 1
                if fecha_v2 <= proxima_fecha:
                    fecha_v2 = proxima_fecha + timedelta(days=1)
                    while not Feriado.es_laboral(fecha_v2):
                        fecha_v2 += timedelta(days=1)
                nueva_visita2 = Visita(
                    cliente_id=cliente_id,
                    ubicacion_id=ubicacion_id,
                    cuadrilla=cuadrilla_id,
                    fecha=fecha_v2,
                    hora_sugerida=hora_obj,
                    servicio=servicio_elegido, # La visita hereda el servicio específico
                    estado='PENDIENTE',
                    recurrencia_id=nueva_regla.id
                )
                db.session.add(nueva_visita2)

            db.session.commit()
            flash('Programación semanal creada con éxito', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear programación: {str(e)}', 'danger')

        return redirect(url_for('agendamientos'))    
    
    @app.route('/agendamientos/eliminar/<int:id>', methods=['POST'])
    @login_required
    def eliminar_visita(id):
        visita = Visita.query.get_or_404(id)
        try:
            db.session.delete(visita)
            db.session.commit()
            flash("Visita eliminada correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al eliminar la visita: {str(e)}", "danger")
        
        return redirect(url_for('agendamientos'))
    
    @app.route('/recurrencias')
    @login_required
    def lista_recurrencias():
        # Obtenemos todas las recurrencias activas con los datos del cliente y ubicación
        todas_recurrencias = Recurrencia.query.filter_by(activo=True).all()
        return render_template('recurrencias_lista.html', recurrencias=todas_recurrencias)

    @app.route('/recurrencias/eliminar/<int:id>', methods=['POST'])
    @login_required
    def eliminar_recurrencia(id):
        regla = Recurrencia.query.get_or_404(id)
        try:
            # En lugar de borrar (delete), podemos desactivarla para mantener historial
            regla.activo = False 
            db.session.commit()
            flash("Programación recurrente desactivada con éxito.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al eliminar: {str(e)}", "danger")
        
        return redirect(url_for('lista_recurrencias'))
    
    @app.route('/crear-visita-esporadica', methods=['POST'])
    @login_required
    def crear_visita_esporadica():
        cliente_id = request.form.get('cliente_id')
        ubicacion_id = request.form.get('ubicacion_id')
        cuadrilla_id = request.form.get('cuadrilla_id')
        fecha_str = request.form.get('fecha') # Recibimos la fecha exacta
        servicio = request.form.get('servicio').upper()
        hora_str = request.form.get('hora_sugerida')
        obs_str= request.form.get('observaciones', '').strip()
    
        try:
            # Convertimos el string de la fecha a objeto date
            fecha_obj = date.fromisoformat(fecha_str)
            hora_obj = datetime.strptime(hora_str, '%H:%M').time() if hora_str else None
            
            nueva_visita = Visita(
                cliente_id=cliente_id,
                ubicacion_id=ubicacion_id,
                cuadrilla=cuadrilla_id,
                fecha=fecha_obj,
                hora_sugerida=hora_obj,
                servicio=servicio,
                observaciones=obs_str,
                estado='PENDIENTE',
                recurrencia_id=None # Importante: No tiene regla asociada
            )
            db.session.add(nueva_visita)
            db.session.commit()
            flash('Visita esporádica programada exitosamente', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear visita: {str(e)}', 'danger')

        return redirect(url_for('agendamientos'))
    
    @app.route('/api/visita/update-estado', methods=['POST'])
    @login_required
    def update_estado_visita():
        data = request.get_json()
        visita_id = data.get('visita_id')
        nuevo_estado = data.get('nuevo_estado').upper()
        observaciones = data.get('observaciones', '').strip()

        if nuevo_estado == 'NO ASISTIO' and not observaciones:
            return jsonify({
                'status': 'error', 
                'message': 'Debe ingresar una observación para marcar como No Asistió.'
            }), 400
        
        visita = Visita.query.get_or_404(visita_id)
        
        try:
            visita.estado = nuevo_estado
            visita.observaciones = observaciones
            db.session.commit()
            return jsonify({'status': 'success', 'nuevo_estado': nuevo_estado})
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/visita/reagendar/<int:id>', methods=['POST'])
    @login_required
    def reagendar_visita(id):
        visita = Visita.query.get_or_404(id)
        try:
            # Actualizamos los campos con los nuevos datos del modal
            visita.fecha = date.fromisoformat(request.form.get('fecha'))
            visita.cuadrilla = request.form.get('cuadrilla_id')
            visita.servicio = request.form.get('servicio').upper()
            visita.observaciones = request.form.get('observaciones')

            # Opcional: Si agregaste el campo hora_sugerida
            hora_str = request.form.get('hora_sugerida')
            if hora_str:
                visita.hora_sugerida = datetime.strptime(hora_str, '%H:%M').time()

            visita.estado = 'PENDIENTE' # Al reagendar, vuelve a estar pendiente
            db.session.commit()
            flash("Visita reprogramada exitosamente", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al reagendar: {str(e)}", "danger")
        
        return redirect(url_for('agendamientos'))
    
    @app.route('/visita/guardar-facturacion', methods=['POST'])
    @login_required
    def guardar_facturacion():
        # 1. Obtener datos principales
        visita_id = request.form.get('visita_id')
        descripciones = request.form.getlist('desc[]')
        cantidades = request.form.getlist('cant[]')
        precios = request.form.getlist('precio[]')
        estados_pago = request.form.getlist('pago_estado[]')
        metodos_pago = request.form.getlist('metodo_pago_item[]')

        visita = Visita.query.get_or_404(visita_id)
        
        try:
            # 2. Limpiar detalles previos si existen (evita duplicados en re-edición)
            DetalleVisita.query.filter_by(visita_id=visita_id).delete()
            
            # 3. Procesar cada ítem del formulario
            for i in range(len(descripciones)):
                # Validar que la descripción no esté vacía
                if not descripciones[i].strip():
                    continue
                    
                try:
                    qty = float(cantidades[i]) if cantidades[i] else 1.0
                    price = int(precios[i]) if precios[i] else 0
                    subtotal = int(qty * price)
                    
                    nuevo_detalle = DetalleVisita(
                        visita_id=visita_id,
                        descripcion=descripciones[i].upper(),
                        cantidad=qty,
                        precio_unitario=price,
                        total=subtotal,
                        estado_pago=estados_pago[i], # 'PENDIENTE' o 'PAGADO'
                        # Si el estado es PAGADO, elegir el metodo de pago; si es PENDIENTE, dejarlo en None
                        metodo_pago=metodos_pago[i] if estados_pago[i] == 'PAGADO' else None,
                        date_finished=datetime.now() if estados_pago[i] == 'PAGADO' else None
                    )
                    db.session.add(nuevo_detalle)
                except ValueError:
                    continue # Saltar filas con datos numéricos corruptos

            # 4. Actualizar estado de la visita
            visita.estado = 'COMPLETADO'
            db.session.commit()
            
            flash(f"Facturación de {visita.cliente.nombre} guardada correctamente.", "success")
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error al procesar la facturación: {str(e)}", "danger")
            
        return redirect(url_for('agendamientos'))

    @app.route('/api/cliente-detalle/<int:id>')
    @login_required
    def api_cliente_detalle(id):
        """
        Ruta auxiliar para obtener el precio base del contrato del cliente
        al abrir el modal de facturación.
        """
        cliente = Cliente.query.get_or_404(id)
        return jsonify({
            'nombre': cliente.nombre,
            'tipo_contrato': cliente.tipo_contrato,
            'tarifa_estandar': getattr(cliente, 'tarifa_mensual', 0) # Ajustar según tu modelo Cliente
        })
# AJUSTES MODULE
    @app.route('/ajustes')
    @login_required
    def parametrico():
        usuarios = User.query.all()
        feriados = Feriado.query.order_by(Feriado.fecha.asc()).all() # Añadir esto
        return render_template('ajustes.html', usuarios=usuarios, feriados=feriados)
    
    # --- FERIADOS ---
    @app.route('/ajustes/feriado/guardar', methods=['POST'])
    @login_required
    @admin_required
    def guardar_feriado():
        id_feriado = request.form.get('feriado_id')
        fecha_str = request.form.get('fecha')
        descripcion = request.form.get('descripcion').upper()
        no_laboral = True if request.form.get('no_laboral') else False
        
        
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        if id_feriado:
            f = Feriado.query.get(id_feriado)
            f.no_laboral = no_laboral
            f.fecha = fecha_obj
            f.descripcion = descripcion
        else: # Nuevo feriado
            nuevo_f = Feriado(fecha=fecha_obj, descripcion=descripcion)
            db.session.add(nuevo_f)
        
        db.session.commit()
        flash("Feriado actualizado", "success")
        return redirect(url_for('parametrico'))

    @app.route('/ajustes/feriado/eliminar/<int:id>')
    @login_required
    @admin_required
    def eliminar_feriado(id):
        f = Feriado.query.get_or_404(id)
        db.session.delete(f)
        db.session.commit()
        flash("Feriado eliminado", "info")
        return redirect(url_for('parametrico'))

# FACTURACION MODULE
    @app.route('/facturacion')
    @login_required
    def facturacion():
        filtro = request.args.get('filtro', 'pendientes')
        query = DetalleVisita.query.join(Visita)
        
        # --- APLICAR FILTROS ---
        today = datetime.today()
        if filtro == 'mes':
            query = query.filter(extract('month', DetalleVisita.date_created) == today.month,
                                extract('year', DetalleVisita.date_created) == today.year)
        elif filtro == 'año':
            query = query.filter(extract('year', DetalleVisita.date_created) == today.year)
        elif filtro == 'pendientes':
            query = query.filter(DetalleVisita.estado_pago == 'PENDIENTE')

        detalles = query.all()

        # --- AGRUPAR POR CLIENTE ---
        # Dentro de def facturacion():
        agrupados = {}
        total_deuda_global = 0      
        total_cobrado_periodo = 0   

        for d in detalles:
            c_id = d.visita.cliente_id
            v_id = d.visita.id
            
            if c_id not in agrupados:
                agrupados[c_id] = {
                    'cliente_nombre': d.visita.cliente.nombre,
                    'visitas': {}, # Cambiamos registros por un dict de visitas
                    'deuda_total': 0
                }
            
            # Dentro de la lógica de agrupación en routes.py
            if v_id not in agrupados[c_id]['visitas']:
                agrupados[c_id]['visitas'][v_id] = {
                    'fecha': d.visita.fecha,
                    'servicio_principal': d.visita.servicio,
                    'detalles_items': [], # CAMBIADO: de 'items' a 'detalles_items'
                    'total_visita': 0,
                    'pendiente_visita': 0
                }

            agrupados[c_id]['visitas'][v_id]['detalles_items'].append(d) # CAMBIADO AQUÍ TAMBIÉN
            
            # agrupados[c_id]['visitas'][v_id]['items'].append(d)
            agrupados[c_id]['visitas'][v_id]['total_visita'] += d.total
            
            if d.estado_pago == 'PENDIENTE':
                agrupados[c_id]['visitas'][v_id]['pendiente_visita'] += d.total
                agrupados[c_id]['deuda_total'] += d.total
                total_deuda_global += d.total
            else:
                total_cobrado_periodo += d.total

        return render_template('facturacion.html', 
                            agrupados_por_cliente=agrupados, 
                            total_deuda_global=total_deuda_global,
                            total_cobrado_periodo=total_cobrado_periodo)

#     @app.route('/facturacion/actualizar-pago/<int:id>', methods=['POST'])
#     @login_required
#     def actualizar_pago_item(id):
#         detalle = DetalleVisita.query.get_or_404(id)
#         data = request.get_json()
#         nuevo_estado = data.get('estado')
        
#         detalle.estado_pago = nuevo_estado
#         detalle.metodo_pago = data.get('metodo')
        
#         # Si el nuevo estado es PAGADO, guardamos la fecha de finalización
#         if nuevo_estado == 'PAGADO':
#             detalle.date_finished = datetime.now()
#         else:
#             detalle.date_finished = None # Por si se revierte a PENDIENTE
            
#         db.session.commit()
#         return jsonify({"status": "success"})   
    
# # API ENDPOINTS
    @app.route('/api/ubicaciones/<int:cliente_id>')
    @login_required
    def get_ubicaciones_cliente(cliente_id):
        ubicaciones = Ubicacion.query.filter_by(cliente_id=cliente_id).all()
        return jsonify([{
            'id': u.id,
            'nombre': u.nombre_sucursal
        } for u in ubicaciones])

    @app.route('/api/cliente-detalle/<int:cliente_id>')
    @login_required
    def get_cliente_detalle(cliente_id):
        # Esta ruta permite al modal saber qué contrato tiene el cliente por defecto
        cliente = Cliente.query.get_or_404(cliente_id)
        return jsonify({
            'id': cliente.id,
            'tipo_contrato': cliente.tipo_contrato.upper() # Asegura que el tipo de contrato se envíe en mayúsculas
        })

    @app.route('/api/visita/update-servicio', methods=['POST'])
    @login_required
    def update_servicio_visita():
        # Permite cambiar el servicio directamente desde la tabla de 7 días
        data = request.get_json()
        visita = Visita.query.get(data.get('visita_id'))
        
        if visita:
            visita.servicio = data.get('nuevo_servicio')
            db.session.commit()
            return jsonify({'status': 'ok'})
        return jsonify({'status': 'error'}), 404
    
    @app.route('/api/cliente-detalle-por-visita/<int:visita_id>')
    @login_required
    def api_cliente_detalle_visita(visita_id):
        visita = Visita.query.get_or_404(visita_id)
        precio = getattr(visita.cliente, 'tarifa_mensual', 0) 
        print(precio)
        return jsonify({'precio_base': precio})
    
    @app.route('/api/facturacion/cobrar-cliente/<int:cliente_id>', methods=['POST'])
    @login_required
    def cobrar_cliente(cliente_id):
        data = request.json
        # Buscamos todos los detalles pendientes de este cliente a través de sus visitas
        pendientes = DetalleVisita.query.join(Visita).filter(
            Visita.cliente_id == cliente_id,
            DetalleVisita.estado_pago == 'PENDIENTE'
        ).all()
        
        for item in pendientes:
            item.estado_pago = 'PAGADO'
            item.metodo_pago = data.get('metodo', 'EFECTIVO')
            item.date_finished = datetime.now()
            
        db.session.commit()
        return jsonify({"status": "success", "items_cobrados": len(pendientes)})
    
    # En el endpoint de actualizar_pago_item
    @app.route('/api/facturacion/actualizar-pago-item/<int:id>', methods=['POST'])
    @login_required
    def actualizar_pago_item(id):
        detalle = DetalleVisita.query.get_or_404(id)
        data = request.get_json()
        
        detalle.estado_pago = 'PAGADO'
        detalle.metodo_pago = data.get('metodo', 'EFECTIVO')
        detalle.date_finished = datetime.now() # Guardamos la fecha de hoy
        
        db.session.commit()
        return jsonify({"status": "success"})

    @app.route('/api/facturacion/cobrar-visita/<int:visita_id>', methods=['POST'])
    @login_required
    def cobrar_visita(visita_id):
        data = request.get_json()
        metodo = data.get('metodo', 'EFECTIVO')
        
        # Buscamos todos los ítems pendientes de esta visita específica
        detalles = DetalleVisita.query.filter_by(visita_id=visita_id, estado_pago='PENDIENTE').all()
        
        for d in detalles:
            d.estado_pago = 'PAGADO'
            d.metodo_pago = metodo
            d.date_finished = datetime.now()
            
        db.session.commit()
        return jsonify({"status": "success", "count": len(detalles)})