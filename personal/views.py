from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView

from proyectos.models import Proyecto
from .models import (
    Cuadrilla, Asignacion, Rol, TrabajadorPerfil,
    Competencia, Certificacion, Experiencia, Trabajador
)


# ============================================================
# Helpers y utilidades internas
# ============================================================

def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


def asegurar_usuario(trabajador: Trabajador):
    """
    Garantiza que un Trabajador tenga un User asociado.
    Si no tiene, crea uno; si tiene, solo lo retorna.
    Maneja todos los errores de forma segura.
    """
    if trabajador.user:
        return trabajador.user

    try:
        user = trabajador.crear_usuario()
        Trabajador.objects.filter(pk=trabajador.pk).update(user_id=user.id)
        trabajador.user = user
        return user
    except Exception as e:
        raise ValueError(f"Error creando usuario para trabajador {trabajador.rut}: {str(e)}")


def obtener_roles_segun_post(request, trabajador_id):
    """
    Extrae el rol seleccionado en el formulario para un trabajador.
    Si es inválido o no viene, retorna None.
    """
    role_field = request.POST.get(f'roles_{trabajador_id}')
    if not role_field:
        return None
    try:
        return Rol.objects.filter(id=int(role_field)).first()
    except:
        return None


def asignaciones_por_usuario(cuadrilla):
    """
    Retorna un dict rápido:
        { user.id : asignacion }
    para acceso O(1).
    """
    return {a.trabajador.id: a for a in cuadrilla.asignaciones.select_related('trabajador', 'rol')}


def precargar_datos_trabajadores(trabajadores, asign_map):
    """
    Agrega la propiedad temporal .asignacion a cada Trabajador
    para simplificar los templates.
    """
    for t in trabajadores:
        t.asignacion = asign_map.get(t.user.id) if t.user else None
    return trabajadores


# ============================================================
# Crear cuadrilla
# ============================================================

@login_required
@user_passes_test(es_jefe)
def crear_cuadrilla(request):
    proyectos = Proyecto.objects.filter(jefe=request.user)
    trabajadores = Trabajador.objects.filter(activo=True)
    roles = Rol.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        proyecto_id = request.POST.get('proyecto')
        lider_id = request.POST.get('lider')
        seleccionados = request.POST.getlist('trabajadores')

        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        lider = User.objects.filter(id=lider_id).first() if lider_id else None

        cuadrilla = Cuadrilla.objects.create(
            nombre=nombre,
            proyecto=proyecto,
            lider=lider
        )

        # Crear asignaciones
        for trabajador_id in seleccionados:
            trabajador_obj = get_object_or_404(Trabajador, id=trabajador_id)
            user = asegurar_usuario(trabajador_obj)
            rol = obtener_roles_segun_post(request, trabajador_id)

            Asignacion.objects.create(
                trabajador=user,
                cuadrilla=cuadrilla,
                rol=rol
            )

        return redirect('personal:detalle_cuadrilla', cuadrilla.id)

    return render(request, 'cuadrilla_form.html', {
        'proyectos': proyectos,
        'trabajadores': trabajadores,
        'roles': roles
    })


# ============================================================
# Editar cuadrilla
# ============================================================

@login_required
@user_passes_test(es_jefe)
def editar_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    trabajadores = Trabajador.objects.filter(activo=True).select_related('user')
    roles = Rol.objects.all()
    proyectos = Proyecto.objects.filter(jefe=request.user)

    # Pre-cargar asignaciones en un mapa
    asign_map = asignaciones_por_usuario(cuadrilla)
    trabajadores = precargar_datos_trabajadores(trabajadores, asign_map)

    if request.method == 'POST':
        cuadrilla.nombre = request.POST.get('nombre')

        lider_id = request.POST.get('lider')
        cuadrilla.lider = User.objects.filter(id=lider_id).first() if lider_id else None

        proyecto_id = request.POST.get('proyecto')
        cuadrilla.proyecto = Proyecto.objects.filter(id=proyecto_id, jefe=request.user).first() if proyecto_id else None
        cuadrilla.save()

        seleccionados = set(request.POST.getlist('trabajadores'))

        actuales_qs = cuadrilla.asignaciones.all()
        actuales = {str(a.trabajador.id): a for a in actuales_qs}

        for trabajador_id in seleccionados:
            trabajador_obj = get_object_or_404(Trabajador, id=trabajador_id)
            user = asegurar_usuario(trabajador_obj)
            rol = obtener_roles_segun_post(request, trabajador_id)

            key = str(user.id)

            if key in actuales:
                asign = actuales[key]
                asign.rol = rol
                asign.save()
                actuales.pop(key)
            else:
                Asignacion.objects.create(trabajador=user, cuadrilla=cuadrilla, rol=rol)

        # Eliminar asignaciones desmarcadas
        for asign in actuales.values():
            asign.delete()

        return redirect('proyectos:panel')

    return render(request, 'cuadrilla_editar.html', {
        'cuadrilla': cuadrilla,
        'trabajadores': trabajadores,
        'roles': roles,
        'proyectos': proyectos,
    })


# ============================================================
# Detalle cuadrilla
# ============================================================

@login_required
@user_passes_test(es_jefe)
def detalle_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    asignaciones = (
        Asignacion.objects
        .filter(cuadrilla=cuadrilla)
        .select_related("trabajador", "rol")
    )

    usuarios = [a.trabajador for a in asignaciones]

    perfiles = TrabajadorPerfil.objects.filter(user__in=usuarios)
    perfil_map = {p.user_id: p for p in perfiles}

    comp_map = {}
    for c in Competencia.objects.filter(trabajador__in=usuarios):
        comp_map.setdefault(c.trabajador_id, []).append(c)

    cert_map = {}
    for c in Certificacion.objects.filter(trabajador__in=usuarios):
        cert_map.setdefault(c.trabajador_id, []).append(c)

    exp_map = {}
    for e in Experiencia.objects.filter(trabajador__in=usuarios):
        exp_map.setdefault(e.trabajador_id, []).append(e)

    return render(request, 'detalle_cuadrilla.html', {
        'cuadrilla': cuadrilla,
        'asignaciones': asignaciones,
        'perfil_map': perfil_map,
        'comp_map': comp_map,
        'cert_map': cert_map,
        'exp_map': exp_map,
    })


# ============================================================
# Cambio de contraseña
# ============================================================

class TrabajadorPasswordChangeView(PasswordChangeView):
    def form_valid(self, form):
        response = super().form_valid(form)

        trabajador = getattr(self.request.user, 'trabajador_profile', None)
        if trabajador:
            trabajador.password_inicial = False
            trabajador.save()

        update_session_auth_hash(self.request, form.user)
        return response


# ============================================================
# Cambio estado manual trabajador
# ============================================================


@login_required
@user_passes_test(es_jefe)
def editar_estado_trabajador(request, trabajador_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado_manual")

        if nuevo_estado in ['disponible', 'no_disponible', 'licencia', 'vacaciones']:
            perfil = getattr(trabajador.user, "perfil_trabajador", None)
            if perfil:
                perfil.estado_manual = nuevo_estado
                perfil.save()

        return redirect('personal:detalle_cuadrilla', trabajador.cuadrilla_set.first().id)

    perfil = getattr(trabajador.user, "perfil_trabajador", None)

    return render(request, "editar_estado_trabajador.html", {
        "trabajador": trabajador,
        "perfil": perfil,
    })