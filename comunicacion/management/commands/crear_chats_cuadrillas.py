from django.core.management.base import BaseCommand
from personal.models import Cuadrilla, Asignacion
from comunicacion.models import Conversation


class Command(BaseCommand):
    help = 'Crea conversaciones grupales para todas las cuadrillas que no tienen una'

    def handle(self, *args, **options):
        cuadrillas = Cuadrilla.objects.all()
        created = 0

        for cuadrilla in cuadrillas:
            # Verificar si ya existe conversación grupal para esta cuadrilla
            conv_existe = Conversation.objects.filter(
                is_group=True,
                cuadrilla=cuadrilla
            ).exists()

            if not conv_existe:
                # Crear conversación grupal
                conv = Conversation.objects.create(
                    nombre=f"Chat {cuadrilla.nombre}",
                    is_group=True,
                    cuadrilla=cuadrilla
                )

                # Agregar todos los miembros de la cuadrilla como participantes
                asignaciones = Asignacion.objects.filter(cuadrilla=cuadrilla)
                for asignacion in asignaciones:
                    conv.participants.add(asignacion.trabajador)

                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Creada conversación grupal para {cuadrilla.nombre}')
                )

        if created == 0:
            self.stdout.write(
                self.style.WARNING('No se crearon conversaciones nuevas (todas ya existen)')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Total de conversaciones creadas: {created}')
            )
