from django.apps import AppConfig


class ComunicacionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "comunicacion"
    verbose_name = "Comunicacion"

    def ready(self):
        # Importar signals para que se registren
        import comunicacion.signals