from .models import Notificacion

def crear_notificacion(user, mensaje: str):
    """
    Crea una notificación interna para un usuario.
    No deberia hacer nada si user es None.
    """
    if not user:
        return
    Notificacion.objects.create(user=user, mensaje=mensaje)
