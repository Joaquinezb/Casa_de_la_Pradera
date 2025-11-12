from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Proyecto
from .forms import ProyectoForm
from personal.models import Cuadrilla
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
    proyectos = Proyecto.objects.filter(jefe=request.user).prefetch_related('cuadrillas')
    data = []

    for p in proyectos:
        cuadrillas = Cuadrilla.objects.filter(proyecto=p)
        data.append({
            'proyecto': p,
            'cuadrillas': cuadrillas
        })

    return render(request, 'panel.html', {'data': data})

@login_required
@user_passes_test(es_jefe)
def asignar_cuadrillas(request, proyecto_id):
    proyecto = Proyecto.objects.get(id=proyecto_id, jefe=request.user)
    cuadrillas_disponibles = Cuadrilla.objects.all()

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