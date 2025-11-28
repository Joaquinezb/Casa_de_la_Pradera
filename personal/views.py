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
@user_passes_test(es_jefe)
def editar_cuadrilla(request, cuadrilla_id):

    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)

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
    # Mostrar solo proyectos activos al editar una cuadrilla
    proyectos = Proyecto.objects.filter(jefe=request.user, activo=True)

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
    })


# =====================================================
# 3. DETALLE CUADRILLA (SIN CAMBIOS)
# =====================================================
def detalle_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    asignaciones = Asignacion.objects.filter(cuadrilla=cuadrilla)

    users = [a.trabajador for a in asignaciones]

    # Obtener los Trabajador correspondientes a los Users asignados
    trabajadores = Trabajador.objects.filter(user__in=users)

    perfiles = TrabajadorPerfil.objects.filter(user__in=users)
    competencias = CompetenciaTrabajador.objects.filter(trabajador__in=trabajadores)
    certificaciones = CertificacionTrabajador.objects.filter(trabajador__in=trabajadores)
    experiencias = ExperienciaTrabajador.objects.filter(trabajador__in=trabajadores)

    perfil_map = {p.user_id: p for p in perfiles}

    comp_map = {}
    for c in competencias:
        # clave por user.id para coincidir con la plantilla
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

    return render(request, "detalle_cuadrilla.html", {
        "cuadrilla": cuadrilla,
        "asignaciones": asignaciones,
        "perfil_map": perfil_map,
        "comp_map": comp_map,
        "cert_map": cert_map,
        "exp_map": exp_map,
        "can_manage": request.user.is_authenticated and request.user.groups.filter(name='JefeProyecto').exists(),
        "cuadrillas": Cuadrilla.objects.all(),
    })



@login_required
@user_passes_test(es_jefe)
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
@user_passes_test(es_jefe)
def disolver_cuadrilla(request, cuadrilla_id):
    """Eliminar una cuadrilla que no esté asociada a un proyecto.

    Crea notificaciones para los trabajadores que fueran asignados y para el líder.
    """
    cuad = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    # Solo permitir disolver si no está asociada a un proyecto
    if cuad.proyecto is not None:
        crear_notificacion(request.user, f"No se puede disolver la cuadrilla '{cuad.nombre}' porque está asociada a un proyecto.")
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
@user_passes_test(es_jefe)
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
    trabajador_user = asign.trabajador

    # Capturar datos antes de eliminar
    lider = cuadrilla.lider
    nombre_cuadrilla = cuadrilla.nombre

    # Eliminar la asignación
    asign.delete()

    # Ajustar estado del Trabajador: si no tiene override manual, poner 'disponible'
    try:
        trabajador_profile = getattr(trabajador_user, 'trabajador_profile', None)
        if trabajador_profile and not getattr(trabajador_profile, 'manual_override', False):
            # trabajador_profile here is actually Trabajador model on this project
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
