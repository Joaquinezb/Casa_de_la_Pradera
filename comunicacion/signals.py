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

    # Obtener todas las asignaciones actuales de la cuadrilla
    miembros = Asignacion.objects.filter(cuadrilla=cuadrilla)
    total = miembros.count()

    conv = Conversation.objects.filter(is_group=True, cuadrilla=cuadrilla).first()

    if total >= 2:
        # Crear conversación grupal si no existe
        if not conv:
            conv = Conversation.objects.create(
                is_group=True,
                cuadrilla=cuadrilla,
                nombre=f"Cuadrilla {cuadrilla.nombre}"
            )
        # Asegurar que todos los miembros sean participantes
        for a in miembros:
            if a.trabajador:
                conv.participants.add(a.trabajador)
    else:
        # Si hay menos de 2 miembros y existe conversación, eliminarla
        if conv:
            # Quitar al trabajador actual
            if instance.trabajador:
                conv.participants.remove(instance.trabajador)
            # Si quedan menos de 2 participantes, eliminar la conversación
            if conv.participants.count() < 2:
                conv.delete()


@receiver(post_delete, sender=Asignacion)
def manejar_baja_trabajador(sender, instance, **kwargs):
    """Cuando se elimina una asignación, quitar al trabajador de la conversación
    de cuadrilla y eliminar la conversación si queda con menos de 2 participantes.
    """
    cuadrilla = instance.cuadrilla
    if not cuadrilla:
        return

    conv = Conversation.objects.filter(is_group=True, cuadrilla=cuadrilla).first()
    if not conv:
        return

    if instance.trabajador:
        try:
            conv.participants.remove(instance.trabajador)
        except Exception:
            pass

    if conv.participants.count() < 2:
        conv.delete()
