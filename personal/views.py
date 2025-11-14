from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from proyectos.models import Proyecto
from .models import Cuadrilla, Asignacion, Rol, TrabajadorPerfil, Competencia, Certificacion, Experiencia

def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


@login_required
@user_passes_test(es_jefe)
def crear_cuadrilla(request):
    proyectos = Proyecto.objects.filter(jefe=request.user)
    trabajadores = User.objects.exclude(groups__name__in=['JefeProyecto'])
    roles = Rol.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        proyecto_id = request.POST.get('proyecto')
        lider_id = request.POST.get('lider')
        seleccionados = request.POST.getlist('trabajadores')
        roles_seleccionados = request.POST.getlist('roles')

        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        lider = User.objects.filter(id=lider_id).first()

        cuadrilla = Cuadrilla.objects.create(
            nombre=nombre,
            proyecto=proyecto,
            lider=lider
        )

        for i, trabajador_id in enumerate(seleccionados):
            trabajador = User.objects.get(id=trabajador_id)
            rol = Rol.objects.filter(id=roles_seleccionados[i]).first()
            Asignacion.objects.create(
                trabajador=trabajador,
                cuadrilla=cuadrilla,
                rol=rol
            )

        return redirect('proyectos:panel')

    return render(request, 'cuadrilla_form.html', {
        'proyectos': proyectos,
        'trabajadores': trabajadores,
        'roles': roles
    })


@login_required
@user_passes_test(es_jefe)
def editar_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    trabajadores = User.objects.exclude(groups__name__in=['JefeProyecto'])
    roles = Rol.objects.all()

    if request.method == 'POST':
        cuadrilla.nombre = request.POST.get('nombre')
        lider_id = request.POST.get('lider')
        cuadrilla.lider = User.objects.filter(id=lider_id).first()
        cuadrilla.save()

        Asignacion.objects.filter(cuadrilla=cuadrilla).delete()

        seleccionados = request.POST.getlist('trabajadores')
        roles_seleccionados = request.POST.getlist('roles')

        for i, trabajador_id in enumerate(seleccionados):
            trabajador = User.objects.get(id=trabajador_id)
            rol = Rol.objects.filter(id=roles_seleccionados[i]).first()
            Asignacion.objects.create(
                trabajador=trabajador,
                cuadrilla=cuadrilla,
                rol=rol
            )

        return redirect('proyectos:panel')

    return render(request, 'cuadrilla_editar.html', {
        'cuadrilla': cuadrilla,
        'trabajadores': trabajadores,
        'roles': roles,
        'asignaciones': cuadrilla.asignaciones.all()
    })


@login_required
@user_passes_test(es_jefe)
def detalle_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    asignaciones = Asignacion.objects.filter(cuadrilla=cuadrilla)

    # Extraer los users involucrados
    trabajadores = [a.trabajador for a in asignaciones]

    # Mapear perfiles, competencias, certificaciones y experiencias
    perfiles = TrabajadorPerfil.objects.filter(user__in=trabajadores)
    competencias = Competencia.objects.filter(trabajador__in=trabajadores)
    certificaciones = Certificacion.objects.filter(trabajador__in=trabajadores)
    experiencias = Experiencia.objects.filter(trabajador__in=trabajadores)

    # Creamos estructuras fáciles de acceder desde la plantilla
    perfil_map = {p.user_id: p for p in perfiles}

    comp_map = {}
    for c in competencias:
        comp_map.setdefault(c.trabajador_id, []).append(c)

    cert_map = {}
    for c in certificaciones:
        cert_map.setdefault(c.trabajador_id, []).append(c)

    exp_map = {}
    for e in experiencias:
        exp_map.setdefault(e.trabajador_id, []).append(e)

    return render(request, 'detalle_cuadrilla.html', {
        'cuadrilla': cuadrilla,
        'asignaciones': asignaciones,
        'perfil_map': perfil_map,
        'comp_map': comp_map,
        'cert_map': cert_map,
        'exp_map': exp_map,
    })
