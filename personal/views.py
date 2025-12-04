from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth import update_session_auth_hash
from django.db import transaction

from proyectos.models import Proyecto
from .models import (
    Cuadrilla, Asignacion, Rol, Trabajador, TrabajadorPerfil,
    CompetenciaTrabajador, CertificacionTrabajador, ExperienciaTrabajador,
    Notificacion,
)
from .utils_notificaciones import crear_notificacion
from .constants import (
    UserGroups, EstadosTrabajador, TiposTrabajador, MensajesNotificacion, MensajesError
)
from .utils import (
    es_jefe_proyecto, es_lider_cuadrilla, puede_gestionar_cuadrilla,
    puede_ver_cuadrilla, enriquecer_trabajador_con_info,
    puede_asignarse_trabajador, preparar_lideres_disponibles,
    validar_disponibilidad_lider, actualizar_estado_trabajador_al_quitar,
    preparar_contexto_especialidades, preparar_contexto_certificaciones,
    obtener_disponibilidad_trabajador
)
from comunicacion.models import (
    Conversation, Message, WorkerRequest, IncidentNotice
)
from comunicacion.models import archive_conversation


# ===================================================================
# FUNCIONES HELPER PRIVADAS
# ===================================================================

def _procesar_asignacion_trabajadores(request, cuadrilla, trabajadores_ids):
    """
    Procesa la asignación de trabajadores a una cuadrilla.
    
    Args:
        request: HttpRequest
        cuadrilla: Instancia de Cuadrilla
        trabajadores_ids: Lista de IDs de usuarios a asignar
        
    Returns:
        list: Lista de tuplas (user, rol) de trabajadores asignados exitosamente
    """
    trabajadores_asignados = []
    
    for trabajador_user_id in trabajadores_ids:
        trabajador = Trabajador.objects.filter(user__id=trabajador_user_id).first()
        
        if not trabajador:
            continue
        
        # Verificar si puede ser asignado
        if not puede_asignarse_trabajador(trabajador):
            continue
        
        # Crear usuario si no existe
        if not trabajador.user:
            user = trabajador.crear_usuario()
            Trabajador.objects.filter(pk=trabajador.pk).update(user_id=user.id)
            trabajador.user = user
        
        # Obtener o crear rol
        rol_custom = (request.POST.get(f"roles_custom_{trabajador_user_id}") or '').strip()
        if rol_custom:
            rol, _ = Rol.objects.get_or_create(nombre=rol_custom)
        else:
            rol_id = request.POST.get(f"roles_{trabajador_user_id}")
            rol = Rol.objects.filter(id=rol_id).first() if rol_id and str(rol_id).isdigit() else None
        
        # Crear asignación
        Asignacion.objects.create(
            trabajador=trabajador.user,
            cuadrilla=cuadrilla,
            rol=rol
        )
        
        trabajadores_asignados.append((trabajador.user, rol))
    
    return trabajadores_asignados


def _enviar_notificaciones_creacion_cuadrilla(cuadrilla, trabajadores_asignados):
    """
    Envía notificaciones al crear una cuadrilla.
    
    Args:
        cuadrilla: Instancia de Cuadrilla creada
        trabajadores_asignados: Lista de tuplas (user, rol)
    """
    # Notificar a trabajadores asignados
    for user, rol in trabajadores_asignados:
        mensaje = MensajesNotificacion.asignado_cuadrilla(
            nombre_cuadrilla=cuadrilla.nombre,
            nombre_proyecto=cuadrilla.proyecto.nombre if cuadrilla.proyecto else None,
            nombre_rol=rol.nombre if rol else None
        )
        crear_notificacion(user, mensaje)
    
    # Notificar al líder
    if cuadrilla.lider:
        mensaje = MensajesNotificacion.lider_nueva_cuadrilla(cuadrilla.nombre)
        crear_notificacion(cuadrilla.lider, mensaje)


