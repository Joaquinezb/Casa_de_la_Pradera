from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from personal.models import Asignacion
from .models import Conversation


@receiver(post_save, sender=Asignacion)
def gestionar_conversacion_cuadrilla(sender, instance, created, **kwargs):
    """Crear/actualizar conversación grupal de la cuadrilla automáticamente.

    - Si la cuadrilla tiene >= 2 asignaciones y no existe conversación grupal,
      se crea una y se agregan todos los participantes.
    - Si existe la conversación, se asegura que el trabajador esté agregado.
    - Si la cuadrilla queda con menos de 2 participantes, se elimina la conversación.
    """
    cuadrilla = instance.cuadrilla
    if not cuadrilla:
        return

    # Centralizar la lógica en el modelo Conversation
    Conversation.ensure_group_for_cuadrilla(cuadrilla, min_members=2)


@receiver(post_delete, sender=Asignacion)
def manejar_baja_trabajador(sender, instance, **kwargs):
    """Cuando se elimina una asignación, quitar al trabajador de la conversación
    de cuadrilla y eliminar la conversación si queda con menos de 2 participantes.
    """
    cuadrilla = instance.cuadrilla
    if not cuadrilla:
        return

    # Reconstruir/limpiar la conversación según el estado actual de asignaciones
    Conversation.ensure_group_for_cuadrilla(cuadrilla, min_members=2)
