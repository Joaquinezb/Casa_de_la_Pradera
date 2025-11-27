from django.db import models
from django.contrib.auth.models import User


"""Modelos para la funcionalidad de comunicación del proyecto.

Contiene modelos principales para conversaciones (`Conversation`), mensajes
(`Message`), solicitudes de trabajador (`WorkerRequest`) y avisos de incidente
(`IncidentNotice`).

Comentarios y docstrings en este archivo tienen granularidad alta: explican
propósito de cada campo, métodos relevantes, side-effects y casos límite.
"""


class Conversation(models.Model):
    """Representa una conversación entre usuarios.

    Tipos de conversación:
    - Privada: `is_group=False`. Usualmente 2 participantes, aunque la estructura
      permite más.
    - Grupal: `is_group=True`. Normalmente vinculada a una `Cuadrilla` (equipo).

    Atributos clave:
    - `nombre`: nombre opcional de la conversación (útil para grupos o alias).
    - `is_group`: bool que marca si es conversación grupal.
    - `cuadrilla`: FK a `personal.Cuadrilla` (nullable). Si está presente y
      `is_group=True`, la conversación representa el canal del equipo.
    - `participants`: ManyToMany con `User` que lista los miembros de la conversación.
    - `created_at`: timestamp de creación.

    Consideraciones de funcionamiento:
    - Se referencia `personal.Cuadrilla` por string para evitar importaciones
      circulares con la app `personal`.
    - Los métodos ayudan a mantener sincronía entre asignaciones en `personal`
      y la conversación grupal (ver `ensure_group_for_cuadrilla`).
    """
    nombre = models.CharField(max_length=150, blank=True, null=True)
    is_group = models.BooleanField(default=False)
    # FK por string para evitar dependencias circulares entre apps
    cuadrilla = models.ForeignKey(
        'personal.Cuadrilla',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversaciones'
    )
    # Usuarios que participan en la conversación
    participants = models.ManyToManyField(User, related_name='conversaciones')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Orden por más reciente primero para listar conversaciones activas
        ordering = ['-created_at']

    def __str__(self):
        # Representación legible de la conversación para admin y debugging
        if self.is_group and self.cuadrilla:
            return f"Grupo: {self.cuadrilla.nombre}"
        if self.nombre:
            return self.nombre
        return f"Privada ({self.pk})"

    def add_participants(self, users):
        """Agrega usuarios como participantes.

        Parámetros
        - users: iterable de instancias `User`.

        Efectos secundarios
        - Añade cada usuario al campo M2M `participants` usando `add()`.
        - No realiza validación adicional (por ejemplo, duplicados son ignorados
          por la relación M2M de Django).
        """
        for u in users:
            if u:
                self.participants.add(u)

    @classmethod
    def ensure_group_for_cuadrilla(cls, cuadrilla, min_members=2):
        """Asegura que exista una conversación grupal para una `cuadrilla`.

        Comportamiento:
        - Busca `Asignacion` en `personal.models` para obtener los miembros
          actuales de la cuadrilla.
        - Si el número de miembros >= `min_members`, crea la conversación
          grupal si no existe y añade todos los `trabajador` como participantes.
        - Si el número de miembros es < `min_members` y existe conversación,
          la elimina (se asume que no tiene sentido conservarla vacía o con pocos
          miembros).

        Retorno:
        - Instancia de `Conversation` creada/actualizada cuando hay suficientes
          miembros.
        - `None` si la conversación no debe existir (menos de `min_members`).

        Notas de rendimiento y concurrencia:
        - La consulta `Asignacion.objects.filter(...)` puede traer muchos
          registros; si se usa en ciclos frecuentes, considerar optimizar con
          `.values_list('trabajador', flat=True)` o señales que actualicen
          incrementalmente.
        - No utiliza transacciones explícitas; si la consistencia es crítica,
          envolver en `transaction.atomic()` desde el lugar que invoque este
          método.
        """
        # Importación local para evitar ciclo de imports al cargar apps
        from personal.models import Asignacion

        miembros = Asignacion.objects.filter(cuadrilla=cuadrilla)
        total = miembros.count()

        # Buscar conversación grupal existente para esta cuadrilla
        conv = cls.objects.filter(is_group=True, cuadrilla=cuadrilla).first()

        if total >= min_members:
            if not conv:
                # Crear conversación grupal nombrada con el nombre de la cuadrilla
                conv = cls.objects.create(
                    is_group=True,
                    cuadrilla=cuadrilla,
                    nombre=f"Cuadrilla {cuadrilla.nombre}"
                )
            # Añadir usuarios asignados (filtrando `None` por seguridad)
            users = [a.trabajador for a in miembros if a.trabajador]
            conv.add_participants(users)
            return conv
        else:
            # Menos miembros de los necesarios: eliminar conversación si existe
            if conv:
                conv.delete()
            return None


