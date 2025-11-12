from django.db import models
from django.contrib.auth.models import User
from proyectos.models import Proyecto

class Cuadrilla(models.Model):
    nombre = models.CharField(max_length=100)
    lider = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cuadrillas_lideradas')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='cuadrillas')
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Trabajador(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_trabajador')
    cuadrilla = models.ForeignKey(Cuadrilla, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajadores')
    oficio = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.usuario.username
