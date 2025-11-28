"""
Utilidades y funciones helper para la aplicación personal.

Este módulo contiene funciones reutilizables que ayudan a mantener
el código DRY y facilitan el testing unitario.
"""

from django.contrib.auth.models import User
from .models import (
    Cuadrilla, Asignacion, Trabajador, TrabajadorPerfil,
    CertificacionTrabajador
)
from .constants import UserGroups, EstadosTrabajador


# ===================================================================
# UTILIDADES DE PERMISOS
def obtener_disponibilidad_trabajador(trabajador, perfil):
    """
    Obtiene la disponibilidad de un trabajador usando lógica unificada.
    
    Args:
        trabajador: Instancia de Trabajador (puede ser None)
        perfil: Instancia de TrabajadorPerfil (puede ser None)
        
    Returns:
        str: Estado de disponibilidad del trabajador o '—' si no disponible
    """
    if trabajador and getattr(trabajador, 'manual_override', False):
        return trabajador.estado
    elif perfil:
        return perfil.estado_efectivo
    else:
        return '—'


# ===================================================================
# UTILIDADES DE PERMISOS
# ===================================================================
# ===================================================================

def es_jefe_proyecto(user):
    """
    Verifica si el usuario pertenece al grupo de Jefes de Proyecto.
    
    Args:
        user: Instancia de User
        
    Returns:
        bool: True si el usuario es Jefe de Proyecto
    """
    return user.groups.filter(name=UserGroups.JEFE_PROYECTO).exists()


def es_lider_cuadrilla(user):
    """
    Verifica si el usuario pertenece al grupo de Líderes de Cuadrilla.
    
    Args:
        user: Instancia de User
        
    Returns:
        bool: True si el usuario es Líder de Cuadrilla
    """
    return user.groups.filter(name=UserGroups.LIDER_CUADRILLA).exists()


def puede_gestionar_cuadrilla(user, cuadrilla):
    """
    Verifica si un usuario tiene permisos para gestionar una cuadrilla.
    
    Args:
        user: Instancia de User
        cuadrilla: Instancia de Cuadrilla
        
    Returns:
        bool: True si el usuario puede gestionar la cuadrilla
    """
    if es_jefe_proyecto(user):
        # Jefe puede gestionar cuadrillas de sus proyectos o sin proyecto
        return (not cuadrilla.proyecto or 
                (cuadrilla.proyecto and cuadrilla.proyecto.jefe_id == user.id))
    
    if es_lider_cuadrilla(user):
        # Líder solo puede gestionar su propia cuadrilla
        return cuadrilla.lider_id == user.id
    
    return False


def puede_ver_cuadrilla(user, cuadrilla):
    """
    Verifica si un usuario tiene permisos para ver una cuadrilla.
    
    Args:
        user: Instancia de User
        cuadrilla: Instancia de Cuadrilla
        
    Returns:
        bool: True si el usuario puede ver la cuadrilla
    """
    if not user.is_authenticated:
        return False
    
    # Jefes de proyecto pueden ver todas las cuadrillas
    if es_jefe_proyecto(user):
        return True
    
    # Líderes pueden ver cuadrillas del mismo proyecto
    if es_lider_cuadrilla(user):
        if cuadrilla.proyecto:
            return Cuadrilla.objects.filter(
                proyecto=cuadrilla.proyecto, 
                lider=user
            ).exists()
        return False
    
    # Trabajadores solo pueden ver si están asignados a la cuadrilla
    return Asignacion.objects.filter(
        trabajador=user, 
        cuadrilla=cuadrilla
    ).exists()


# ===================================================================
# UTILIDADES DE TRABAJADORES
# ===================================================================

def obtener_disponibilidad_trabajador(trabajador):
    """
    Calcula la disponibilidad actual de un trabajador.
    
    Prioriza el estado manual si manual_override está activo,
    de lo contrario usa el estado efectivo del perfil.
    
    Args:
        trabajador: Instancia de Trabajador
        
    Returns:
        str: Estado de disponibilidad del trabajador
    """
    if getattr(trabajador, 'manual_override', False):
        return trabajador.estado
    
    if trabajador.user:
        perfil = TrabajadorPerfil.objects.filter(user=trabajador.user).first()
        if perfil:
            return perfil.estado_efectivo
    
    return EstadosTrabajador.DISPONIBLE


def esta_trabajador_ocupado(trabajador):
    """
    Verifica si un trabajador está ocupado (asignado a cuadrilla con proyecto).
    
    Args:
        trabajador: Instancia de Trabajador
        
    Returns:
        bool: True si el trabajador está ocupado
    """
    if getattr(trabajador, 'manual_override', False):
        return False
    
    if trabajador.user:
        return Asignacion.objects.filter(
            trabajador=trabajador.user,
            cuadrilla__proyecto__isnull=False
        ).exists()
    
    return False


def enriquecer_trabajador_con_info(trabajador):
    """
    Enriquece un objeto Trabajador con información adicional.
    
    Agrega atributos dinámicos:
    - ocupado: bool
    - estado_real: str
    - certificacion_lista: list
    - tiene_certificaciones: bool
    
    Args:
        trabajador: Instancia de Trabajador (modificada in-place)
    """
    # Determinar si está ocupado
    trabajador.ocupado = esta_trabajador_ocupado(trabajador)
    
    # Obtener estado real
    trabajador.estado_real = obtener_disponibilidad_trabajador(trabajador)
    
    # Obtener certificaciones
    certificaciones = CertificacionTrabajador.objects.filter(trabajador=trabajador)
    trabajador.certificacion_lista = [cert.nombre for cert in certificaciones]
    trabajador.tiene_certificaciones = certificaciones.exists()


