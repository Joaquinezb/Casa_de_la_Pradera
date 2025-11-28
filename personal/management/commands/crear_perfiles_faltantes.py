from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from personal.models import TrabajadorPerfil, Trabajador


class Command(BaseCommand):
    help = "Crea TrabajadorPerfil para todos los usuarios trabajadores que no lo tengan."

    def handle(self, *args, **options):
        # Obtener usuarios de trabajadores sin perfil
        trabajadores = Trabajador.objects.select_related('user').filter(user__isnull=False)
        creados = 0
        
        for trabajador in trabajadores:
            user = trabajador.user
            if not hasattr(user, 'perfil_trabajador'):
                TrabajadorPerfil.objects.create(
                    user=user,
                    especialidad=trabajador.especialidad or '',
                    estado_manual='disponible'
                )
                creados += 1
                self.stdout.write(f"Creado perfil para {user.username}")
        
        self.stdout.write(self.style.SUCCESS(f'Total de perfiles creados: {creados}'))
