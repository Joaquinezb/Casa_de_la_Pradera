from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from personal.models import Asignacion
from .models import Conversation
from .models import archive_conversation
from proyectos.models import Proyecto
from django.db.models.signals import pre_save


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

    # Archivado automático: cuando un trabajador deja una cuadrilla, archivar
    # sus conversaciones privadas para preservarlas.
    user = instance.trabajador
    if user:
        privates = Conversation.objects.filter(is_group=False, participants=user, archived=False)
        for conv in privates:
            archive_conversation(conv, archived_by=None, reason=f"Archivado porque {user.username} fue removido de cuadrilla {cuadrilla.nombre}")


@receiver(pre_save, sender=Proyecto)
def proyecto_pre_save(sender, instance, **kwargs):
    """Al marcar un proyecto como inactivo, archivar conversaciones relacionadas.

    Solo se actúa cuando `activo` pasa de True -> False. Usamos pre_save para
    comparar el estado previo en BD con el nuevo valor.
    """
    if not instance.pk:
        return

    try:
        previous = Proyecto.objects.get(pk=instance.pk)
    except Proyecto.DoesNotExist:
        return

    if previous.activo and not instance.activo:
        cuadrillas = instance.cuadrillas.all()
        for c in cuadrillas:
            convs = Conversation.objects.filter(cuadrilla=c, archived=False)
            for conv in convs:
                archive_conversation(conv, archived_by=None, reason=f"Proyecto '{instance.nombre}' finalizado")