class Message(models.Model):
    """Mensaje dentro de una `Conversation`.

    Soporta tipos de mensaje para diferenciar comportamiento en la UI o
    procesamiento posterior (por ejemplo: solicitudes, incidentes).

    Campos relevantes:
    - `conversation`: FK a `Conversation` donde se publica el mensaje.
    - `sender`: usuario emisor; `null` significa mensaje del sistema.
    - `content`: texto principal del mensaje.
    - `message_type`: tipo semántico del mensaje.
    - `read_by`: M2M con `User` para control de lectura por participante.
    - `created_at`: timestamp de creación.
    """
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
    # Usuarios que han marcado el mensaje como leído; usado para indicadores
    # de lectura por participante y notificaciones no leídas.
    read_by = models.ManyToManyField(User, related_name='mensajes_leidos', blank=True)

    class Meta:
        # Orden natural por fecha ascendente (cronológico) dentro de una conversación
        ordering = ['created_at']

    def __str__(self):
        sender = self.sender.username if self.sender else 'Sistema'
        # Mostrar fragmento del contenido para facilitar debugging
        return f"{sender} @ {self.created_at}: {self.content[:40]}"


class WorkerRequest(models.Model):
    """Modelo para peticiones/solicitudes realizadas por un trabajador.

    Ejemplos de uso: solicitudes de cambio de cuadrilla, permisos, comunicaciones
    con RRHH/administración. El flujo típico es:
    - Estado inicial `pending`.
    - Un actor (admin/gestor) cambia a `accepted` o `rejected`.

    Campos:
    - `trabajador`: autor de la solicitud.
    - `cuadrilla`: opción para vincular la petición a un equipo concreto.
    - `asunto`/`descripcion`: contenido textual de la solicitud.
    - `estado`: control del flujo de la solicitud.
    - `created_at`: fecha de creación para auditoría.
    """
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
    """Aviso de incidente reportado por personal o detectado en campo.

    Uso previsto:
    - Registrar eventos con severidad para seguimiento operativo.
    - Vincular (opcionalmente) la incidencia a una `Cuadrilla` responsable.
    - `acknowledged` marca que la incidencia fue reconocida por un actor
      (p. ej. un supervisor) y no requiere avisos adicionales.

    Campos:
    - `descripcion`: detalle del incidente.
    - `severidad`: priorización básica (baja/media/alta).
    - `acknowledged`: booleano para workflow de reconocimiento.
    """
    SEVERITY = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
    ]
    cuadrilla = models.ForeignKey(
        'personal.Cuadrilla',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidentes'
    )
    reporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidentes_reportados')
    descripcion = models.TextField()
    severidad = models.CharField(max_length=10, choices=SEVERITY, default='low')
    created_at = models.DateTimeField(auto_now_add=True)
    # Indica si el incidente fue reconocido por el equipo de respuesta
    acknowledged = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Incidente ({self.severidad}) - {self.cuadrilla or 'Sin cuadrilla'}"