def puede_asignarse_trabajador(trabajador):
    """
    Verifica si un trabajador puede ser asignado a una cuadrilla.
    
    Args:
        trabajador: Instancia de Trabajador
        
    Returns:
        bool: True si el trabajador puede ser asignado
    """
    estado_efectivo = obtener_disponibilidad_trabajador(trabajador)
    
    # No permitir asignación si está en estados especiales
    if estado_efectivo in EstadosTrabajador.ESTADOS_NO_ASIGNABLES:
        return False
    
    # No permitir si ya está asignado a una cuadrilla con proyecto
    if trabajador.user:
        ya_asignado = Asignacion.objects.filter(
            trabajador=trabajador.user,
            cuadrilla__proyecto__isnull=False
        ).exists()
        if ya_asignado:
            return False
    
    return True


# ===================================================================
# UTILIDADES DE LÍDERES
# ===================================================================

def preparar_lideres_disponibles(cuadrilla_actual=None):
    """
    Prepara una lista de líderes disponibles para asignar a una cuadrilla.
    
    Args:
        cuadrilla_actual: Instancia de Cuadrilla (opcional). Si se proporciona,
                         el líder actual será marcado como seleccionable aunque
                         esté ocupado.
    
    Returns:
        list: Lista de diccionarios con información de líderes
              [{'user': User, 'ocupado': bool, 'selectable': bool}, ...]
    """
    lideres_qs = User.objects.filter(
        groups__name=UserGroups.LIDER_CUADRILLA,
        is_active=True
    ).distinct()
    
    lideres_info = []
    
    for usuario in lideres_qs:
        # Verificar si el líder está ocupado
        query_ocupado = Cuadrilla.objects.filter(
            lider=usuario,
            proyecto__isnull=False
        )
        
        # Excluir la cuadrilla actual si se está editando
        if cuadrilla_actual:
            query_ocupado = query_ocupado.exclude(id=cuadrilla_actual.id)
        
        ocupado = query_ocupado.exists()
        
        # El líder actual de la cuadrilla siempre es seleccionable
        es_lider_actual = (cuadrilla_actual and 
                          cuadrilla_actual.lider and 
                          usuario.id == cuadrilla_actual.lider.id)
        
        selectable = not ocupado or es_lider_actual
        
        lideres_info.append({
            'user': usuario,
            'ocupado': ocupado and not es_lider_actual,
            'selectable': selectable,
        })
    
    return lideres_info


def validar_disponibilidad_lider(lider_id, cuadrilla_actual=None):
    """
    Valida si un líder está disponible para ser asignado a una cuadrilla.
    
    Args:
        lider_id: ID del usuario líder
        cuadrilla_actual: Instancia de Cuadrilla (opcional)
        
    Returns:
        tuple: (bool éxito, str mensaje_error o None)
    """
    if not lider_id or not str(lider_id).isdigit():
        return True, None
    
    # Verificar que pertenezca al grupo de líderes
    lider = User.objects.filter(
        id=lider_id,
        groups__name=UserGroups.LIDER_CUADRILLA
    ).first()
    
    if not lider:
        return False, "El usuario seleccionado no es un líder válido."
    
    # Verificar que no lidere otra cuadrilla activa
    query_conflicto = Cuadrilla.objects.filter(
        lider=lider,
        proyecto__isnull=False
    )
    
    if cuadrilla_actual:
        query_conflicto = query_conflicto.exclude(id=cuadrilla_actual.id)
    
    if query_conflicto.exists():
        from .constants import MensajesError
        return False, MensajesError.LIDER_YA_OCUPADO
    
    return True, None


# ===================================================================
# UTILIDADES DE ESTADO
# ===================================================================

def actualizar_estado_trabajador_al_quitar(trabajador_user):
    """
    Actualiza el estado de un trabajador cuando es quitado de una cuadrilla.
    
    Si el trabajador tenía override manual con estado especial (vacaciones, 
    licencia, etc), lo devuelve a modo automático y disponible.
    
    Args:
        trabajador_user: Instancia de User asociada al trabajador
    """
    try:
        trabajador_profile = getattr(trabajador_user, 'trabajador_profile', None)
        
        if not trabajador_profile:
            return
        
        # Si está en modo manual con estado especial, devolver a automático
        if (getattr(trabajador_profile, 'manual_override', False) and 
            trabajador_profile.estado in EstadosTrabajador.ESTADOS_ESPECIALES):
            trabajador_profile.manual_override = False
            trabajador_profile.estado = EstadosTrabajador.DISPONIBLE
            trabajador_profile.save()
        
        # Si no tiene override manual, poner disponible
        elif not getattr(trabajador_profile, 'manual_override', False):
            trabajador_profile.estado = EstadosTrabajador.DISPONIBLE
            trabajador_profile.save()
            
    except Exception as e:
        # Log del error pero no interrumpir el flujo
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Error actualizando estado de trabajador {trabajador_user.id}: {e}"
        )


# ===================================================================
# UTILIDADES DE CONTEXTO
# ===================================================================

def preparar_contexto_especialidades():
    """
    Obtiene la lista de especialidades únicas de trabajadores activos.
    
    Returns:
        QuerySet: Lista de especialidades únicas
    """
    return (
        Trabajador.objects
        .exclude(especialidad__isnull=True)
        .exclude(especialidad__exact="")
        .values_list("especialidad", flat=True)
        .distinct()
    )


def preparar_contexto_certificaciones():
    """
    Obtiene la lista de certificaciones únicas.
    
    Returns:
        QuerySet: Lista de nombres de certificaciones únicas
    """
    return CertificacionTrabajador.objects.values_list("nombre", flat=True).distinct()
