from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from proyectos.models import Proyecto
from personal.models import Cuadrilla, Asignacion, Trabajador, TrabajadorPerfil
from personal.utils import obtener_disponibilidad_trabajador


def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


@login_required(login_url='/usuarios/login/')
def dashboard_redirect(request):
    """Vista de dashboard con métricas según el rol del usuario"""
    user = request.user
    
    # Determinar rol del usuario
    is_jefe = user.groups.filter(name='JefeProyecto').exists()
    is_lider = user.groups.filter(name='LiderCuadrilla').exists()
    is_trabajador = user.groups.filter(name='Trabajador').exists()
    
    # Si es trabajador, redirigir a su vista de cuadrilla
    if is_trabajador and not is_jefe and not is_lider:
        return redirect('personal:mi_cuadrilla')
    
    # Vista limitada para líderes de cuadrilla (sin privilegios de jefe)
    if is_lider and not is_jefe:
        cuadrilla_lider = (
            Cuadrilla.objects
            .filter(lider=user)
            .select_related('proyecto')
            .first()
        )

        miembros_cuadrilla = []
        conteos_estado = {
            'trabajando': 0,
            'disponibles': 0,
            'vacaciones': 0,
            'otros': 0,
        }

        proyecto_actual = None
        estado_proyecto_label = 'Sin proyecto asignado'

        if cuadrilla_lider:
            proyecto_actual = cuadrilla_lider.proyecto

            if proyecto_actual:
                estado_proyecto_label = 'En progreso' if proyecto_actual.activo else 'Finalizado'

            asignaciones = list(
                Asignacion.objects
                .filter(cuadrilla=cuadrilla_lider)
                .select_related('trabajador')
            )

            users_asignados = [a.trabajador for a in asignaciones]

            trabajadores = {
                t.user_id: t for t in Trabajador.objects.filter(user__in=users_asignados).select_related('user')
            }
            perfiles = {
                p.user_id: p for p in TrabajadorPerfil.objects.filter(user__in=users_asignados).select_related('user')
            }

            estado_labels = {
                'ocupado': 'Trabajando',
                'asignado': 'Trabajando',
                'disponible': 'Disponible',
                'vacaciones': 'En vacaciones',
                'licencia': 'En licencia',
                'no_disponible': 'No disponible',
                'inactivo': 'Inactivo',
            }

            for asignacion in asignaciones:
                miembro_user = asignacion.trabajador
                trabajador_obj = trabajadores.get(miembro_user.id)
                perfil_obj = perfiles.get(miembro_user.id)

                estado_raw = obtener_disponibilidad_trabajador(trabajador_obj, perfil_obj)
                estado_mostrable = estado_labels.get(estado_raw, 'Sin estado')

                if estado_raw in ['ocupado', 'asignado']:
                    conteos_estado['trabajando'] += 1
                elif estado_raw == 'disponible':
                    conteos_estado['disponibles'] += 1
                elif estado_raw == 'vacaciones':
                    conteos_estado['vacaciones'] += 1
                else:
                    conteos_estado['otros'] += 1

                miembros_cuadrilla.append({
                    'nombre': miembro_user.get_full_name() or miembro_user.username,
                    'estado': estado_mostrable,
                })

        context = {
            'is_jefe': is_jefe,
            'is_lider': is_lider,
            'is_trabajador': is_trabajador,
            'cuadrilla_lider': cuadrilla_lider,
            'proyecto_actual': proyecto_actual,
            'estado_proyecto_label': estado_proyecto_label,
            'miembros_cuadrilla': miembros_cuadrilla,
            'conteos_estado': conteos_estado,
            'total_miembros': len(miembros_cuadrilla),
            'sin_cuadrilla': cuadrilla_lider is None,
        }

        return render(request, 'dashboard.html', context)

    # KPIs generales
    proyectos_activos = Proyecto.objects.filter(activo=True).count()
    proyectos_finalizados = Proyecto.objects.filter(activo=False).count()
    cuadrillas_activas = Cuadrilla.objects.exclude(proyecto__isnull=True).count()
    cuadrillas_sin_proyecto = Cuadrilla.objects.filter(proyecto__isnull=True).count()

    # Total de trabajadores operativos (excluye líderes y jefes que son roles administrativos)
    total_trabajadores = Trabajador.objects.filter(
        activo=True,
        tipo_trabajador='trabajador'
    ).count()

    # Trabajadores asignados: obtener los IDs de User desde Asignacion,
    # luego contar cuántos Trabajador tipo 'trabajador' tienen ese user asociado
    users_asignados = Asignacion.objects.values_list('trabajador', flat=True).distinct()
    trabajadores_asignados = Trabajador.objects.filter(
        activo=True,
        tipo_trabajador='trabajador',
        user__id__in=users_asignados
    ).count()

    # Trabajadores disponibles
    trabajadores_disponibles = total_trabajadores - trabajadores_asignados

    # Proyectos recientes (últimos 5 activos)
    proyectos_recientes = Proyecto.objects.filter(activo=True).order_by('-created_at')[:5]

    # Lista completa de proyectos activos para el modal
    proyectos_activos_list = Proyecto.objects.filter(activo=True).order_by('nombre')

    # Cuadrillas sin asignar
    cuadrillas_disponibles = Cuadrilla.objects.filter(proyecto__isnull=True)[:5]

    context = {
        'is_jefe': is_jefe,
        'is_lider': is_lider,
        'is_trabajador': is_trabajador,
        'proyectos_activos': proyectos_activos,
        'proyectos_finalizados': proyectos_finalizados,
        'cuadrillas_activas': cuadrillas_activas,
        'cuadrillas_sin_proyecto': cuadrillas_sin_proyecto,
        'total_trabajadores': total_trabajadores,
        'trabajadores_asignados': trabajadores_asignados,
        'trabajadores_disponibles': trabajadores_disponibles,
        'proyectos_recientes': proyectos_recientes,
        'proyectos_activos_list': proyectos_activos_list,
        'cuadrillas_disponibles': cuadrillas_disponibles,
    }

    return render(request, 'dashboard.html', context)


