from django.db import models
from django.contrib.auth.models import User

class Proyecto(models.Model):
    nombre = models.CharField(max_length=100)
    # Características / descripción del proyecto
    descripcion = models.TextField(blank=True)

    # Tipo de proyecto (ejemplos, puedes ajustar las opciones)
    TIPO_CHOICES = [
        ('construccion', 'Construcción'),
        ('mantenimiento', 'Mantenimiento'),
        ('instalacion', 'Instalación'),
        ('otro', 'Otro'),
    ]
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='otro')

    # Complejidad del proyecto
    COMPLEJIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
    ]
    complejidad = models.CharField(max_length=10, choices=COMPLEJIDAD_CHOICES, default='media')
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField(null=True, blank=True)
    jefe = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proyectos')
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Rol(models.Model):
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre
