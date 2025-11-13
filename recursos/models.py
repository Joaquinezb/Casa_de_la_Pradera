from django.db import models
from personal.models import Cuadrilla

class Recurso(models.Model):
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)
    cantidad = models.PositiveIntegerField()
    unidad = models.CharField(max_length=20, default='unidades')
    cuadrilla = models.ForeignKey(Cuadrilla, on_delete=models.CASCADE, related_name='recursos')

    def __str__(self):
        return f"{self.nombre} ({self.cantidad} {self.unidad})"
