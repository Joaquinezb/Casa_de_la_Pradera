from django.db import models
from django.contrib.auth.models import User

class Proyecto(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField(null=True, blank=True)
    jefe = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proyectos')
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre
