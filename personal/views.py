from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth import update_session_auth_hash

from proyectos.models import Proyecto
from .models import (
    Cuadrilla, Asignacion, Rol, Trabajador, TrabajadorPerfil,
    CompetenciaTrabajador, CertificacionTrabajador, ExperienciaTrabajador,
    Notificacion,
)
from .utils_notificaciones import crear_notificacion
from comunicacion.models import archive_conversation


# -----------------------------------------------------
#  PERMISO: Solo Jefe de Proyecto
# -----------------------------------------------------
def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


# =====================================================
# 1. CREAR CUADRILLA (CORREGIDO)
# =====================================================
@login_required
@user_passes_test(es_jefe)
def crear_cuadrilla(request):

    # Mostrar solo proyectos activos al crear una cuadrilla
    proyectos = Proyecto.objects.filter(jefe=request.user, activo=True)

    # Mostrar solo trabajadores de tipo 'trabajador' (excluir líderes y jefes)
    trabajadores = (
        Trabajador.objects.filter(activo=True, tipo_trabajador='trabajador')
        .select_related("user")
        .prefetch_related("certificaciones_trabajador")
    )

    roles = Rol.objects.all()

    # Preparar lista de líderes para el selector: incluimos todos los usuarios
    # del grupo 'LiderCuadrilla' y marcamos cuáles están ocupados (lideran una
    # cuadrilla con proyecto). En el formulario de creación los ocupados se
    # mostrarán pero no serán seleccionables.
    posibles_lideres_qs = User.objects.filter(groups__name='LiderCuadrilla', is_active=True).distinct()
    posibles_lideres = []
    for u in posibles_lideres_qs:
        ocupado = Cuadrilla.objects.filter(lider=u, proyecto__isnull=False).exists()
        posibles_lideres.append({
            'user': u,
            'ocupado': ocupado,
            'selectable': not ocupado,
        })

    # Enriquecer trabajadores
    for t in trabajadores:

        # Priorizar override manual: si el trabajador tiene `manual_override`, respetar su estado
        if getattr(t, 'manual_override', False):
            t.ocupado = False
        else:
            # Considerar 'ocupado' cuando el trabajador está asignado a una cuadrilla que tiene proyecto
            t.ocupado = Asignacion.objects.filter(trabajador=t.user, cuadrilla__proyecto__isnull=False).exists() if t.user else False

        perfil = TrabajadorPerfil.objects.filter(user=t.user).first() if t.user else None
        # Priorizar el estado manual del Trabajador si manual_override está activo, sino usar el estado efectivo del perfil
        t.estado_real = t.estado if getattr(t, 'manual_override', False) else (perfil.estado_efectivo if perfil else 'disponible')

        certs = CertificacionTrabajador.objects.filter(trabajador=t)
        t.certificacion_lista = [c.nombre for c in certs]
        t.tiene_certificaciones = certs.exists()

    especialidades = (
        Trabajador.objects.exclude(especialidad__isnull=True)
        .exclude(especialidad__exact="")
        .values_list("especialidad", flat=True)
        .distinct()
    )

    certificaciones = CertificacionTrabajador.objects.values_list("nombre", flat=True).distinct()

    if request.method == "POST":

        nombre = request.POST.get("nombre")
        proyecto_id = request.POST.get("proyecto")
        lider_id = request.POST.get("lider")
        seleccionados = request.POST.getlist("trabajadores")

        proyecto = None
        if proyecto_id and proyecto_id.isdigit():
            # Asegurarse de que el proyecto seleccionado esté activo y pertenezca al jefe
            proyecto = Proyecto.objects.filter(id=proyecto_id, jefe=request.user, activo=True).first()

        # Validar que el líder seleccionado pertenezca al grupo 'LiderCuadrilla'
            lider_usuario = None
            if lider_id and lider_id.isdigit():
                lider_usuario = User.objects.filter(id=lider_id, groups__name='LiderCuadrilla').first()

            # Validación: un Líder no puede liderar más de una cuadrilla activa
            errors = []
            if lider_usuario:
                lider_conflict = Cuadrilla.objects.filter(lider=lider_usuario, proyecto__isnull=False).exists()
                if lider_conflict:
                    errors.append('El usuario seleccionado ya lidera otra cuadrilla asociada a un proyecto activo.')

            if errors:
                # En caso de error, re-renderizar el formulario con los mensajes
                return render(request, 'cuadrilla_form.html', {
                    'proyectos': proyectos,
                    'trabajadores': trabajadores,
                    'roles': roles,
                    'especialidades': especialidades,
                    'certificaciones': certificaciones,
                    'posibles_lideres': posibles_lideres,
                    'errors': errors,
                    'nombre': nombre,
                })

            cuadrilla = Cuadrilla.objects.create(
                nombre=nombre,
                proyecto=proyecto,
                lider=lider_usuario
            )

        trabajadores_asignados = []

        for trabajador_user_id in seleccionados:
            # Ahora esperamos `user.id` enviado desde la plantilla (normalizado)
            trabajador = Trabajador.objects.filter(user__id=trabajador_user_id).first()
            if not trabajador:
                # valor inválido; saltar
                continue

            # calcular estado efectivo para validación server-side
            perfil_tmp = TrabajadorPerfil.objects.filter(user=trabajador.user).first() if trabajador.user else None
            estado_efectivo = trabajador.estado if getattr(trabajador, 'manual_override', False) else (perfil_tmp.estado_efectivo if perfil_tmp else 'disponible')

            # No permitir asignar si está en licencia, vacaciones o no_disponible
            if estado_efectivo in ['licencia', 'vacaciones', 'no_disponible']:
                continue

            # No permitir asignar si ya está asignado a una cuadrilla que tiene proyecto
            asignado_a_proyecto = Asignacion.objects.filter(trabajador=trabajador.user, cuadrilla__proyecto__isnull=False).exists() if trabajador.user else False
            if asignado_a_proyecto:
                continue

            if not trabajador.user:
                user = trabajador.crear_usuario()
                Trabajador.objects.filter(pk=trabajador.pk).update(user_id=user.id)
                trabajador.user = user

            # Soporta rol personalizado por trabajador: 'roles_custom_{user_id}'
            rol_custom = (request.POST.get(f"roles_custom_{trabajador_user_id}") or '').strip()
            if rol_custom:
                rol, _ = Rol.objects.get_or_create(nombre=rol_custom)
            else:
                rol_id = request.POST.get(f"roles_{trabajador_user_id}")
                rol = Rol.objects.filter(id=rol_id).first() if rol_id and rol_id.isdigit() else None

            Asignacion.objects.create(
                trabajador=trabajador.user,
                cuadrilla=cuadrilla,
                rol=rol
            )

            trabajadores_asignados.append((trabajador.user, rol))

        # NOTIFICACIONES
        for user, rol in trabajadores_asignados:
            msg = f"Has sido asignado a la cuadrilla '{cuadrilla.nombre}'"
            if cuadrilla.proyecto:
                msg += f" en el proyecto '{cuadrilla.proyecto.nombre}'."
            else:
                msg += "."
            if rol:
                msg += f" Rol: {rol.nombre}."
            crear_notificacion(user, msg)

        if cuadrilla.lider:
            crear_notificacion(
                cuadrilla.lider,
                f"Eres líder de la nueva cuadrilla '{cuadrilla.nombre}'."
            )

        return redirect("personal:detalle_cuadrilla", cuadrilla.id)

    return render(request, "cuadrilla_form.html", {
        "proyectos": proyectos,
        "trabajadores": trabajadores,
        "roles": roles,
        "especialidades": especialidades,
        "certificaciones": certificaciones,
        "posibles_lideres": posibles_lideres,
    })


# =====================================================
# 2. EDITAR CUADRILLA (CORREGIDO)
# =====================================================
@login_required
def editar_cuadrilla(request, cuadrilla_id):

    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    # Permisos:
    # - JefeProyecto: puede editar solo cuadrillas que pertenezcan a sus proyectos
    #   o cuadrillas sin proyecto.
    # - LiderCuadrilla: solo puede editar su propia cuadrilla.
    user = request.user
    if user.groups.filter(name='JefeProyecto').exists():
        if cuadrilla.proyecto and cuadrilla.proyecto.jefe_id != user.id:
            crear_notificacion(user, 'No tienes permiso para editar esta cuadrilla.')
            return redirect('proyectos:panel')
    elif user.groups.filter(name='LiderCuadrilla').exists():
        if cuadrilla.lider_id != user.id:
            crear_notificacion(user, 'Solo puedes editar tu propia cuadrilla.')
            return redirect('proyectos:panel')
    else:
        # Otros roles no pueden editar
        return redirect('proyectos:panel')

    # Mostrar solo trabajadores de tipo 'trabajador' (excluir líderes y jefes)
    trabajadores = Trabajador.objects.filter(activo=True, tipo_trabajador='trabajador').select_related("user")
    roles = Rol.objects.all()
    # Preparar lista de líderes para el selector en edición: incluimos todos
    # y marcamos ocupados; sin embargo permitimos que el `cuadrilla.lider`
    # actual sea seleccionable incluso si su cuadrilla está asociada a un
    # proyecto (para poder conservar la selección al editar).
    posibles_lideres_qs = User.objects.filter(groups__name='LiderCuadrilla', is_active=True).distinct()
    posibles_lideres = []
    for u in posibles_lideres_qs:
        ocupado = Cuadrilla.objects.filter(lider=u, proyecto__isnull=False).exclude(id=cuadrilla.id).exists()
        # Si el usuario es el líder actual de la cuadrilla, permitir seleccionarlo
        selectable = (not ocupado) or (cuadrilla.lider and u.id == cuadrilla.lider.id)
        posibles_lideres.append({
            'user': u,
            'ocupado': ocupado and not (cuadrilla.lider and u.id == cuadrilla.lider.id),
            'selectable': selectable,
        })
    # Mostrar proyectos permitidos en el selector:
    # - Para Jefe: proyectos activos donde es jefe
    # - Para Líder: solo el proyecto actual de la cuadrilla (no permitir cambiar a otro proyecto)
    if user.groups.filter(name='JefeProyecto').exists():
        proyectos = Proyecto.objects.filter(jefe=request.user, activo=True)
    else:
        proyectos = Proyecto.objects.filter(id=cuadrilla.proyecto.id) if cuadrilla.proyecto else Proyecto.objects.none()

    asignaciones_actuales = {
        str(a.trabajador.id): a for a in Asignacion.objects.filter(cuadrilla=cuadrilla)
    }

    for t in trabajadores:
        t.asignacion = asignaciones_actuales.get(str(t.user.id)) if t.user else None

        # Enriquecer información para mostrar estado y certificaciones
        # Priorizar override manual: si el trabajador tiene `manual_override`, respetar su estado
        if getattr(t, 'manual_override', False):
            t.ocupado = False
        else:
            # Considerar 'ocupado' cuando el trabajador está asignado a una cuadrilla que tiene proyecto
            t.ocupado = Asignacion.objects.filter(trabajador=t.user, cuadrilla__proyecto__isnull=False).exists() if t.user else False
        perfil = TrabajadorPerfil.objects.filter(user=t.user).first() if t.user else None
        # Priorizar el estado manual del Trabajador si manual_override está activo, sino usar el estado efectivo del perfil
        t.estado_real = t.estado if getattr(t, 'manual_override', False) else (perfil.estado_efectivo if perfil else 'disponible')

        certs = CertificacionTrabajador.objects.filter(trabajador=t)
        t.certificacion_lista = [c.nombre for c in certs]
        t.tiene_certificaciones = certs.exists()
        # Permiso local para mostrar botón 'Quitar' en la plantilla de edición:
        if user.groups.filter(name='JefeProyecto').exists():
            t.can_remove = (not cuadrilla.proyecto) or (cuadrilla.proyecto and cuadrilla.proyecto.jefe_id == user.id)
        elif user.groups.filter(name='LiderCuadrilla').exists():
            t.can_remove = cuadrilla.lider_id == user.id
        else:
            t.can_remove = False

    if request.method == "POST":

        lider_anterior = cuadrilla.lider
        proyecto_anterior = cuadrilla.proyecto

        cuadrilla.nombre = request.POST.get("nombre")

        lider_id = request.POST.get("lider")
        cuadrilla.lider = None
        if lider_id and lider_id.isdigit():
            # Solo asignar si el usuario pertenece al grupo de líderes de cuadrilla
            posible_lider = User.objects.filter(id=lider_id, groups__name='LiderCuadrilla').first()

            # Validación: el líder no debe liderar otra cuadrilla activa distinta a esta
            if posible_lider:
                conflicto = Cuadrilla.objects.filter(lider=posible_lider, proyecto__isnull=False).exclude(id=cuadrilla.id).exists()
                if conflicto:
                    errors = [
                        'El usuario seleccionado ya lidera otra cuadrilla asociada a un proyecto activo.'
                    ]
                    # Re-renderizar formulario con error y contexto actual
                    return render(request, 'cuadrilla_editar.html', {
                        'cuadrilla': cuadrilla,
                        'trabajadores': trabajadores,
                        'roles': roles,
                        'proyectos': proyectos,
                        'posibles_lideres': posibles_lideres,
                        'errors': errors,
                    })
            cuadrilla.lider = posible_lider

        proyecto_id = request.POST.get("proyecto")
        cuadrilla.proyecto = Proyecto.objects.filter(
            id=proyecto_id,
            jefe=request.user,
            activo=True
        ).first() if proyecto_id and proyecto_id.isdigit() else None

        cuadrilla.save()

        # Si el formulario no envía ningún 'trabajadores', asumimos que no hubo cambios
        # (evita eliminar asignaciones por errores de envío del formulario/front-end).
        raw_seleccionados = request.POST.getlist("trabajadores")
        if not raw_seleccionados:
            return redirect("proyectos:panel")

        seleccionados = set(raw_seleccionados)
        restantes = asignaciones_actuales.copy()

        agregados = []
        removidos = []
        cambios_rol = []

        for trabajador_user_id in seleccionados:

            # Ahora esperamos `user.id` enviado desde la plantilla (normalizado)
            trabajador_obj = Trabajador.objects.filter(user__id=trabajador_user_id).first()
            if not trabajador_obj:
                # valor inválido; saltar
                continue

            # validar estado efectivo y evitar asignar si está en licencia/vacaciones/no_disponible
            perfil_tmp = TrabajadorPerfil.objects.filter(user=trabajador_obj.user).first() if trabajador_obj.user else None
            estado_efectivo = trabajador_obj.estado if getattr(trabajador_obj, 'manual_override', False) else (perfil_tmp.estado_efectivo if perfil_tmp else 'disponible')
            if estado_efectivo in ['licencia', 'vacaciones', 'no_disponible']:
                # Si el trabajador fue seleccionado por error, simplemente saltarlo
                continue

            # Evitar asignar si ya está asignado a una cuadrilla que tiene proyecto
            asignado_a_proyecto = Asignacion.objects.filter(trabajador=trabajador_obj.user, cuadrilla__proyecto__isnull=False).exists() if trabajador_obj.user else False
            if asignado_a_proyecto:
                continue

            if not trabajador_obj.user:
                user = trabajador_obj.crear_usuario()
                Trabajador.objects.filter(pk=trabajador_obj.pk).update(user_id=user.id)
                trabajador_obj.user = user

            user = trabajador_obj.user
            clave = str(user.id)

            # Soporta rol personalizado por trabajador: 'roles_custom_{user_id}'
            rol_custom = (request.POST.get(f"roles_custom_{trabajador_user_id}") or '').strip()
            if rol_custom:
                rol, _ = Rol.objects.get_or_create(nombre=rol_custom)
            else:
                rol_id = request.POST.get(f"roles_{trabajador_user_id}")
                rol = Rol.objects.filter(id=rol_id).first() if rol_id and rol_id.isdigit() else None

            if clave in restantes:
                asign = restantes.pop(clave)
                rol_anterior = asign.rol

                if rol_anterior != rol:
                    cambios_rol.append((user, cuadrilla, rol))

                asign.rol = rol
                asign.save()

            else:
                Asignacion.objects.create(
                    trabajador=user,
                    cuadrilla=cuadrilla,
                    rol=rol
                )
                agregados.append((user, rol))

        # Nota: NO eliminamos automáticamente las asignaciones que el usuario
        # no vuelva a seleccionar en el formulario de edición. El flujo de
        # 'editar cuadrilla' aquí añade nuevos trabajadores y actualiza roles
        # cuando corresponde, pero la eliminación explícita de un trabajador
        # debe realizarse mediante la acción dedicada `quitar_trabajador`.
        #
        # Conservamos `restantes` sin borrarlas para evitar comportamientos
        # sorpresa donde una edición parcial (p. ej. añadir un trabajador)
        # borre las asignaciones previas.
        to_delete = []

        # NOTIFICACIONES
        if lider_anterior != cuadrilla.lider:
            if lider_anterior:
                crear_notificacion(
                    lider_anterior,
                    f"Ya no eres líder de la cuadrilla '{cuadrilla.nombre}'."
                )
            if cuadrilla.lider:
                crear_notificacion(
                    cuadrilla.lider,
                    f"Has sido asignado como líder de la cuadrilla '{cuadrilla.nombre}'."
                )

        if proyecto_anterior != cuadrilla.proyecto:
            for asig in Asignacion.objects.filter(cuadrilla=cuadrilla):
                msg = f"La cuadrilla '{cuadrilla.nombre}' ha cambiado de proyecto."
                if cuadrilla.proyecto:
                    msg += f" Nuevo proyecto: {cuadrilla.proyecto.nombre}."
                crear_notificacion(asig.trabajador, msg)

        for user, rol in agregados:
            msg = f"Has sido agregado a la cuadrilla '{cuadrilla.nombre}'."
            if rol:
                msg += f" Rol: {rol.nombre}."
            crear_notificacion(user, msg)

        for user, cuad in removidos:
            crear_notificacion(user, f"Has sido removido de la cuadrilla '{cuad.nombre}'.")

        for user, cuad, rol in cambios_rol:
            if rol:
                msg = f"Tu rol en la cuadrilla '{cuad.nombre}' ahora es '{rol.nombre}'."
            else:
                msg = f"Tu rol en la cuadrilla '{cuad.nombre}' ha sido removido."
            crear_notificacion(user, msg)

        return redirect("proyectos:panel")

    return render(request, "cuadrilla_editar.html", {
        "cuadrilla": cuadrilla,
        "trabajadores": trabajadores,
        "roles": roles,
        "proyectos": proyectos,
        "posibles_lideres": posibles_lideres,
        "can_manage": True,
    })


