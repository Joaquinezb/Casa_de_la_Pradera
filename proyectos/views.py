from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Proyecto
from .forms import ProyectoForm
from personal.models import Cuadrilla
from django.db.models import Q
from personal.utils_notificaciones import crear_notificacion
from django.contrib import messages

def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()

@login_required
@user_passes_test(es_jefe)
def panel_proyectos(request):
    proyectos = Proyecto.objects.filter(jefe=request.user)
    return render(request, 'panel.html', {'proyectos': proyectos})

@login_required
@user_passes_test(es_jefe)
def crear_proyecto(request):
    if request.method == 'POST':
        form = ProyectoForm(request.POST)
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.jefe = request.user  # asigna automáticamente el jefe
            proyecto.save()
            return redirect('proyectos:panel')
    else:
        form = ProyectoForm()
    return render(request, 'nuevo_proyecto.html', {'form': form})


@login_required
@user_passes_test(es_jefe)
def panel_proyectos(request):
    # Separar proyectos activos y finalizados
    proyectos_activos = Proyecto.objects.filter(jefe=request.user, activo=True).prefetch_related('cuadrillas')
    proyectos_finalizados = Proyecto.objects.filter(jefe=request.user, activo=False).prefetch_related('cuadrillas')

    data = []
    for p in proyectos_activos:
        cuadrillas = Cuadrilla.objects.filter(proyecto=p)
        data.append({'proyecto': p, 'cuadrillas': cuadrillas})

    finalizados = []
    for p in proyectos_finalizados:
        cuadrillas = Cuadrilla.objects.filter(proyecto=p)
        finalizados.append({'proyecto': p, 'cuadrillas': cuadrillas})

    # Mostrar también cuadrillas que no están asignadas a ningún proyecto
    cuadrillas_sin_proyecto = Cuadrilla.objects.filter(proyecto__isnull=True)

    return render(request, 'panel.html', {
        'data': data,
        'finalizados': finalizados,
        'cuadrillas_sin_proyecto': cuadrillas_sin_proyecto
    })

@login_required
@user_passes_test(es_jefe)
def asignar_cuadrillas(request, proyecto_id):
    proyecto = Proyecto.objects.get(id=proyecto_id, jefe=request.user)
    # Limpiar asociaciones con proyectos finalizados: si una cuadrilla aún apunta
    # a un proyecto que ya fue marcado como inactivo, la desasignamos.
    Cuadrilla.objects.filter(proyecto__activo=False).update(proyecto=None)

    # Cuadrillas disponibles son aquellas sin proyecto, con proyecto inactivo
    # (ya limpiadas arriba) o que ya pertenecen a este proyecto.
    cuadrillas_disponibles = Cuadrilla.objects.filter(Q(proyecto__isnull=True) | Q(proyecto=proyecto))

    if request.method == 'POST':
        seleccionadas = request.POST.getlist('cuadrillas')
        
        # Desasignar cuadrillas anteriores
        Cuadrilla.objects.filter(proyecto=proyecto).update(proyecto=None)
        
        # Asignar nuevas
        Cuadrilla.objects.filter(id__in=seleccionadas).update(proyecto=proyecto)

        messages.success(request, f"Se actualizaron las cuadrillas para el proyecto '{proyecto.nombre}'.")
        return redirect('proyectos:panel')

    cuadrillas_asignadas = Cuadrilla.objects.filter(proyecto=proyecto).values_list('id', flat=True)

    return render(request, 'asignar_cuadrillas.html', {
        'proyecto': proyecto,
        'cuadrillas_disponibles': cuadrillas_disponibles,
        'cuadrillas_asignadas': cuadrillas_asignadas
    })


@login_required
@user_passes_test(es_jefe)
def finalizar_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, id=proyecto_id, jefe=request.user)

    if request.method == 'POST':
        # Marcar proyecto como inactivo/finalizado
        proyecto.activo = False
        proyecto.save()

        # Liberar cuadrillas asignadas y notificar a trabajadores
        cuadrillas = Cuadrilla.objects.filter(proyecto=proyecto)
        for c in cuadrillas:
            # Notificar a cada trabajador asignado
            for asig in c.asignaciones.all():
                msg = f"El proyecto '{proyecto.nombre}' ha sido finalizado. Has sido liberado de la cuadrilla '{c.nombre}'."
                crear_notificacion(asig.trabajador, msg)

            # Notificar al líder si existe
            if c.lider:
                crear_notificacion(c.lider, f"La cuadrilla '{c.nombre}' ha sido liberada porque el proyecto '{proyecto.nombre}' finalizó.")

            # Desasignar la cuadrilla del proyecto
            c.proyecto = None
            c.save()

        messages.success(request, f"El proyecto '{proyecto.nombre}' ha sido finalizado y las cuadrillas han sido liberadas.")
        return redirect('proyectos:panel')

    # Si es GET, mostrar confirmación simple (puede mejorarse)
    return render(request, 'confirmar_finalizar_proyecto.html', {'proyecto': proyecto})