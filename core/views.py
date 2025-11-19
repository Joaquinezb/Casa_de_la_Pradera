from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def dashboard_redirect(request):
    user = request.user
    if user.groups.filter(name='JefeProyecto').exists():
        return redirect('proyectos:panel')
    elif user.groups.filter(name='LiderCuadrilla').exists():
        return redirect('tareas:bitacoras')
    else:
        return redirect('tareas:asignaciones')

@login_required
def dashboard_redirect(request):
    user = request.user
    if user.groups.filter(name='JefeProyecto').exists():
        return redirect('proyectos:panel')
    elif user.groups.filter(name='LiderCuadrilla').exists():
        return redirect('tareas:bitacoras')
    else:
        return redirect('tareas:asignaciones')

@login_required(login_url='/usuarios/login/')
def index(request):
    return render(request, 'index.html')