# =====================================================
# 3. DETALLE CUADRILLA (SIN CAMBIOS)
# =====================================================
def detalle_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    # Control de acceso según rol:
    # - JefeProyecto: puede ver todas las cuadrillas
    # - LiderCuadrilla: puede ver si lidera alguna cuadrilla en el mismo proyecto (ver todas las cuadrillas del proyecto)
    # - Trabajador: solo puede ver si está asignado a esta cuadrilla
    user = request.user
    if user.is_authenticated:
        if user.groups.filter(name='JefeProyecto').exists():
            allowed = True
        elif user.groups.filter(name='LiderCuadrilla').exists():
            # permitir si el líder lidera alguna cuadrilla del mismo proyecto
            if cuadrilla.proyecto and Cuadrilla.objects.filter(proyecto=cuadrilla.proyecto, lider=user).exists():
                allowed = True
            else:
                allowed = False
        else:
            # trabajador u otros: permitir solo si está asignado a esta cuadrilla
            from .models import Asignacion as AsigModel
            allowed = AsigModel.objects.filter(trabajador=user, cuadrilla=cuadrilla).exists()
    else:
        allowed = False

    if not allowed:
        return redirect('proyectos:panel')
    asignaciones = Asignacion.objects.filter(cuadrilla=cuadrilla)

    users = [a.trabajador for a in asignaciones]
    trabajadores = Trabajador.objects.filter(user__in=users)
    perfiles = TrabajadorPerfil.objects.filter(user__in=users)
    perfil_map = {p.user_id: p for p in perfiles}

    # Construir lista enriquecida de trabajadores asignados
    trabajadores_detalle = []
    for asignacion in asignaciones:
        user = asignacion.trabajador
        trabajador = trabajadores.filter(user=user).first()
        perfil = perfil_map.get(user.id)
        # Disponibilidad: lógica unificada
        if trabajador and getattr(trabajador, 'manual_override', False):
            disponibilidad = trabajador.estado
        elif perfil:
            disponibilidad = perfil.estado_efectivo
        else:
            disponibilidad = '—'
        # Especialidad: del modelo Trabajador
        especialidad = trabajador.especialidad if trabajador and trabajador.especialidad else '—'
        trabajadores_detalle.append({
            'user': user,
            'rol': asignacion.rol,
            'disponibilidad': disponibilidad,
            'especialidad': especialidad,
            'asignacion': asignacion,
        })

    competencias = CompetenciaTrabajador.objects.filter(trabajador__in=trabajadores)
    certificaciones = CertificacionTrabajador.objects.filter(trabajador__in=trabajadores)
    experiencias = ExperienciaTrabajador.objects.filter(trabajador__in=trabajadores)

    comp_map = {}
    for c in competencias:
        user_id = c.trabajador.user_id
        comp_map.setdefault(user_id, []).append(c)

    cert_map = {}
    for c in certificaciones:
        user_id = c.trabajador.user_id
        cert_map.setdefault(user_id, []).append(c)

    exp_map = {}
    for e in experiencias:
        user_id = e.trabajador.user_id
        exp_map.setdefault(user_id, []).append(e)

    can_manage = False
    if request.user.is_authenticated:
        if request.user.groups.filter(name='JefeProyecto').exists():
            can_manage = (not cuadrilla.proyecto) or (cuadrilla.proyecto and cuadrilla.proyecto.jefe_id == request.user.id)
        elif request.user.groups.filter(name='LiderCuadrilla').exists() and cuadrilla.lider_id == request.user.id:
            can_manage = True

    return render(request, "detalle_cuadrilla.html", {
        "cuadrilla": cuadrilla,
        "trabajadores_detalle": trabajadores_detalle,
        "comp_map": comp_map,
        "cert_map": cert_map,
        "exp_map": exp_map,
        "can_manage": can_manage,
        "cuadrillas": Cuadrilla.objects.all(),
    })



