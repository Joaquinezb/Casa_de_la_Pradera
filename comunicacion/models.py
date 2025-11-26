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
        return f"{self.sender} @ {self.created_at}: {self.content[:40]}"


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
