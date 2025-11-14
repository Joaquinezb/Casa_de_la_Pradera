from django.apps import AppConfig


class PersonalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "personal"

    def ready(self):
        # importar signals para que se registren
        try:
            import personal.signals 
            # Asegurar que los grupos necesarios existen. Mantener simple y seguro.
            from django.contrib.auth.models import Group
            Group.objects.get_or_create(name='Trabajador')
            Group.objects.get_or_create(name='LiderCuadrilla')
            Group.objects.get_or_create(name='JefeProyecto')
        except Exception:
            pass