def _procesar_edicion_asignaciones(request, cuadrilla, seleccionados, asignaciones_actuales):
    """
    Procesa la edición de asignaciones de trabajadores a una cuadrilla.
    
    Args:
        request: HttpRequest
        cuadrilla: Instancia de Cuadrilla
        seleccionados: Set de IDs de trabajadores seleccionados
        asignaciones_actuales: Dict de asignaciones actuales {user_id: Asignacion}
        
    Returns:
        tuple: (agregados, cambios_rol)
            - agregados: Lista de tuplas (user, rol)
            - cambios_rol: Lista de tuplas (user, cuadrilla, rol)
    """
    agregados = []
    cambios_rol = []
    restantes = asignaciones_actuales.copy()
    
    for trabajador_user_id in seleccionados:
        trabajador_obj = Trabajador.objects.filter(user__id=trabajador_user_id).first()
        
        if not trabajador_obj:
            continue
        
        # Validar si puede ser asignado
        if not puede_asignarse_trabajador(trabajador_obj):
            continue
        
        # Crear usuario si no existe
        if not trabajador_obj.user:
            user = trabajador_obj.crear_usuario()
            Trabajador.objects.filter(pk=trabajador_obj.pk).update(user_id=user.id)
            trabajador_obj.user = user
        
        user = trabajador_obj.user
        clave = str(user.id)
        
        # Obtener o crear rol
        rol_custom = (request.POST.get(f"roles_custom_{trabajador_user_id}") or '').strip()
        if rol_custom:
            rol, _ = Rol.objects.get_or_create(nombre=rol_custom)
        else:
            rol_id = request.POST.get(f"roles_{trabajador_user_id}")
            rol = Rol.objects.filter(id=rol_id).first() if rol_id and str(rol_id).isdigit() else None
        
        # Actualizar o crear asignación
        if clave in restantes:
            # Trabajador ya estaba asignado - actualizar rol si cambió
            asignacion = restantes.pop(clave)
            rol_anterior = asignacion.rol
            
            if rol_anterior != rol:
                cambios_rol.append((user, cuadrilla, rol))
            
            asignacion.rol = rol
            asignacion.save()
        else:
            # Nuevo trabajador - crear asignación
            Asignacion.objects.create(
                trabajador=user,
                cuadrilla=cuadrilla,
                rol=rol
            )
            agregados.append((user, rol))
    
    return agregados, cambios_rol


def _enviar_notificaciones_edicion_cuadrilla(cuadrilla, lider_anterior, 
                                             proyecto_anterior, agregados, cambios_rol):
    """
    Envía notificaciones al editar una cuadrilla.
    
    Args:
        cuadrilla: Instancia de Cuadrilla editada
        lider_anterior: User que era líder anteriormente (o None)
        proyecto_anterior: Proyecto anterior (o None)
        agregados: Lista de tuplas (user, rol) de trabajadores agregados
        cambios_rol: Lista de tuplas (user, cuadrilla, rol) con cambios de rol
    """
    # Notificar cambio de liderazgo
    if lider_anterior != cuadrilla.lider:
        if lider_anterior:
            mensaje = MensajesNotificacion.removido_liderazgo(cuadrilla.nombre)
            crear_notificacion(lider_anterior, mensaje)
        
        if cuadrilla.lider:
            mensaje = MensajesNotificacion.asignado_liderazgo(cuadrilla.nombre)
            crear_notificacion(cuadrilla.lider, mensaje)
    
    # Notificar cambio de proyecto
    if proyecto_anterior != cuadrilla.proyecto:
        for asignacion in Asignacion.objects.filter(cuadrilla=cuadrilla):
            mensaje = MensajesNotificacion.cambio_proyecto_cuadrilla(
                nombre_cuadrilla=cuadrilla.nombre,
                nombre_proyecto=cuadrilla.proyecto.nombre if cuadrilla.proyecto else None
            )
            crear_notificacion(asignacion.trabajador, mensaje)
    
    # Notificar trabajadores agregados
    for user, rol in agregados:
        mensaje = MensajesNotificacion.agregado_cuadrilla(
            nombre_cuadrilla=cuadrilla.nombre,
            nombre_rol=rol.nombre if rol else None
        )
        crear_notificacion(user, mensaje)
    
    # Notificar cambios de rol
    for user, cuad, rol in cambios_rol:
        mensaje = MensajesNotificacion.cambio_rol(
            nombre_cuadrilla=cuad.nombre,
            nombre_rol=rol.nombre if rol else None
        )
        crear_notificacion(user, mensaje)


# ===================================================================
# VISTAS
# ===================================================================


