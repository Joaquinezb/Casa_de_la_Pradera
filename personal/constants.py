"""
Constantes para la aplicación personal.

Este módulo centraliza todos los valores constantes utilizados en la aplicación,
siguiendo el principio DRY (Don't Repeat Yourself) y facilitando el mantenimiento.
"""

# ===================================================================
# GRUPOS DE USUARIOS
# ===================================================================
class UserGroups:
    """Nombres de grupos de usuarios en el sistema."""
    JEFE_PROYECTO = 'JefeProyecto'
    LIDER_CUADRILLA = 'LiderCuadrilla'
    TRABAJADOR = 'Trabajador'


# ===================================================================
# ESTADOS DE TRABAJADOR
# ===================================================================
class EstadosTrabajador:
    """Estados posibles para un trabajador."""
    DISPONIBLE = 'disponible'
    ASIGNADO = 'asignado'
    VACACIONES = 'vacaciones'
    LICENCIA = 'licencia'
    INACTIVO = 'inactivo'
    NO_DISPONIBLE = 'no_disponible'
    
    # Estados que impiden asignación a cuadrilla
    ESTADOS_NO_ASIGNABLES = [VACACIONES, LICENCIA, NO_DISPONIBLE]
    
    # Estados que requieren override manual para ser removidos
    ESTADOS_ESPECIALES = [VACACIONES, LICENCIA, NO_DISPONIBLE]


# ===================================================================
# TIPOS DE TRABAJADOR
# ===================================================================
class TiposTrabajador:
    """Tipos de trabajador en el sistema."""
    TRABAJADOR = 'trabajador'
    LIDER = 'lider'
    JEFE = 'jefe'


# ===================================================================
# ESTADOS DE SOLICITUD
# ===================================================================
class EstadosSolicitud:
    """Estados para solicitudes de trabajadores."""
    PENDIENTE = 'pending'
    ACEPTADA = 'accepted'
    RECHAZADA = 'rejected'


