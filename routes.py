from flask import abort, app, flash, json, jsonify, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlsplit # from werkzeug.urls import url_parse
from sqlalchemy import func, extract
from sqlalchemy.orm import joinedload
from models import db, User, Cliente, Ubicacion, Categoria, Recurrencia, Visita, Feriado, DetalleVisita, Personal, Vehiculo, ConfiguracionCuadrilla
from formularios import LoginForm
from utilitarios import calcular_total, calcular_proximo_dia, agrupar_por_semana
from mensajes import TEXTOS
from functools import wraps
from datetime import date, datetime, timedelta, time
from collections import defaultdict


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
                flash(TEXTOS.get("ALERT_ERROR_LOGIN", "Combinacion de usuario/contraseña invalida."), "danger")
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlsplit(next_page).netloc != '':
                next_page = url_for('index')
            return redirect(next_page)
        return render_template('login.html', title='Iniciar Sesion', form=form)

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
        # --- Datos para KPIs ---
        # Contamos visitas agendadas para hoy
        hoy = datetime.now().date()
        visitas_hoy = Visita.query.filter_by(fecha=hoy).count()
        
        equipos = ConfiguracionCuadrilla.query.count()
        
        agenda_hoy = Visita.query.filter_by(fecha=hoy).order_by(Visita.hora).all()
        # for v in agenda_hoy:
        #     print(f"Visita ID {v.id} cuadrilla { v.config_cuadrilla.nombre_cuadrilla }")
        
        # --- Datos para el Gráfico (Chart.js) ---
        pendientes = db.session.query(db.func.sum(DetalleVisita.total)).filter(DetalleVisita.estado_pago == 'PENDIENTE').scalar() or 0
        pagado = db.session.query(db.func.sum(DetalleVisita.total)).filter(DetalleVisita.estado_pago == 'PAGADO').scalar() or 0
        datos_grafico = [float(pagado), float(pendientes)]
        print(DetalleVisita.query.all())

        return render_template('index.html', 
                            txt=TEXTOS, 
                            datetime=datetime,
                            visitas_hoy=visitas_hoy,
                            pendientes_cobro=f"{pendientes:,.0f}",
                            equipos_activos=equipos,
                            agenda=agenda_hoy,
                            datos_grafico=datos_grafico)
    
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

        # ubicaciones = Ubicacion.query.all() # PLACEHOLDER: Solo para extraer ubicaciones para verificar con googlemaps
        # for u in ubicaciones: 
        #     print(f"{u.id} | {u.coordenadas_url}")
        
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
        
        # Captura de todos los campos de ubicación
        nombres = request.form.getlist('ubi_nombre[]')
        urls = request.form.getlist('ubi_url[]')
        ciudades = request.form.getlist('ubi_ciudad[]')
        barrios = request.form.getlist('ubi_barrio[]')
        calles = request.form.getlist('ubi_calle[]')
        grupos = request.form.getlist('ubi_grupo[]')

        # for nombre, url in zip(nombres, urls):
        #     if url.strip(): # Solo guardar si hay un link
        #         ubi = Ubicacion(
        #             cliente_id=nuevo_c.id, 
        #             nombre_sucursal=nombre or "Principal", 
        #             coordenadas_url=url
        #         )
        #         db.session.add(ubi)

        for data in zip(nombres, urls, ciudades, barrios, calles, grupos):
            nombre, url, ciudad, barrio, calle, grupo = data
            if url.strip() or nombre.strip(): # Guardar si tiene link o al menos un nombre
                ubi = Ubicacion(
                    cliente_id=nuevo_c.id, 
                    nombre_sucursal=nombre or "Principal", 
                    coordenadas_url=url,
                    ciudad=ciudad,
                    barrio=barrio,
                    calle_principal=calle,
                    grupo=grupo
                )
                db.session.add(ubi)

        db.session.commit()
        flash("Nuevo cliente/proveedor guardado exitosamente.", "success")
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
            
            # Limpieza y actualización de ubicaciones
            Ubicacion.query.filter_by(cliente_id=c.id).delete()
            
            nombres = request.form.getlist('ubi_nombre[]')
            urls = request.form.getlist('ubi_url[]')
            ciudades = request.form.getlist('ubi_ciudad[]')
            barrios = request.form.getlist('ubi_barrio[]')
            calles = request.form.getlist('ubi_calle[]')
            grupos = request.form.getlist('ubi_grupo[]')

            for data in zip(nombres, urls, ciudades, barrios, calles, grupos):
                nombre, url, ciudad, barrio, calle, grupo = data
                if url.strip() or nombre.strip():
                    nueva_ubi = Ubicacion(
                        cliente_id=c.id, 
                        nombre_sucursal=nombre, 
                        coordenadas_url=url,
                        ciudad=ciudad,
                        barrio=barrio,
                        calle_principal=calle,
                        grupo=grupo
                    )
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
        import json
        from collections import defaultdict  # <--- IMPORTANTE: Faltaba esto

        hoy = date.today()
        
        # 1. Datos Maestros
        cuadrillas = ConfiguracionCuadrilla.query.all()
        vehiculos = Vehiculo.query.all()
        clientes = Cliente.query.order_by(Cliente.nombre).all()

        # 2. Visitas (Nota: Asegúrate que la migración de cuadrilla_id se aplicó)
        visitas = Visita.query.filter(
            Visita.fecha >= hoy,
            Visita.estado != 'CANCELADO'
        ).order_by(Visita.fecha.asc()).all()

        # 3. Feriados (Asunción, PY)
        feriados = Feriado.query.all()
        feriados_list = [f.fecha.strftime('%Y-%m-%d') for f in feriados if f.no_laboral]

        # 4. Lógica de Agrupación por Semanas
        # Usamos defaultdict para no tener errores de llave no encontrada
        semanas = defaultdict(lambda: defaultdict(list))
        
        for v in visitas:
            # Calculamos el lunes de esa semana
            week_monday = v.fecha - timedelta(days=v.fecha.weekday())
            semanas[week_monday][v.fecha].append(v)

        # 5. Transformación a lista ordenada para el Template
        # Retorna: (Inicio_Semana, Fin_Semana, {Fecha: [Visitas]})
        semanas_lista = [
            (wk, wk + timedelta(days=5), dict(sorted(dias.items())))
            for wk, dias in sorted(semanas.items())
        ]

        DIAS_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        return render_template('agendamientos.html',
                                cuadrillas=cuadrillas,
                                visitas=visitas,
                                semanas=semanas_lista,
                                dias_es=DIAS_ES,
                                vehiculos=vehiculos,
                                clientes=clientes,
                                hoy=hoy,
                                feriados_json=json.dumps(feriados_list))

    @app.route('/generar-visitas-semana', methods=['POST'])
    @login_required
    def generar_visitas_semana():
        today = date.today()

        # ── Always generate the week AFTER the latest existing visita ────────────
        ultima_visita = Visita.query.order_by(Visita.fecha.desc()).first()
        if ultima_visita:
            ref = ultima_visita.fecha
        else:
            ref = today

        # Find that reference date's Monday, then jump one full week ahead
        monday_of_ref = ref - timedelta(days=ref.weekday())
        next_monday   = monday_of_ref + timedelta(weeks=1)
        next_saturday = next_monday + timedelta(days=5)

        # ── Feriados in that window ───────────────────────────────────────────────
        feriados_en_semana = {
            f.fecha for f in Feriado.query.filter(
                Feriado.fecha >= next_monday,
                Feriado.fecha <= next_saturday,
                Feriado.no_laboral == True
            ).all()
        }

        recurrencias = Recurrencia.query.filter_by(activo=True).all()
        generadas = omitidas = bloqueadas = 0

        for r in recurrencias:

            # ── Build the exact list of (day_index) slots to generate ────────────
            dias_a_generar = [r.dia_semana]

            if r.frecuencia == 'SEMANAL_2X' and r.segundo_dia is not None:
                segundo = int(r.segundo_dia)
                # Only add it if it's a valid workday AND different from the main day
                if 0 <= segundo <= 5 and segundo != r.dia_semana:
                    dias_a_generar.append(segundo)
                # If segundo_dia is invalid or same as main, log and skip silently
                # (don't drop the whole rule, just the second slot)

            for dia_idx in dias_a_generar:

                # Validate range — skip without clamping so we don't corrupt dates
                if not (0 <= dia_idx <= 5):
                    omitidas += 1
                    continue

                target_date = next_monday + timedelta(days=dia_idx)

                # Skip feriados
                if target_date in feriados_en_semana:
                    bloqueadas += 1
                    continue

                # Frequency gate — only on the MAIN day slot
                if dia_idx == r.dia_semana:
                    if r.frecuencia == 'QUINCENAL' and r.ultimo_generado:
                        if (target_date - r.ultimo_generado).days < 14:
                            omitidas += 1
                            continue
                    if r.frecuencia == 'MENSUAL' and r.ultimo_generado:
                        if (target_date - r.ultimo_generado).days < 28:
                            omitidas += 1
                            continue

                # Duplicate guard — exact recurrencia + date combo
                ya_existe = Visita.query.filter_by(
                    recurrencia_id=r.id,
                    fecha=target_date
                ).first()
                if ya_existe:
                    omitidas += 1
                    continue

                nueva = Visita(
                    cliente_id     = r.cliente_id,
                    ubicacion_id   = r.ubicacion_id,
                    recurrencia_id = r.id,
                    fecha          = target_date,
                    hora           = r.hora_sugerida,
                    hora_sugerida  = r.hora_sugerida,
                    servicio       = r.servicio,
                    estado         = 'PENDIENTE',
                    cuadrilla_id   = r.cuadrilla_id,
                )
                db.session.add(nueva)
                r.ultimo_generado = target_date
                generadas += 1

        db.session.commit()

        semana_str = f"{next_monday.strftime('%d/%m')} – {next_saturday.strftime('%d/%m/%Y')}"

        if generadas > 0:
            flash(
                f"✔ {generadas} visita(s) generadas para {semana_str}. "
                f"{omitidas} omitida(s) · {bloqueadas} bloqueada(s) por feriado (se debe agendar manualmente).",
                'success'
            )
        else:
            flash(
                f"No se generaron visitas nuevas para {semana_str}. "
                f"{omitidas} ya existían o no correspondían · {bloqueadas} por feriado (se debe agendar manualmente).",
                'warning'
            )

        return redirect(url_for('agendamientos'))


    @app.route('/operaciones/historico')
    @login_required
    def historico_visitas():
        # Cargamos visitas con sus relaciones para evitar múltiples consultas a la DB
        todas_las_visitas = Visita.query.options(
            joinedload(Visita.cliente),
            joinedload(Visita.detalles)
        ).order_by(Visita.fecha.desc()).all()
        
        # Agrupamos por cliente
        agrupados = {}
        for v in todas_las_visitas:
            cliente_nom = v.cliente.nombre if v.cliente else "SIN CLIENTE"
            if cliente_nom not in agrupados:
                agrupados[cliente_nom] = []
            agrupados[cliente_nom].append(v)

        cuadrillas = ConfiguracionCuadrilla.query.all()

        return render_template('agendamientos_historico.html', agrupados=agrupados, cuadrillas=cuadrillas)

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
        segundo_dia = request.form.get('segundo_dia')

        try:
            nueva_regla = Recurrencia(
                cliente_id=cliente_id,
                ubicacion_id=ubicacion_id,
                cuadrilla_id=cuadrilla_id,
                dia_semana=dia_semana,
                hora_sugerida=hora_obj,
                servicio=servicio_elegido, 
                frecuencia=frecuencia,
                segundo_dia=int(segundo_dia) if segundo_dia else None,
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
                cuadrilla_id=cuadrilla_id,
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
                    cuadrilla_id=cuadrilla_id,
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
        # todas_recurrencias = Recurrencia.query.filter_by(activo=True).all()
        todas_recurrencias = Recurrencia.query.filter_by(activo=True)\
            .options(joinedload(Recurrencia.config_cuadrilla))\
            .all()
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

        # cuadrilla = request.form.get('cuadrilla')

        # Buscar si existe un vehículo asignado por defecto a esa cuadrilla
        config = ConfiguracionCuadrilla.query.filter_by(nombre_cuadrilla=str(cuadrilla_id)).first()
        v_id = config.vehiculo_default_id if config else None

        try:
            # Convertimos el string de la fecha a objeto date
            fecha_obj = date.fromisoformat(fecha_str)
            hora_obj = datetime.strptime(hora_str, '%H:%M').time() if hora_str else None
            
            nueva_visita = Visita(
                cliente_id=cliente_id,
                ubicacion_id=ubicacion_id,
                cuadrilla_id=cuadrilla_id,
                vehiculo_id=v_id, # Asignación automática
                fecha=fecha_obj,
                hora=hora_obj,
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
    
   # Ruta para guardar la configuración de defaults

    @app.route('/visita/reagendar/<int:id>', methods=['POST'])
    @login_required
    def reagendar_visita(id):
        visita = Visita.query.get_or_404(id)
        try:
            # Actualizamos los campos con los nuevos datos del modal
            visita.fecha = date.fromisoformat(request.form.get('fecha'))
            visita.cuadrilla_id = request.form.get('cuadrilla_id')
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
    
    @app.route('/gestion/vehiculo/guardar', methods=['POST'])
    @login_required
    def guardar_vehiculo():
        v_id = request.form.get('v_id')
        denominacion = request.form.get('denominacion').upper()
        chapa = request.form.get('chapa').upper()
        tipo = request.form.get('tipo')

        if v_id: # Editar
            v = Vehiculo.query.get(v_id)
            v.denominacion = denominacion
            v.chapa = chapa
            v.tipo = tipo
        else: # Nuevo
            nuevo = Vehiculo(denominacion=denominacion, chapa=chapa, tipo=tipo)
            db.session.add(nuevo)
        
        db.session.commit()
        return redirect(url_for('gestion_personal'))

    @app.route('/gestion/vehiculo/eliminar/<int:id>')
    @login_required
    def eliminar_vehiculo(id):
        v = Vehiculo.query.get_or_404(id)
        # Opcional: Verificar si tiene visitas asociadas antes de borrar
        db.session.delete(v)
        db.session.commit()
        return redirect(url_for('gestion_personal'))
    
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
        filtro = request.args.get('filtro', 'todo')
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

# RRHH MODULE
    @app.route('/gestion/personal')
    @login_required
    def gestion_personal():

        vehiculos = Vehiculo.query.all()
        
        staff = Personal.query.all()
        vehiculos = Vehiculo.query.all()
        # cuadrillas = ConfiguracionCuadrilla.query.all()
        cuadrillas = ConfiguracionCuadrilla.query.options(
                joinedload(ConfiguracionCuadrilla.vehiculo_default)
            ).all()
        
        # Diccionario de listas: { id_vehiculo: ["Cuadrilla A", "Cuadrilla B"] }
        asignaciones = {}
        for c in cuadrillas:
            if c.vehiculo_default:
                v_id = c.vehiculo_default.id
                if v_id not in asignaciones:
                    asignaciones[v_id] = []
                asignaciones[v_id].append(c.nombre_cuadrilla)

        return render_template('personal.html', 
                            staff=staff, 
                            vehiculos=vehiculos, 
                            asignaciones=asignaciones,
                            cuadrillas=cuadrillas)

    @app.route('/gestion/personal/guardar', methods=['POST'])
    @login_required
    def guardar_personal():
        p_id = request.form.get('p_id')
        nombre = request.form.get('nombre').upper()
        rol = request.form.get('rol')
        conductor = True if request.form.get('es_conductor') else False
        sueldo = int(request.form.get('sueldo', 0))

        if p_id:
            p = Personal.query.get(p_id)
            p.nombre, p.rol, p.es_conductor, p.sueldo_base = nombre, rol, conductor, sueldo
        else:
            nuevo = Personal(nombre=nombre, rol=rol, es_conductor=conductor, sueldo_base=sueldo)
            db.session.add(nuevo)
        
        db.session.commit()
        return redirect(url_for('gestion_personal'))
    
    @app.route('/gestion/guardar-cuadrilla', methods=['POST'])
    @login_required
    def guardar_cuadrilla():
        id_cuadrilla = request.form.get('cuadrilla_id')
        nombre = request.form.get('nombre_cuadrilla')
        id_vehiculo = request.form.get('vehiculo_id')
        
        # Obtenemos la lista de IDs seleccionados en el select múltiple
        ids_personal = request.form.getlist('personal_ids') # Retorna lista de IDs ['1', '5']

        if id_cuadrilla:
            cuadrilla = ConfiguracionCuadrilla.query.get(id_cuadrilla)
        else:
            cuadrilla = ConfiguracionCuadrilla()

        cuadrilla.nombre_cuadrilla = nombre
        cuadrilla.vehiculo_default_id = id_vehiculo
        
        # Sincronizamos los integrantes
        # Buscamos los objetos Personal correspondientes a los IDs recibidos
        cuadrilla.integrantes = Personal.query.filter(Personal.id.in_(ids_personal)).all()

        db.session.add(cuadrilla)
        db.session.commit()
        return redirect(url_for('gestion_personal'))
    
    @app.route('/gestion/eliminar-cuadrilla/<int:id>')
    def eliminar_cuadrilla(id):
        cuadrilla = ConfiguracionCuadrilla.query.get_or_404(id)
        db.session.delete(cuadrilla)
        db.session.commit()
        return redirect(url_for('gestion_personal'))

    @app.route('/gestion/remover-miembro/<int:cuadrilla_id>/<int:personal_id>')
    @login_required
    def remover_miembro(cuadrilla_id, personal_id):
        # Localizamos la cuadrilla y el miembro del staff
        cuadrilla = ConfiguracionCuadrilla.query.get_or_404(cuadrilla_id)
        miembro = Personal.query.get_or_404(personal_id)
        
        # Si el miembro pertenece a la cuadrilla, lo removemos de la lista
        if miembro in cuadrilla.integrantes:
            cuadrilla.integrantes.remove(miembro)
            db.session.commit()
            
        return redirect(url_for('gestion_personal'))
    
    @app.route('/gestion/configurar-cuadrilla', methods=['POST'])
    # @login_required
    # def configurar_cuadrilla():
    #     nombre = request.form.get('nombre_cuadrilla')
    #     v_id = request.form.get('vehiculo_id')
        
    #     config = ConfiguracionCuadrilla.query.filter_by(nombre_cuadrilla=nombre).first()
    #     if not config:
    #         config = ConfiguracionCuadrilla(nombre_cuadrilla=nombre)
    #         db.session.add(config)
        
    #     config.vehiculo_default_id = v_id
    #     db.session.commit()
    #     flash(f"Vehículo predeterminado para {nombre} actualizado.", "success")
    #     return redirect(url_for('gestion_personal')) 
    @login_required
    def configurar_cuadrilla():
        # Obtenemos los IDs del formulario
        cuadrilla_id = request.form.get('cuadrilla_id')
        vehiculo_id = request.form.get('vehiculo_id')

        if not cuadrilla_id or not vehiculo_id:
            flash("Por favor, seleccione ambos campos.", "warning")
            return redirect(url_for('gestion_personal'))

        # Buscamos la cuadrilla en la base de datos
        cuadrilla = ConfiguracionCuadrilla.query.get(cuadrilla_id)
        
        if cuadrilla:
            # Actualizamos el vehículo asignado por defecto
            cuadrilla.vehiculo_default_id = vehiculo_id
            db.session.commit()
            flash(f"Logística de {cuadrilla.nombre_cuadrilla} actualizada.", "success")
        
        return redirect(url_for('gestion_personal'))

    
# API ENDPOINTS
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
