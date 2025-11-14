from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Trabajador


@receiver(post_save, sender=Trabajador)
def crear_usuario_automatico(sender, instance: Trabajador, created, **kwargs):
    """Signal minimal: al crear un trabajador, delega la creación del User al
    método del modelo y luego asocia el user al trabajador usando una
    actualización a nivel de queryset para evitar reentradas en signals.
    """
    if not created:
        return

    try:
        user = instance.crear_usuario()
        if user:
            # Actualizamos el registro sin llamar a instance.save() para evitar loops
            Trabajador.objects.filter(pk=instance.pk).update(user_id=user.id, password_inicial=True)
    except Exception:
        # No romper el flujo del admin; registrar/loggear en entorno real
        pass


@receiver(post_save, sender=Trabajador)
def sincronizar_usuario(sender, instance: Trabajador, **kwargs):
    """Signal minimal: si existe user asociado, sincroniza campos básicos.
    Mantener la lógica simple y sin operaciones pesadas.
    """
    if not instance.user:
        return
    try:
        instance.sincronizar_a_user()
    except Exception:
        pass