@login_required
def mover_trabajador(request):
    """
    Mueve un trabajador (a través de su Asignacion) de una cuadrilla a otra.
    Espera POST con 'asignacion_id' y 'nueva_cuadrilla_id'.
    Crea notificaciones para el trabajador y, si corresponde, para los líderes afectados.
    """
    if request.method != 'POST':
        return redirect('proyectos:panel')

    asignacion_id = request.POST.get('asignacion_id')
    nueva_id = request.POST.get('nueva_cuadrilla_id')

    asign = Asignacion.objects.filter(id=asignacion_id).first()
    nueva = Cuadrilla.objects.filter(id=nueva_id).first()

    if not asign or not nueva:
        return redirect('personal:detalle_cuadrilla', asign.cuadrilla.id if asign else None)

    # Permisos: permitir acción si
    # - Usuario es JefeProyecto del proyecto origen o destino, o
    # - Usuario es LiderCuadrilla y lidera la cuadrilla origen (gestiona su propio personal)
    user = request.user
    permitido = False
    if user.groups.filter(name='JefeProyecto').exists():
        # permitir si alguna de las cuadrillas pertenece a un proyecto cuyo jefe es el usuario
        if (antigua.proyecto and antigua.proyecto.jefe_id == user.id) or (nueva.proyecto and nueva.proyecto.jefe_id == user.id):
            permitido = True
    elif user.groups.filter(name='LiderCuadrilla').exists():
        if antigua.lider_id == user.id:
            permitido = True

    if not permitido:
        crear_notificacion(user, 'No tienes permiso para mover este trabajador entre cuadrillas.')
        return redirect('personal:detalle_cuadrilla', antigua.id)

    antigua = asign.cuadrilla
    trabajador_user = asign.trabajador

    asign.cuadrilla = nueva
    asign.save()

    # Notificar al trabajador
    crear_notificacion(trabajador_user, f"Has sido trasladado de la cuadrilla '{antigua.nombre}' a '{nueva.nombre}'.")

    # Notificar líderes si aplicable
    if antigua.lider:
        crear_notificacion(antigua.lider, f"El trabajador {trabajador_user.get_full_name()} ha sido removido de tu cuadrilla '{antigua.nombre}'.")
    if nueva.lider:
        crear_notificacion(nueva.lider, f"El trabajador {trabajador_user.get_full_name()} ha sido asignado a tu cuadrilla '{nueva.nombre}'.")

    return redirect('personal:detalle_cuadrilla', nueva.id)



