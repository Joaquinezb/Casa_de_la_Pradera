from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required


@login_required(login_url='/usuarios/login/')
def dashboard_redirect(request):
    user = request.user

    # Jefe de proyecto → panel de proyectos
    if user.groups.filter(name='JefeProyecto').exists():
        return redirect('proyectos:panel')

    # Líder de cuadrilla → vista futura de líder
    elif user.groups.filter(name='LiderCuadrilla').exists():
        return redirect('tareas:bitacoras')  # Ajusta si no existe aún

    # Trabajador → asignaciones personales
    else:
        return redirect('tareas:asignaciones')  # Ajusta si no existe aún
def index(request):
    # Mostrar una página pública si el usuario NO está autenticado (sin navbar)
    if not request.user.is_authenticated:
        return render(request, 'index_public.html')
    # Usuario autenticado: mostrar la vista que extiende `base.html`
    return render(request, 'index.html')