def index(request):
    # Mostrar una página pública si el usuario NO está autenticado (sin navbar)
    if not request.user.is_authenticated:
        return render(request, 'index_public.html')
    # Usuario autenticado: redirigir a dashboard
    return redirect('core:dashboard')


@login_required(login_url='/usuarios/login/')
@user_passes_test(es_jefe)
def asignar_cuadrilla_individual(request, cuadrilla_id):
    """Asigna una cuadrilla individual a un proyecto"""
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id, proyecto__isnull=True)
    
    if request.method == 'POST':
        proyecto_id = request.POST.get('proyecto_id')
        if proyecto_id:
            proyecto = get_object_or_404(Proyecto, id=proyecto_id, activo=True)
            cuadrilla.proyecto = proyecto
            cuadrilla.save()
            
            messages.success(request, f"La cuadrilla '{cuadrilla.nombre}' fue asignada al proyecto '{proyecto.nombre}'.")
        else:
            messages.error(request, "Debe seleccionar un proyecto.")
    
    return redirect('core:dashboard')


@login_required(login_url='/usuarios/login/')
@user_passes_test(es_jefe)
def asignar_cuadrillas_masivo(request):
    """Vista para asignar múltiples cuadrillas a proyectos"""
    cuadrillas_disponibles = Cuadrilla.objects.filter(proyecto__isnull=True)
    proyectos_activos = Proyecto.objects.filter(activo=True).order_by('nombre')
    
    if request.method == 'POST':
        asignaciones_realizadas = 0
        
        for cuadrilla in cuadrillas_disponibles:
            proyecto_id = request.POST.get(f'proyecto_{cuadrilla.id}')
            if proyecto_id:
                proyecto = get_object_or_404(Proyecto, id=proyecto_id, activo=True)
                cuadrilla.proyecto = proyecto
                cuadrilla.save()
                asignaciones_realizadas += 1
        
        if asignaciones_realizadas > 0:
            messages.success(request, f"Se asignaron {asignaciones_realizadas} cuadrilla(s) a sus respectivos proyectos.")
        else:
            messages.warning(request, "No se realizó ninguna asignación.")
        
        return redirect('core:dashboard')
    
    context = {
        'cuadrillas_disponibles': cuadrillas_disponibles,
        'proyectos_activos': proyectos_activos,
    }
    
    return render(request, 'asignar_cuadrillas_masivo.html', context)