@login_required
def disolver_cuadrilla(request, cuadrilla_id):
    """Eliminar una cuadrilla que no esté asociada a un proyecto.

    Crea notificaciones para los trabajadores que fueran asignados y para el líder.
    """
    cuad = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    # Solo permitir disolver si no está asociada a un proyecto
    if cuad.proyecto is not None:
        crear_notificacion(request.user, f"No se puede disolver la cuadrilla '{cuad.nombre}' porque está asociada a un proyecto.")
        return redirect('personal:detalle_cuadrilla', cuad.id)

    # Permisos: permitir disolver si es líder de la cuadrilla o (si la cuadrilla está asignada
    # a un proyecto) si el usuario es el jefe de ese proyecto. Si la cuadrilla no tiene proyecto,
    # solo el líder puede disolverla.
    user = request.user
    if cuad.proyecto:
        permitido = (user.groups.filter(name='LiderCuadrilla').exists() and cuad.lider_id == user.id) or \
                    (user.groups.filter(name='JefeProyecto').exists() and cuad.proyecto.jefe_id == user.id)
    else:
        permitido = (user.groups.filter(name='LiderCuadrilla').exists() and cuad.lider_id == user.id)

    if not permitido:
        crear_notificacion(user, 'No tienes permiso para disolver esta cuadrilla.')
        return redirect('personal:detalle_cuadrilla', cuad.id)

    # Capturar información antes de eliminar
    asignaciones = list(Asignacion.objects.filter(cuadrilla=cuad))
    lider = cuad.lider
    nombre = cuad.nombre

    # Archivado: antes de borrar la cuadrilla, archivar su conversación de grupo si existe
    try:
        conv = getattr(cuad, 'conversaciones').first()
        if conv:
            archive_conversation(conv, archived_by=request.user, reason=f"Disolución de cuadrilla '{nombre}'")
    except Exception:
        pass

    # Borrar la cuadrilla (cascade eliminará asignaciones)
    cuad.delete()

    # Notificar a trabajadores
    for a in asignaciones:
        crear_notificacion(a.trabajador, f"La cuadrilla '{nombre}' ha sido disuelta. Ya no perteneces a esa cuadrilla.")

    # Notificar al líder si existía
    if lider:
        crear_notificacion(lider, f"La cuadrilla '{nombre}' que liderabas ha sido disuelta.")

    return redirect('proyectos:panel')



