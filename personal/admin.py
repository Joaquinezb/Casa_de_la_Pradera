from django.contrib import admin
from django.contrib.auth.models import User
from .models import (
    TrabajadorPerfil,
    Competencia,
    Certificacion,
    Experiencia,
    Cuadrilla,
    Rol,
    Asignacion,
    # nuevos
    Trabajador,
    CompetenciaTrabajador,
    CertificacionTrabajador,
    ExperienciaTrabajador,
)


class CompetenciaInline(admin.TabularInline):
    model = CompetenciaTrabajador
    extra = 1


class CertificacionInline(admin.TabularInline):
    model = CertificacionTrabajador
    extra = 1


class ExperienciaInline(admin.TabularInline):
    model = ExperienciaTrabajador
    extra = 1


@admin.action(description='Regenerar usuario para trabajadores seleccionados')
def regenerar_usuarios(modeladmin, request, queryset):
    for t in queryset:
        try:
            t.crear_usuario()
        except Exception:
            pass


@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    list_display = ('rut', 'nombre', 'apellido', 'email', 'tipo_trabajador', 'estado', 'activo', 'has_user')
    list_filter = ('tipo_trabajador', 'especialidad', 'estado', 'activo')
    search_fields = ('rut', 'nombre', 'apellido', 'email')
    inlines = [CompetenciaInline, CertificacionInline, ExperienciaInline]
    actions = [regenerar_usuarios]
    readonly_fields = ('username_display', 'initial_password_info')

    def has_user(self, obj):
        return bool(obj.user)
    has_user.boolean = True
    has_user.short_description = 'Usuario generado'

    def username_display(self, obj):
        return obj.user.username if obj.user else ''
    username_display.short_description = 'Username'

    def initial_password_info(self, obj):
        if obj.user and obj.password_inicial:
            return 'Password inicial = RUT (debe cambiarse en primer login)'
        return ''
    initial_password_info.short_description = 'Password inicial'


# Mantener registros existentes para compatibilidad
admin.site.register(TrabajadorPerfil)
admin.site.register(Competencia)
admin.site.register(Certificacion)
admin.site.register(Experiencia)
admin.site.register(Cuadrilla)
admin.site.register(Rol)
admin.site.register(Asignacion)
