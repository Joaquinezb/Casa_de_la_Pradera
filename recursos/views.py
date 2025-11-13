from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Recurso
from personal.models import Cuadrilla
from proyectos.models import Proyecto

#Funciones auxiliares
def es_lider(user):
    return user.groups.filter(name='LiderCuadrilla').exists()

def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


#Vista para líderes de cuadrilla
@login_required
@user_passes_test(es_lider)
def inventario_lider(request):
    cuadrillas = Cuadrilla.objects.filter(lider=request.user)
    recursos = Recurso.objects.filter(cuadrilla__in=cuadrillas)
    return render(request, 'inventario.html', {
        'recursos': recursos,
        'vista': 'lider',
    })


#Vista para jefes de proyecyto
@login_required
@user_passes_test(es_jefe)
def inventario_jefe(request):
    proyectos = Proyecto.objects.filter(jefe=request.user)
    recursos = Recurso.objects.filter(cuadrilla__proyecto__in=proyectos)
    return render(request, 'inventario.html', {
        'recursos': recursos,
        'vista': 'jefe',
    })