@login_required
def quitar_trabajador(request):
    """
    Quitar un trabajador de su cuadrilla actual.

    Espera POST con 'asignacion_id'. Elimina la Asignacion correspondiente,
    ajusta el estado del `Trabajador` a 'disponible' si no tiene `manual_override`,
    y crea notificaciones para el trabajador y el líder de la cuadrilla.

    Preparación para archivado: aquí podríamos marcar metadatos para archivar
    el historial de asignación en el futuro.
    """
    if request.method != 'POST':
        return redirect('proyectos:panel')

    asignacion_id = request.POST.get('asignacion_id')
    asign = Asignacion.objects.filter(id=asignacion_id).first()
    if not asign:
        return redirect('personal:detalle_cuadrilla', None)

    cuadrilla = asign.cuadrilla
    # Permisos: permitir si
    # - JefeProyecto del proyecto de la cuadrilla, o
    # - LiderCuadrilla y lidera la cuadrilla
    user = request.user
    permitido = False
    if user.groups.filter(name='JefeProyecto').exists():
        # permitir si el jefe es responsable del proyecto asociado a la cuadrilla (o si la cuadrilla no tiene proyecto)
        if not cuadrilla.proyecto or (cuadrilla.proyecto and cuadrilla.proyecto.jefe_id == user.id):
            permitido = True
    elif user.groups.filter(name='LiderCuadrilla').exists():
        permitido = cuadrilla.lider_id == user.id

    if not permitido:
        crear_notificacion(user, 'No tienes permiso para quitar a este trabajador.')
        return redirect('personal:detalle_cuadrilla', cuadrilla.id)

    trabajador_user = asign.trabajador

    # Capturar datos antes de eliminar
    lider = cuadrilla.lider
    nombre_cuadrilla = cuadrilla.nombre

    # Eliminar la asignación
    asign.delete()

    # Ajustar estado del Trabajador: si tenía override manual y estado especial, devolver a automático y disponible
    try:
        trabajador_profile = getattr(trabajador_user, 'trabajador_profile', None)
        if trabajador_profile:
            # Si está en modo manual y el estado es vacaciones/licencia/no_disponible, devolver a automático y disponible
            if getattr(trabajador_profile, 'manual_override', False) and trabajador_profile.estado in ['vacaciones', 'licencia', 'no_disponible']:
                trabajador_profile.manual_override = False
                trabajador_profile.estado = 'disponible'
                trabajador_profile.save()
            # Si no tiene override manual, poner disponible
            elif not getattr(trabajador_profile, 'manual_override', False):
                trabajador_profile.estado = 'disponible'
                trabajador_profile.save()
    except Exception:
        # Silenciar errores no críticos de actualización de estado
        pass

    # Notificar al trabajador
    crear_notificacion(trabajador_user, f"Has sido removido de la cuadrilla '{nombre_cuadrilla}'. Ahora estás sin cuadrilla.")

    # Notificar al líder de la cuadrilla si aplica
    if lider:
        crear_notificacion(lider, f"El trabajador {trabajador_user.get_full_name()} ha sido removido de tu cuadrilla '{nombre_cuadrilla}'.")

    # Preparación para archivado: aquí podríamos crear un registro en una tabla
    # de historial de asignaciones si se implementa más adelante.

    return redirect('personal:detalle_cuadrilla', cuadrilla.id)


