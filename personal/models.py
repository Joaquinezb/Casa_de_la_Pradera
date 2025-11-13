from django.db import models
from django.contrib.auth.models import User
from proyectos.models import Proyecto

class Cuadrilla(models.Model):
    nombre = models.CharField(max_length=100)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='cuadrillas')
    lider = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cuadrillas_lideradas')

    def __str__(self):
        return f"{self.nombre} ({self.proyecto.nombre})"


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