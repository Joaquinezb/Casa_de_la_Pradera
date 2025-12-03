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
    
    # ============================================
    # MODIFICACIÓN: Corrección del cálculo de trabajadores disponibles
    # ============================================
    # PROBLEMA ORIGINAL: El cálculo anterior usaba User.objects.filter(groups__name='Trabajador')
    # y Asignacion.objects.values('trabajador').distinct(), lo que causaba que el resultado
    # fuera negativo (-1) cuando había más asignaciones que usuarios en el grupo.
    #
    # SOLUCIÓN: Ahora usamos el modelo Trabajador directamente para un cálculo más preciso:
    # 1. Contamos solo trabajadores activos del tipo 'trabajador'
    # 2. Filtramos por estado 'disponible'
    # 3. Excluimos trabajadores asignados a proyectos activos
    # 4. Garantizamos que el resultado nunca sea negativo
    # ============================================
    
    # Total de trabajadores - usar modelo Trabajador directamente
    total_trabajadores = Trabajador.objects.filter(activo=True, tipo_trabajador='trabajador').count()
    
    # Trabajadores asignados a cuadrillas con proyecto activo
    trabajadores_asignados_ids = Asignacion.objects.filter(
        cuadrilla__proyecto__isnull=False,
        cuadrilla__proyecto__activo=True
    ).values_list('trabajador_id', flat=True).distinct()
    
    # Trabajadores disponibles: activos, tipo trabajador, estado disponible, y no asignados
    trabajadores_disponibles = Trabajador.objects.filter(
        activo=True,
        tipo_trabajador='trabajador',
        estado='disponible'
    ).exclude(
        user_id__in=trabajadores_asignados_ids
    ).count()
    
    # Asegurar que no sea negativo (protección adicional)
    if trabajadores_disponibles < 0:
        trabajadores_disponibles = 0
    
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
