from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from proyectos.models import Proyecto
from personal.models import Cuadrilla, Asignacion, Rol as RolCuadrilla, Trabajador


class Command(BaseCommand):
    help = "Genera datos de demo: 5 proyectos, 2 cuadrillas por proyecto y 4 trabajadores por cuadrilla."

    def handle(self, *args, **options):
        # Obtener o crear grupos
        jefe_group, _ = Group.objects.get_or_create(name='JefeProyecto')
        lider_group, _ = Group.objects.get_or_create(name='LiderCuadrilla')

        # Seleccionar dos jefes existentes; si faltan, crearlos
        jefes = list(User.objects.filter(groups__name='JefeProyecto')[:2])
        while len(jefes) < 2:
            idx = len(jefes) + 1
            u = User.objects.create_user(
                username=f'jefe{idx}', password='jefe1234',
                first_name=f'Jefe {idx}', last_name='Demo', email=f'jefe{idx}@demo.local'
            )
            u.groups.add(jefe_group)
            jefes.append(u)

        # Crear rol por defecto para asignaciones si no existe
        rol_trabajador, _ = RolCuadrilla.objects.get_or_create(nombre='Operario')

        proyectos_creados = []
        for i in range(1, 6):
            jefe = jefes[i % 2]
            nombre = f"Proyecto Demo {i}"
            proyecto, created = Proyecto.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'descripcion': 'Proyecto de demostración generado automáticamente',
                    'tipo': 'construccion',
                    'complejidad': 'media',
                    'fecha_inicio': timezone.localdate(),
                    'jefe': jefe,
                    'created_by': jefe,
                    'activo': True,
                }
            )
            if not created:
                proyecto.jefe = jefe
                proyecto.activo = True
                proyecto.save()
            proyectos_creados.append(proyecto)

        # Crear líderes suficientes
        lideres = list(User.objects.filter(groups__name='LiderCuadrilla'))
        needed_lideres = 2 * len(proyectos_creados) - len(lideres)
        for i in range(1, needed_lideres + 1):
            u = User.objects.create_user(
                username=f'lider{i}', password='lider1234',
                first_name=f'Líder {i}', last_name='Demo', email=f'lider{i}@demo.local'
            )
            u.groups.add(lider_group)
            lideres.append(u)

        # Crear trabajadores suficientes y vincular a Trabajador
        trabajadores_users = list(User.objects.exclude(id__in=[u.id for u in jefes + lideres]))
        trabajadores = list(Trabajador.objects.filter(user__in=trabajadores_users))
        # Calcular cuántos trabajadores se requieren: 2 cuadrillas * 4 trabajadores por proyecto
        required_trabajadores = 2 * 4 * len(proyectos_creados)
        deficit = required_trabajadores - len(trabajadores)
        for i in range(1, deficit + 1):
            username = f'trab{i}'
            user = User.objects.create_user(
                username=username, password='trab1234',
                first_name='Trab', last_name=f'Demo{i}', email=f'{username}@demo.local'
            )
            t = Trabajador.objects.create(
                rut=f'{100000000 + i}',
                nombre=user.first_name,
                apellido=user.last_name,
                email=user.email,
                tipo_trabajador='trabajador',
                estado='disponible',
                user=user,
                activo=True,
            )
            trabajadores.append(t)

        # Asignar cuadrillas y trabajadores
        trabajador_idx = 0
        lider_idx = 0
        for proyecto in proyectos_creados:
            for cnum in range(1, 3):
                lider = lideres[lider_idx % len(lideres)]
                lider_idx += 1
                cuadrilla, _ = Cuadrilla.objects.get_or_create(
                    nombre=f"Cuadrilla {proyecto.nombre}-{cnum}",
                    proyecto=proyecto,
                    defaults={'lider': lider}
                )
                cuadrilla.lider = lider
                cuadrilla.save()

                # Limpiar asignaciones previas
                cuadrilla.asignaciones.all().delete()

                # Asignar 4 trabajadores
                for _ in range(4):
                    t = trabajadores[trabajador_idx % len(trabajadores)]
                    trabajador_idx += 1
                    Asignacion.objects.create(
                        trabajador=t.user,
                        cuadrilla=cuadrilla,
                        rol=rol_trabajador,
                    )

        self.stdout.write(self.style.SUCCESS('Datos de demo generados correctamente.'))