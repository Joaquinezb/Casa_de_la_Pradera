from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Crear 6 trabajadores de prueba con RUTs específicos para validación'

    RUTS = [
        '218391519',
        '218391521',
        '218391522',
        '218391523',
        '218391524',
        '218391525',
    ]

    def handle(self, *args, **options):
        from django.contrib.auth.models import Group
        from personal.models import Trabajador

        created = []
        updated = []

        for i, rut in enumerate(self.RUTS, start=1):
            t = Trabajador.objects.filter(rut=rut).first()
            if t:
                # actualizar datos básicos si es necesario
                t.nombre = t.nombre or f'Test{i}'
                t.apellido = t.apellido or 'Prueba'
                t.email = t.email or f'{rut}@example.com'
                t.tipo_trabajador = 'trabajador'
                t.activo = True
                t.save()
                updated.append(rut)
            else:
                t = Trabajador.objects.create(
                    rut=rut,
                    nombre=f'Test{i}',
                    apellido='Prueba',
                    email=f'{rut}@example.com',
                    tipo_trabajador='trabajador',
                    estado='disponible',
                    activo=True,
                )
                created.append(rut)

            # Crear y asociar User si es necesario
            try:
                user = t.crear_usuario()
                # vincular explícitamente y guardar
                if not t.user or t.user.id != user.id:
                    t.user = user
                    t.save()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Advertencia creando usuario para {rut}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Creados: {len(created)} ({created})'))
        self.stdout.write(self.style.SUCCESS(f'Actualizados: {len(updated)} ({updated})'))

        # Verificación rápida
        qs = Trabajador.objects.filter(rut__in=self.RUTS)
        for tr in qs:
            self.stdout.write(f'- {tr.rut} | user_id={tr.user_id} | nombre={tr.nombre} {tr.apellido}')
