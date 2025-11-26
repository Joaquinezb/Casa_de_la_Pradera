from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
    """Una conversación puede ser grupal (vinculada a una cuadrilla) o privada entre usuarios.
    - Si `is_group=True` y `cuadrilla` está presente: conversación de la cuadrilla.
    - Si `is_group=False`: conversación privada entre participantes (idealmente 2 participantes).
    """
    nombre = models.CharField(max_length=150, blank=True, null=True)
    is_group = models.BooleanField(default=False)
    # Referencia por string para evitar importaciones circulares
    cuadrilla = models.ForeignKey('personal.Cuadrilla', on_delete=models.CASCADE, null=True, blank=True, related_name='conversaciones')
    participants = models.ManyToManyField(User, related_name='conversaciones')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.is_group and self.cuadrilla:
            return f"Grupo: {self.cuadrilla.nombre}"
        if self.nombre:
            return self.nombre
        return f"Privada ({self.pk})"

    def add_participants(self, users):
        """Agregar múltiples usuarios como participantes de la conversación.

        `users` puede ser un iterable de instancias `User`.
        """
        for u in users:
            if u:
                self.participants.add(u)

    @classmethod
    def ensure_group_for_cuadrilla(cls, cuadrilla, min_members=2):
        """Crear o actualizar la conversación grupal para una `cuadrilla`.

        - Si la cuadrilla tiene al menos `min_members` asignaciones, se crea (si no
          existe) una conversación grupal vinculada y se agregan todos los participantes.
        - Si existen menos miembros que `min_members` y ya existe conversación,
          la conversación es eliminada.
        Devuelve la instancia de `Conversation` creada/actualizada o `None` si no existe.
        """
        from personal.models import Asignacion

        miembros = Asignacion.objects.filter(cuadrilla=cuadrilla)
        total = miembros.count()

        conv = cls.objects.filter(is_group=True, cuadrilla=cuadrilla).first()

        if total >= min_members:
            if not conv:
                conv = cls.objects.create(is_group=True, cuadrilla=cuadrilla, nombre=f"Cuadrilla {cuadrilla.nombre}")
            # Añadir todos los usuarios asignados
            users = [a.trabajador for a in miembros if a.trabajador]
            conv.add_participants(users)
            return conv
        else:
            if conv:
                conv.delete()
            return None


class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Texto'),
        ('request', 'Solicitud'),
        ('incident', 'Incidente'),
    ]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='mensajes')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='mensajes_enviados')
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    created_at = models.DateTimeField(auto_now_add=True)
    # Quiénes han leído este mensaje
    read_by = models.ManyToManyField(User, related_name='mensajes_leidos', blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        sender = self.sender.username if self.sender else 'Sistema'
        return f"{sender} @ {self.created_at}: {self.content[:40]}"


class WorkerRequest(models.Model):
    STATE_CHOICES = [
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('rejected', 'Rechazada'),
    ]
    trabajador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitudes')
    cuadrilla = models.ForeignKey('personal.Cuadrilla', on_delete=models.SET_NULL, null=True, blank=True)
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=STATE_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Solicitud {self.asunto} - {self.trabajador.username} ({self.estado})"


class IncidentNotice(models.Model):
    SEVERITY = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
    ]
    cuadrilla = models.ForeignKey('personal.Cuadrilla', on_delete=models.SET_NULL, null=True, blank=True, related_name='incidentes')
    reporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidentes_reportados')
    descripcion = models.TextField()
    severidad = models.CharField(max_length=10, choices=SEVERITY, default='low')
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Incidente ({self.severidad}) - {self.cuadrilla or 'Sin cuadrilla'}"
