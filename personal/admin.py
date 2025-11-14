from django.contrib import admin
from .models import (
    TrabajadorPerfil,
    Competencia,
    Certificacion,
    Experiencia,
    # y si quieres, también:
    Cuadrilla,
    Rol,
    Asignacion,
)

admin.site.register(TrabajadorPerfil)
admin.site.register(Competencia)
admin.site.register(Certificacion)
admin.site.register(Experiencia)
admin.site.register(Cuadrilla)
admin.site.register(Rol)
admin.site.register(Asignacion)