# =====================================================
# 4. DETALLE TRABAJADOR (CORREGIDO)
# =====================================================
def detalle_trabajador(request, trabajador_id):

    trabajador = get_object_or_404(Trabajador, id=trabajador_id)

    perfil = TrabajadorPerfil.objects.filter(user=trabajador.user).first()
    competencias = CompetenciaTrabajador.objects.filter(trabajador=trabajador)
    certificaciones = CertificacionTrabajador.objects.filter(trabajador=trabajador)
    experiencias = ExperienciaTrabajador.objects.filter(trabajador=trabajador)

    asignaciones = Asignacion.objects.filter(trabajador=trabajador.user)

    # Calcular disponibilidad: si el trabajador tiene override manual, usar su estado;
    # en otro caso usar el estado efectivo calculado en el perfil.
    if getattr(trabajador, 'manual_override', False):
        disponibilidad = trabajador.estado
    elif perfil:
        disponibilidad = perfil.estado_efectivo
    else:
        disponibilidad = '—'

    return render(request, "detalle_trabajador.html", {
        "trabajador": trabajador,
        "perfil": perfil,
        "competencias": competencias,
        "certificaciones": certificaciones,
        "experiencias": experiencias,
        "asignaciones": asignaciones,
        "disponibilidad": disponibilidad,
    })