# =====================================================
# 1. CREAR CUADRILLA
# =====================================================
@login_required
@user_passes_test(es_jefe_proyecto)
def crear_cuadrilla(request):

    # Obtener proyectos activos del jefe
    proyectos = Proyecto.objects.filter(jefe=request.user, activo=True)

    # Obtener trabajadores activos (excluir líderes y jefes)
    trabajadores = (
        Trabajador.objects
        .filter(activo=True, tipo_trabajador=TiposTrabajador.TRABAJADOR)
        .select_related("user")
        .prefetch_related("certificaciones_trabajador", "user__perfil_trabajador")
    )

    roles = Rol.objects.all()

    # Preparar lista de líderes disponibles
    posibles_lideres = preparar_lideres_disponibles()

    # Enriquecer trabajadores con información adicional
    for trabajador in trabajadores:
        enriquecer_trabajador_con_info(trabajador)

    # Obtener especialidades y certificaciones únicas
    especialidades = preparar_contexto_especialidades()
    certificaciones = preparar_contexto_certificaciones()

    if request.method == "POST":
        nombre = request.POST.get("nombre")
        proyecto_id = request.POST.get("proyecto")
        lider_id = request.POST.get("lider")
        seleccionados = request.POST.getlist("trabajadores")

        # Obtener proyecto si se especificó
        proyecto = None
        if proyecto_id and proyecto_id.isdigit():
            proyecto = Proyecto.objects.filter(
                id=proyecto_id,
                jefe=request.user,
                activo=True
            ).first()

        # Validar líder
        lider_usuario = None
        if lider_id and lider_id.isdigit():
            lider_usuario = User.objects.filter(
                id=lider_id,
                groups__name=UserGroups.LIDER_CUADRILLA
            ).first()
            
            # Validar disponibilidad del líder
            es_valido, mensaje_error = validar_disponibilidad_lider(lider_id)
            if not es_valido:
                return render(request, 'cuadrilla_form.html', {
                    'proyectos': proyectos,
                    'trabajadores': trabajadores,
                    'roles': roles,
                    'especialidades': especialidades,
                    'certificaciones': certificaciones,
                    'posibles_lideres': posibles_lideres,
                    'errors': [mensaje_error],
                    'nombre': nombre,
                })

        # Crear cuadrilla
        with transaction.atomic():
            cuadrilla = Cuadrilla.objects.create(
                nombre=nombre,
                proyecto=proyecto,
                lider=lider_usuario
            )

            # Procesar asignación de trabajadores
            trabajadores_asignados = _procesar_asignacion_trabajadores(
                request, cuadrilla, seleccionados
            )

            # Enviar notificaciones
            _enviar_notificaciones_creacion_cuadrilla(
                cuadrilla, trabajadores_asignados
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
# 2. EDITAR CUADRILLA
# =====================================================
@login_required
def editar_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    # Verificar permisos
    user = request.user
    if es_jefe_proyecto(user):
        if cuadrilla.proyecto and cuadrilla.proyecto.jefe_id != user.id:
            crear_notificacion(user, MensajesNotificacion.sin_permiso_editar_cuadrilla())
            return redirect('proyectos:panel')
    elif es_lider_cuadrilla(user):
        if cuadrilla.lider_id != user.id:
            crear_notificacion(user, MensajesNotificacion.solo_editar_propia_cuadrilla())
            return redirect('proyectos:panel')
    else:
        return redirect('proyectos:panel')

    # Preparar contexto
    trabajadores = Trabajador.objects.filter(
        activo=True,
        tipo_trabajador=TiposTrabajador.TRABAJADOR
    ).select_related("user")
    
    roles = Rol.objects.all()
    posibles_lideres = preparar_lideres_disponibles(cuadrilla_actual=cuadrilla)
    
    # Proyectos permitidos según rol
    if es_jefe_proyecto(user):
        proyectos = Proyecto.objects.filter(jefe=request.user, activo=True)
    else:
        proyectos = (Proyecto.objects.filter(id=cuadrilla.proyecto.id) 
                    if cuadrilla.proyecto else Proyecto.objects.none())

    # Obtener asignaciones actuales
    asignaciones_actuales = {
        str(a.trabajador.id): a 
        for a in Asignacion.objects.filter(cuadrilla=cuadrilla)
    }

    # Enriquecer trabajadores
    for trabajador in trabajadores:
        trabajador.asignacion = asignaciones_actuales.get(
            str(trabajador.user.id)
        ) if trabajador.user else None
        
        enriquecer_trabajador_con_info(trabajador)
        
        # Permisos para mostrar botón 'Quitar'
        trabajador.can_remove = puede_gestionar_cuadrilla(user, cuadrilla)

    if request.method == "POST":
        lider_anterior = cuadrilla.lider
        proyecto_anterior = cuadrilla.proyecto

        cuadrilla.nombre = request.POST.get("nombre")

        # Procesar cambio de líder
        lider_id = request.POST.get("lider")
        cuadrilla.lider = None
        
        if lider_id and lider_id.isdigit():
            posible_lider = User.objects.filter(
                id=lider_id,
                groups__name=UserGroups.LIDER_CUADRILLA
            ).first()

            # Validar disponibilidad
            if posible_lider:
                es_valido, mensaje_error = validar_disponibilidad_lider(
                    lider_id,
                    cuadrilla_actual=cuadrilla
                )
                if not es_valido:
                    return render(request, 'cuadrilla_editar.html', {
                        'cuadrilla': cuadrilla,
                        'trabajadores': trabajadores,
                        'roles': roles,
                        'proyectos': proyectos,
                        'posibles_lideres': posibles_lideres,
                        'errors': [mensaje_error],
                    })
            cuadrilla.lider = posible_lider

        # Procesar cambio de proyecto
        proyecto_id = request.POST.get("proyecto")
        cuadrilla.proyecto = Proyecto.objects.filter(
            id=proyecto_id,
            jefe=request.user,
            activo=True
        ).first() if proyecto_id and proyecto_id.isdigit() else None

        cuadrilla.save()

        # Procesar asignaciones
        raw_seleccionados = request.POST.getlist("trabajadores")
        if raw_seleccionados:
            agregados, cambios_rol = _procesar_edicion_asignaciones(
                request, cuadrilla, set(raw_seleccionados), asignaciones_actuales
            )
            
            # Enviar notificaciones
            _enviar_notificaciones_edicion_cuadrilla(
                cuadrilla, lider_anterior, proyecto_anterior, agregados, cambios_rol
            )

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
# =====================================================
# 3. DETALLE CUADRILLA
# =====================================================
def detalle_cuadrilla(request, cuadrilla_id):
    """Vista de detalle de una cuadrilla con trabajadores asignados."""
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    # Verificar permisos
    if not puede_ver_cuadrilla(request.user, cuadrilla):
        return redirect('proyectos:panel')

    # Optimizar queries con select_related y prefetch_related
    asignaciones = (Asignacion.objects
                   .filter(cuadrilla=cuadrilla)
                   .select_related('trabajador', 'rol')
                   .order_by('trabajador__username'))

    users = [a.trabajador for a in asignaciones]
    
    # Prefetch relacionados
    trabajadores = (Trabajador.objects
                   .filter(user__in=users)
                   .select_related('user'))
    
    perfiles = (TrabajadorPerfil.objects
               .filter(user__in=users)
               .select_related('user'))
    
    perfil_map = {p.user_id: p for p in perfiles}
    trabajador_map = {t.user_id: t for t in trabajadores}

    # Construir lista enriquecida
    trabajadores_detalle = []
    for asignacion in asignaciones:
        user = asignacion.trabajador
        trabajador = trabajador_map.get(user.id)
        perfil = perfil_map.get(user.id)
        
        disponibilidad = obtener_disponibilidad_trabajador(trabajador, perfil)
        especialidad = trabajador.especialidad if trabajador and trabajador.especialidad else '—'
        
        trabajadores_detalle.append({
            'user': user,
            'rol': asignacion.rol,
            'disponibilidad': disponibilidad,
            'especialidad': especialidad,
            'asignacion': asignacion,
        })

    # Prefetch competencias, certificaciones y experiencias
    competencias = (CompetenciaTrabajador.objects
                   .filter(trabajador__in=trabajadores)
                   .select_related('trabajador', 'trabajador__user'))
    
    certificaciones = (CertificacionTrabajador.objects
                      .filter(trabajador__in=trabajadores)
                      .select_related('trabajador', 'trabajador__user'))
    
    experiencias = (ExperienciaTrabajador.objects
                   .filter(trabajador__in=trabajadores)
                   .select_related('trabajador', 'trabajador__user'))

    # Mapas para template
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

    can_manage = puede_gestionar_cuadrilla(request.user, cuadrilla)

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
# =====================================================
# 4. MOVER TRABAJADOR
# =====================================================
@login_required
def mover_trabajador(request):
    """Mueve un trabajador de una cuadrilla a otra."""
    if request.method != 'POST':
        return redirect('proyectos:panel')

    asignacion_id = request.POST.get('asignacion_id')
    nueva_id = request.POST.get('nueva_cuadrilla_id')

    asign = Asignacion.objects.filter(id=asignacion_id).first()
    nueva = Cuadrilla.objects.filter(id=nueva_id).first()

    if not asign or not nueva:
        return redirect('proyectos:panel')

    antigua = asign.cuadrilla
    trabajador_user = asign.trabajador

    # Verificar permisos
    user = request.user
    permitido = False
    
    if es_jefe_proyecto(user):
        # Permitir si maneja proyecto origen o destino
        if ((antigua.proyecto and antigua.proyecto.jefe_id == user.id) or
            (nueva.proyecto and nueva.proyecto.jefe_id == user.id)):
            permitido = True
    elif es_lider_cuadrilla(user):
        # Permitir si lidera la cuadrilla origen
        if antigua.lider_id == user.id:
            permitido = True

    if not permitido:
        crear_notificacion(user, MensajesNotificacion.sin_permiso_mover_trabajador())
        return redirect('personal:detalle_cuadrilla', antigua.id)

    # Realizar movimiento
    asign.cuadrilla = nueva
    asign.save()

    # Notificaciones
    mensaje = MensajesNotificacion.movido_cuadrilla(antigua.nombre, nueva.nombre)
    crear_notificacion(trabajador_user, mensaje)

    # Notificar líderes si aplicable
    if antigua.lider and antigua.lider != trabajador_user:
        mensaje_lider = MensajesNotificacion.trabajador_removido_cuadrilla(
            trabajador_user.get_full_name(), antigua.nombre
        )
        crear_notificacion(antigua.lider, mensaje_lider)
    
    if nueva.lider and nueva.lider != trabajador_user:
        mensaje_lider = MensajesNotificacion.trabajador_agregado_cuadrilla(
            trabajador_user.get_full_name(), nueva.nombre
        )
        crear_notificacion(nueva.lider, mensaje_lider)

    return redirect('personal:detalle_cuadrilla', antigua.id)



# =====================================================
# 5. DISOLVER CUADRILLA
# =====================================================
@login_required
def disolver_cuadrilla(request, cuadrilla_id):
    """Disuelve una cuadrilla sin proyecto asociado."""
    cuad = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    # Validar que no tenga proyecto
    if cuad.proyecto is not None:
        crear_notificacion(
            request.user,
            MensajesNotificacion.no_disolver_cuadrilla_con_proyecto(cuad.nombre)
        )
        return redirect('personal:detalle_cuadrilla', cuad.id)

    # Verificar permisos: cualquier Jefe puede disolver si no hay proyecto;
    # o el Líder asignado puede disolver su propia cuadrilla.
    user = request.user
    permitido = False
    if es_jefe_proyecto(user) and cuad.proyecto is None:
        permitido = True
    elif es_lider_cuadrilla(user) and cuad.lider_id == user.id:
        permitido = True

    if not permitido:
        crear_notificacion(user, MensajesNotificacion.sin_permiso_disolver_cuadrilla())
        return redirect('personal:detalle_cuadrilla', cuad.id)

    # Archivar conversación antes de eliminar
    nombre_cuadrilla = cuad.nombre
    try:
        conversaciones = Conversation.objects.filter(cuadrilla=cuad)
        for conv in conversaciones:
            print(f"Archivando conversación {conv.id} de cuadrilla {nombre_cuadrilla}")
            archive_conversation(
                conv,
                archived_by=request.user,
                reason=f"Disolución de cuadrilla '{nombre_cuadrilla}'"
            )
            print(f"Conversación {conv.id} archivada exitosamente")
    except Exception as e:
        print(f"Error archivando conversación: {e}")
        import traceback
        traceback.print_exc()

    # Capturar datos antes de eliminar
    asignaciones = list(Asignacion.objects.filter(cuadrilla=cuad))
    lider = cuad.lider

    # Eliminar cuadrilla
    cuad.delete()

    # Notificaciones
    for a in asignaciones:
        crear_notificacion(
            a.trabajador,
            MensajesNotificacion.cuadrilla_disuelta(nombre_cuadrilla)
        )

    if lider:
        crear_notificacion(
            lider,
            MensajesNotificacion.cuadrilla_disuelta_lider(nombre_cuadrilla)
        )

    return redirect('proyectos:panel')



# =====================================================
# 6. QUITAR TRABAJADOR
# =====================================================
@login_required
def quitar_trabajador(request):
    """Remueve un trabajador de una cuadrilla."""
    if request.method != 'POST':
        return redirect('proyectos:panel')

    asignacion_id = request.POST.get('asignacion_id')
    asign = Asignacion.objects.filter(id=asignacion_id).first()
    
    if not asign:
        return redirect('proyectos:panel')

    cuadrilla = asign.cuadrilla
    trabajador_user = asign.trabajador

    # Verificar permisos
    user = request.user
    permitido = False
    
    if es_jefe_proyecto(user):
        if not cuadrilla.proyecto or cuadrilla.proyecto.jefe_id == user.id:
            permitido = True
    elif es_lider_cuadrilla(user):
        permitido = cuadrilla.lider_id == user.id

    if not permitido:
        crear_notificacion(user, MensajesNotificacion.sin_permiso_quitar_trabajador())
        return redirect('personal:detalle_cuadrilla', cuadrilla.id)

    # Eliminar asignación
    asign.delete()

    # Actualizar estado del trabajador
    actualizar_estado_trabajador_al_quitar(trabajador_user)

    # Notificaciones
    crear_notificacion(
        trabajador_user,
        MensajesNotificacion.removido_de_cuadrilla(cuadrilla.nombre)
    )

    if cuadrilla.lider and cuadrilla.lider != trabajador_user:
        mensaje_lider = MensajesNotificacion.trabajador_removido_cuadrilla(
            trabajador_user.get_full_name(), cuadrilla.nombre
        )
        crear_notificacion(cuadrilla.lider, mensaje_lider)

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
@login_required
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
            
            # IMPORTANTE: Limpiar estado_manual en perfil para evitar persistencia incorrecta
            if perfil:
                perfil.estado_manual = 'disponible'
                perfil.save()
            
            return redirect("personal:detalle_trabajador", trabajador.id)

        if nuevo_estado in [
            EstadosTrabajador.DISPONIBLE,
            EstadosTrabajador.ASIGNADO,
            EstadosTrabajador.VACACIONES,
            EstadosTrabajador.LICENCIA,
            EstadosTrabajador.INACTIVO,
            EstadosTrabajador.NO_DISPONIBLE
        ]:
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
                    MensajesNotificacion.estado_laboral_cambiado(nuevo_estado)
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
# 8. MI CUADRILLA (VISTA TRABAJADOR)
# =====================================================
@login_required
def mi_cuadrilla(request):
    """
    Vista para trabajadores: muestra solo su cuadrilla actual.
    No permite ediciones, solo consulta.
    """
    user = request.user
    
    # Buscar asignación del trabajador
    asignacion = Asignacion.objects.filter(trabajador=user).select_related('cuadrilla', 'cuadrilla__proyecto', 'rol').first()
    
    if not asignacion:
        # Trabajador no tiene cuadrilla asignada
        return render(request, 'personal/mi_cuadrilla.html', {
            'sin_cuadrilla': True,
        })
    
    cuadrilla = asignacion.cuadrilla
    proyecto = cuadrilla.proyecto
    
    # Obtener todos los miembros de la cuadrilla
    asignaciones = Asignacion.objects.filter(cuadrilla=cuadrilla).select_related('trabajador', 'rol').order_by('trabajador__username')
    
    miembros = []
    for asig in asignaciones:
        trabajador_obj = Trabajador.objects.filter(user=asig.trabajador).first()
        miembros.append({
            'user': asig.trabajador,
            'rol': asig.rol,
            'trabajador': trabajador_obj,
            'es_lider': cuadrilla.lider == asig.trabajador,
        })
    
    return render(request, 'personal/mi_cuadrilla.html', {
        'cuadrilla': cuadrilla,
        'proyecto': proyecto,
        'miembros': miembros,
        'mi_rol': asignacion.rol,
        'sin_cuadrilla': False,
    })


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
