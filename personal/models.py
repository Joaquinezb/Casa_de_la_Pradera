from django.db import models
from django.contrib.auth.models import User
from proyectos.models import Proyecto

class Cuadrilla(models.Model):
    nombre = models.CharField(max_length=100)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='cuadrillas', null=True, blank=True)
    lider = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cuadrillas_lideradas')

    def __str__(self):
        return f"{self.nombre} ({self.proyecto.nombre if self.proyecto else 'Sin proyecto'})"


class Rol(models.Model):
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre


class Asignacion(models.Model):
    trabajador = models.ForeignKey(User, on_delete=models.CASCADE)
    cuadrilla = models.ForeignKey(Cuadrilla, on_delete=models.CASCADE, related_name='asignaciones')
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.trabajador.username} → {self.rol.nombre if self.rol else 'Sin rol'}"


# Perfil extendido del trabajador
class TrabajadorPerfil(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil_trabajador'
    )
    especialidad = models.CharField(max_length=100, blank=True, null=True)
    # Estado manual: se usa para vacaciones, licencia, etc.
    estado_manual = models.CharField(
        max_length=20,
        choices=[
            ('disponible', 'Disponible'),
            ('no_disponible', 'No disponible'),
            ('licencia', 'Licencia médica'),
            ('vacaciones', 'Vacaciones'),
        ],
        default='disponible'
    )

    def __str__(self):
        return self.user.username

    @property
    def estado_efectivo(self):
        """
        Si el trabajador tiene alguna asignación activa, lo consideramos 'ocupado'.
        Si no, usamos el estado_manual.
        """
        asignado = Asignacion.objects.filter(trabajador=self.user).exists()
        if asignado:
            return 'ocupado'
        return self.estado_manual


# Competencias por trabajador (p.ej. "Soldadura certificada")
class Competencia(models.Model):
    trabajador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='competencias'
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    certificada = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nombre} ({self.trabajador.username})"


# Certificaciones con archivo PDF
class Certificacion(models.Model):
    trabajador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='certificaciones'
    )
    nombre = models.CharField(max_length=100)
    archivo = models.FileField(upload_to='certificaciones/')  # PDF u otro
    fecha_emision = models.DateField()
    fecha_expiracion = models.DateField(null=True, blank=True)
    entidad = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.trabajador.username}"


# Experiencia del trabajador (interna y externa)
class Experiencia(models.Model):
    trabajador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='experiencias'
    )
    # Si es un proyecto de la empresa:
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='experiencias_trabajador'
    )
    # Si es un trabajo anterior externo:
    proyecto_externo = models.CharField(max_length=150, blank=True, null=True)
    empresa_externa = models.CharField(max_length=150, blank=True, null=True)
    meses_participacion = models.PositiveIntegerField(null=True, blank=True)

    calificacion = models.CharField(
        max_length=20,
        choices=[
            ('no_recomendado', 'No recomendado'),
            ('recomendado', 'Recomendado'),
            ('muy_recomendado', 'Muy recomendado'),
        ]
    )

    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.proyecto:
            return f"{self.trabajador.username} - {self.proyecto.nombre}"
        return f"{self.trabajador.username} - {self.proyecto_externo or 'Experiencia externa'}"