# ===================================================================
# MENSAJES DEL SISTEMA
# ===================================================================
class MensajesNotificacion:
    """Plantillas de mensajes para notificaciones."""
    
    @staticmethod
    def asignado_cuadrilla(nombre_cuadrilla, nombre_proyecto=None, nombre_rol=None):
        """Mensaje cuando un trabajador es asignado a una cuadrilla."""
        msg = f"Has sido asignado a la cuadrilla '{nombre_cuadrilla}'"
        if nombre_proyecto:
            msg += f" en el proyecto '{nombre_proyecto}'."
        else:
            msg += "."
        if nombre_rol:
            msg += f" Rol: {nombre_rol}."
        return msg
    
    @staticmethod
    def lider_nueva_cuadrilla(nombre_cuadrilla):
        """Mensaje cuando un usuario se convierte en líder de cuadrilla."""
        return f"Eres líder de la nueva cuadrilla '{nombre_cuadrilla}'."
    
    @staticmethod
    def removido_liderazgo(nombre_cuadrilla):
        """Mensaje cuando un usuario deja de ser líder de cuadrilla."""
        return f"Ya no eres líder de la cuadrilla '{nombre_cuadrilla}'."
    
    @staticmethod
    def asignado_liderazgo(nombre_cuadrilla):
        """Mensaje cuando un usuario es asignado como líder."""
        return f"Has sido asignado como líder de la cuadrilla '{nombre_cuadrilla}'."
    
    @staticmethod
    def cambio_proyecto_cuadrilla(nombre_cuadrilla, nombre_proyecto=None):
        """Mensaje cuando una cuadrilla cambia de proyecto."""
        msg = f"La cuadrilla '{nombre_cuadrilla}' ha cambiado de proyecto."
        if nombre_proyecto:
            msg += f" Nuevo proyecto: {nombre_proyecto}."
        return msg
    
    @staticmethod
    def agregado_cuadrilla(nombre_cuadrilla, nombre_rol=None):
        """Mensaje cuando un trabajador es agregado a una cuadrilla."""
        msg = f"Has sido agregado a la cuadrilla '{nombre_cuadrilla}'."
        if nombre_rol:
            msg += f" Rol: {nombre_rol}."
        return msg
    
    @staticmethod
    def removido_cuadrilla(nombre_cuadrilla):
        """Mensaje cuando un trabajador es removido de una cuadrilla."""
        return f"Has sido removido de la cuadrilla '{nombre_cuadrilla}'."
    
    @staticmethod
    def cambio_rol(nombre_cuadrilla, nombre_rol=None):
        """Mensaje cuando cambia el rol de un trabajador en una cuadrilla."""
        if nombre_rol:
            return f"Tu rol en la cuadrilla '{nombre_cuadrilla}' ahora es '{nombre_rol}'."
        return f"Tu rol en la cuadrilla '{nombre_cuadrilla}' ha sido removido."
    
    @staticmethod
    def movido_cuadrilla(nombre_cuadrilla_origen, nombre_cuadrilla_destino):
        """Mensaje cuando un trabajador es trasladado entre cuadrillas."""
        return f"Has sido trasladado de la cuadrilla '{nombre_cuadrilla_origen}' a '{nombre_cuadrilla_destino}'."
    
    @staticmethod
    def trabajador_removido_cuadrilla(nombre_completo, nombre_cuadrilla):
        """Mensaje para líder cuando un trabajador es removido de su cuadrilla."""
        return f"El trabajador {nombre_completo} ha sido removido de tu cuadrilla '{nombre_cuadrilla}'."
    
    @staticmethod
    def trabajador_agregado_cuadrilla(nombre_completo, nombre_cuadrilla):
        """Mensaje para líder cuando un trabajador es agregado a su cuadrilla."""
        return f"El trabajador {nombre_completo} ha sido asignado a tu cuadrilla '{nombre_cuadrilla}'."
    
    @staticmethod
    def cuadrilla_disuelta(nombre_cuadrilla):
        """Mensaje cuando una cuadrilla es disuelta."""
        return f"La cuadrilla '{nombre_cuadrilla}' ha sido disuelta. Ya no perteneces a esa cuadrilla."
    
    @staticmethod
    def cuadrilla_disuelta_lider(nombre_cuadrilla):
        """Mensaje cuando se disuelve una cuadrilla que el usuario lideraba."""
        return f"La cuadrilla '{nombre_cuadrilla}' que liderabas ha sido disuelta."
    
    @staticmethod
    def no_disolver_cuadrilla_con_proyecto(nombre_cuadrilla):
        """Mensaje cuando se intenta disolver una cuadrilla con proyecto."""
        return f"No se puede disolver la cuadrilla '{nombre_cuadrilla}' porque está asociada a un proyecto."
    
    @staticmethod
    def removido_de_cuadrilla(nombre_cuadrilla):
        """Mensaje cuando un trabajador es removido de una cuadrilla."""
        return f"Has sido removido de la cuadrilla '{nombre_cuadrilla}'. Ahora estás sin cuadrilla."
    
    @staticmethod
    def estado_laboral_cambiado(nuevo_estado):
        """Mensaje cuando cambia el estado laboral de un trabajador."""
        return f"Tu estado laboral ha cambiado a: {nuevo_estado}."
    
    @staticmethod
    def sin_permiso_editar_cuadrilla():
        """Mensaje cuando un usuario no tiene permiso para editar una cuadrilla."""
        return 'No tienes permiso para editar esta cuadrilla.'
    
    @staticmethod
    def solo_editar_propia_cuadrilla():
        """Mensaje cuando un líder intenta editar una cuadrilla que no es suya."""
        return 'Solo puedes editar tu propia cuadrilla.'
    
    @staticmethod
    def sin_permiso_mover_trabajador():
        """Mensaje cuando un usuario no tiene permiso para mover trabajadores."""
        return 'No tienes permiso para mover este trabajador entre cuadrillas.'
    
    @staticmethod
    def sin_permiso_disolver_cuadrilla():
        """Mensaje cuando un usuario no tiene permiso para disolver una cuadrilla."""
        return 'No tienes permiso para disolver esta cuadrilla.'
    
    @staticmethod
    def cuadrilla_con_proyecto_no_disolvible(nombre_cuadrilla):
        """Mensaje cuando se intenta disolver una cuadrilla con proyecto activo."""
        return f"No se puede disolver la cuadrilla '{nombre_cuadrilla}' porque está asociada a un proyecto."
    
    @staticmethod
    def sin_permiso_quitar_trabajador():
        """Mensaje cuando un usuario no tiene permiso para quitar trabajadores."""
        return 'No tienes permiso para quitar a este trabajador.'


# ===================================================================
# MENSAJES DE ERROR
# ===================================================================
class MensajesError:
    """Mensajes de error del sistema."""
    LIDER_YA_OCUPADO = 'El usuario seleccionado ya lidera otra cuadrilla asociada a un proyecto activo.'


# ===================================================================
# CONFIGURACIÓN DE CUADRILLAS
# ===================================================================
class ConfigCuadrillas:
    """Configuración relacionada con cuadrillas."""
    MINIMO_MIEMBROS_CONVERSACION_GRUPAL = 2