# =====================================================
# 5. EDITAR ESTADO TRABAJADOR
# =====================================================
def editar_estado_trabajador(request, trabajador_id):

    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    perfil = TrabajadorPerfil.objects.filter(user=trabajador.user).first()

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado_manual")

        # Opción para volver al modo automático
        if nuevo_estado == 'automatic' or nuevo_estado == '' or nuevo_estado is None:
            # Desactivar override manual; el estado será calculado automáticamente
            trabajador.manual_override = False
            trabajador.save()
            return redirect("personal:detalle_trabajador", trabajador.id)

        if nuevo_estado in ["disponible", "asignado", "vacaciones", "licencia", "inactivo", "no_disponible"]:
            # Asegurar que exista perfil
            if not perfil and trabajador.user:
                perfil = TrabajadorPerfil.objects.create(user=trabajador.user)

            # Guardar en perfil y marcar override manual en Trabajador
            if perfil:
                perfil.estado_manual = nuevo_estado
                perfil.save()

            trabajador.estado = nuevo_estado
            trabajador.manual_override = True
            trabajador.save()

            if trabajador.user:
                crear_notificacion(
                    trabajador.user,
                    f"Tu estado laboral ha cambiado a: {nuevo_estado}."
                )

        return redirect("personal:detalle_trabajador", trabajador.id)

    return render(request, "editar_estado_trabajador.html", {
        "trabajador": trabajador,
        "perfil": perfil,
    })


# =====================================================
# 6. NOTIFICACIONES
# =====================================================
@login_required
def mis_notificaciones(request):

    notifs = request.user.notificaciones.all()
    return render(request, "mis_notificaciones.html", {
        "notifs": notifs,
    })


@login_required
def marcar_todas_leidas(request):

    request.user.notificaciones.filter(leida=False).update(leida=True)
    return redirect("personal:mis_notificaciones")


# =====================================================
# 7. PASSWORD CHANGE VIEW
# =====================================================
class TrabajadorPasswordChangeView(PasswordChangeView):

    def form_valid(self, form):
        response = super().form_valid(form)

        trabajador = getattr(self.request.user, 'trabajador_profile', None)
        if trabajador:
            trabajador.password_inicial = False
            trabajador.save()

        update_session_auth_hash(self.request, form.user)
        return response
