from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from proyectos.models import Proyecto
from personal.models import Cuadrilla, Asignacion, Trabajador


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
    
    # KPIs generales
    proyectos_activos = Proyecto.objects.filter(activo=True).count()
    proyectos_finalizados = Proyecto.objects.filter(activo=False).count()
    cuadrillas_activas = Cuadrilla.objects.exclude(proyecto__isnull=True).count()
    cuadrillas_sin_proyecto = Cuadrilla.objects.filter(proyecto__isnull=True).count()
    
    # Total de trabajadores - Contar desde el modelo Trabajador (no desde User)
    total_trabajadores = Trabajador.objects.filter(activo=True).count()
    
    # Trabajadores asignados (que tienen user y están en asignaciones)
    trabajadores_asignados = Asignacion.objects.values('trabajador').distinct().count()
    
    # Trabajadores disponibles
    trabajadores_disponibles = total_trabajadores - trabajadores_asignados
    
    # Proyectos recientes (últimos 5 activos)
    proyectos_recientes = Proyecto.objects.filter(activo=True).order_by('-created_at')[:5]
    
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
        'cuadrillas_disponibles': cuadrillas_disponibles,
    }
    
    return render(request, 'dashboard.html', context)


def index(request):
    # Mostrar una página pública si el usuario NO está autenticado (sin navbar)
    if not request.user.is_authenticated:
        return render(request, 'index_public.html')
    # Usuario autenticado: redirigir a dashboard
    return redirect('dashboard')
