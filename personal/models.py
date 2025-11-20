from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
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


# --- Nuevo modelo: Trabajador (entidad principal) ---
def rut_valido(value):
    """Validador simplificado para RUT: acepta únicamente exactamente 9 dígitos.

    Se limpia cualquier carácter no numérico y se exige que la longitud sea 9.
    Esto evita la validación del Dígito Verificador (DV).
    """
    rut = ''.join(ch for ch in str(value) if ch.isdigit())
    if not rut.isdigit() or len(rut) != 9:
        raise ValidationError('El RUT debe contener exactamente 9 dígitos numéricos')


class Trabajador(models.Model):
    TIPO_CHOICES = [
        ('trabajador', 'Trabajador'),
        ('lider', 'Líder'),
        ('jefe', 'Jefe'),
    ]

    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),
        ('asignado', 'Asignado'),
        ('vacaciones', 'Vacaciones'),
        ('licencia', 'Licencia'),
        ('inactivo', 'Inactivo'),
    ]

    # Datos personales
    rut = models.CharField(max_length=20, unique=True, validators=[rut_valido])
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=30, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    # Datos laborales
    tipo_trabajador = models.CharField(max_length=20, choices=TIPO_CHOICES, default='trabajador')
    especialidad = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='disponible')
    fecha_ingreso = models.DateField(null=True, blank=True)
    anos_experiencia = models.PositiveIntegerField(default=0)

    # Relación opcional con Django User
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajador_profile')

    activo = models.BooleanField(default=True)

    # Indica si el password es inicial (a cambiar en primer login)
    password_inicial = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trabajador'
        verbose_name_plural = 'Trabajadores'

    def __str__(self):
        return f"{self.rut} - {self.nombre} {self.apellido}"

    def clean_rut(self):
        # Devuelve el rut limpio para username: sin puntos ni guión
        return ''.join(ch for ch in str(self.rut) if ch.isalnum())

    def crear_usuario(self):
        """
        Crea automáticamente un User de Django si no existe y retorna el objeto User.

        IMPORTANTE: este método NO debe realizar commits en la instancia Trabajador
        (no llama a self.save()) para evitar loops con signals. El caller (signal
        minimal) es responsable de asociar el user al trabajador con una actualización
        a nivel de queryset.
        """
        if self.user:
            return self.user

        username = self.clean_rut()
        from django.contrib.auth.models import Group

        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.create_user(username=username, password=self.rut)

        # sincronizar datos
        user.email = self.email
        user.first_name = self.nombre
        user.last_name = self.apellido
        user.is_active = self.activo
        user.save()

        # Asignar grupos mínimos (el grupo 'Trabajador' siempre debe existir)
        if self.tipo_trabajador == 'lider':
            group = Group.objects.filter(name='LiderCuadrilla').first()
            if group:
                user.groups.add(group)
        elif self.tipo_trabajador == 'jefe':
            group = Group.objects.filter(name='JefeProyecto').first()
            if group:
                user.groups.add(group)

        return user

    def sincronizar_a_user(self):
        """Sincroniza campos básicos al User asociado si existe."""
        if not self.user:
            return
        u = self.user
        u.email = self.email
        u.first_name = self.nombre
        u.last_name = self.apellido
        u.is_active = self.activo
        u.save()


# Modelos relacionados específicos para Trabajador
class CompetenciaTrabajador(models.Model):
    NIVEL_CHOICES = [
        ('basico', 'Básico'),
        ('intermedio', 'Intermedio'),
        ('avanzado', 'Avanzado'),
        ('experto', 'Experto'),
    ]
    trabajador = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='competencias')
    nombre = models.CharField(max_length=100)
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='basico')
    fecha_adquisicion = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('trabajador', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.trabajador.rut})"


class CertificacionTrabajador(models.Model):
    trabajador = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='certificaciones_trabajador')
    nombre = models.CharField(max_length=150)
    entidad = models.CharField(max_length=150, blank=True, null=True)
    archivo = models.FileField(upload_to='certificaciones/', blank=True, null=True)
    fecha_emision = models.DateField()
    fecha_expiracion = models.DateField(null=True, blank=True)

    def vigente(self):
        if not self.fecha_expiracion:
            return True
        from django.utils import timezone
        return self.fecha_expiracion >= timezone.localdate()

    def __str__(self):
        return f"{self.nombre} - {self.trabajador.rut}"


class ExperienciaTrabajador(models.Model):
    trabajador = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='experiencias_trabajador')
    proyecto = models.CharField(max_length=150, blank=True, null=True)
    empresa_externa = models.CharField(max_length=150, blank=True, null=True)
    rol = models.CharField(max_length=100, blank=True, null=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_termino = models.DateField(null=True, blank=True)
    calificacion = models.CharField(max_length=20, choices=[('no_recomendado','No recomendado'),('recomendado','Recomendado'),('muy_recomendado','Muy recomendado')], blank=True, null=True)

    def __str__(self):
        return f"{self.trabajador.rut} - {self.proyecto or self.empresa_externa or 'Experiencia'}"
    

#  NOTIFICACIONES INTERNAS DEL SISTEMA

class Notificacion(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notificaciones"
    )

    mensaje = models.TextField()

    fecha = models.DateTimeField(auto_now_add=True)

    leida = models.BooleanField(default=False)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.user.username} -> {self.mensaje[:40]}"
