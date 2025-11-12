from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

def es_lider(user):
    return user.groups.filter(name='LiderCuadrilla').exists()

@login_required
@user_passes_test(es_lider)
def bitacoras_view(request):
    return render(request, 'bitacoras.html')

@login_required
def asignaciones_view(request):
    # cualquier usuario autenticado puede verla
    return render(request, 'asignaciones.html')
