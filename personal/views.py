from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth import update_session_auth_hash
from proyectos.models import Proyecto
from .models import Cuadrilla, Asignacion, Rol, TrabajadorPerfil, Competencia, Certificacion, Experiencia, Trabajador

def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


@login_required
@user_passes_test(es_jefe)
def crear_cuadrilla(request):
    proyectos = Proyecto.objects.filter(jefe=request.user)
    # Obtener lista de trabajadores desde el modelo `Trabajador` (entidad principal)
    trabajadores = Trabajador.objects.filter(activo=True)
    roles = Rol.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        proyecto_id = request.POST.get('proyecto')
        lider_id = request.POST.get('lider')
        seleccionados = request.POST.getlist('trabajadores')

        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        lider = None
        if lider_id:
            lider = User.objects.filter(id=lider_id).first()

        cuadrilla = Cuadrilla.objects.create(
            nombre=nombre,
            proyecto=proyecto,
            lider=lider
        )

        # Para cada trabajador seleccionado, leemos el rol específico enviado
        # en el campo `roles_<trabajador_id>` para evitar desalineación de listas
        for trabajador_id in seleccionados:
            # trabajador_id aquí corresponde al id del modelo Trabajador
            trabajador_obj = Trabajador.objects.get(id=trabajador_id)
            # Asegurar que exista el User vinculado; crear si hace falta
            if not trabajador_obj.user:
                user = trabajador_obj.crear_usuario()
                # asociar el user al trabajador sin reentrar signals
                Trabajador.objects.filter(pk=trabajador_obj.pk).update(user_id=user.id)
                trabajador_obj.user = user

            user = trabajador_obj.user

            role_field = request.POST.get(f'roles_{trabajador_id}')
            rol = None
            if role_field:
                try:
                    rol = Rol.objects.filter(id=int(role_field)).first()
                except (ValueError, TypeError):
                    rol = None

            Asignacion.objects.create(
                trabajador=user,
                cuadrilla=cuadrilla,
                rol=rol
            )

        # Después de editar, redirigimos al detalle de la cuadrilla para que
        # el usuario pueda verla/volver a editar fácilmente incluso si quedó
        # sin proyecto asignado.
        return redirect('personal:detalle_cuadrilla', cuadrilla.id)

    return render(request, 'cuadrilla_form.html', {
        'proyectos': proyectos,
        'trabajadores': trabajadores,
        'roles': roles
    })


@login_required
@user_passes_test(es_jefe)
def editar_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    trabajadores = Trabajador.objects.filter(activo=True)
    roles = Rol.objects.all()
    proyectos = Proyecto.objects.filter(jefe=request.user)

    if request.method == 'POST':
        # Actualizar datos básicos
        cuadrilla.nombre = request.POST.get('nombre')
        lider_id = request.POST.get('lider')
        cuadrilla.lider = None
        if lider_id:
            cuadrilla.lider = User.objects.filter(id=lider_id).first()

        # Permitir reasignar la cuadrilla a otro proyecto del jefe
        proyecto_id = request.POST.get('proyecto')
        if proyecto_id:
            cuadrilla.proyecto = Proyecto.objects.filter(id=proyecto_id, jefe=request.user).first()
        else:
            cuadrilla.proyecto = None

        cuadrilla.save()

        # Gestión incremental de asignaciones: actualizar roles, añadir o eliminar trabajadores
        seleccionados = set(request.POST.getlist('trabajadores'))

        # Mapa de asignaciones actuales: llave como string del id del trabajador
        actuales_qs = Asignacion.objects.filter(cuadrilla=cuadrilla)
        actuales = {str(a.trabajador.id): a for a in actuales_qs}

        # Añadir o actualizar los seleccionados
        for trabajador_id in seleccionados:
            trabajador_obj = Trabajador.objects.get(id=trabajador_id)
            # Asegurar user creado
            if not trabajador_obj.user:
                user = trabajador_obj.crear_usuario()
                Trabajador.objects.filter(pk=trabajador_obj.pk).update(user_id=user.id)
                trabajador_obj.user = user

            user = trabajador_obj.user

            role_field = request.POST.get(f'roles_{trabajador_id}')
            rol = None
            if role_field:
                try:
                    rol = Rol.objects.filter(id=int(role_field)).first()
                except (ValueError, TypeError):
                    rol = None

            # clave en `actuales` es str(user.id) porque actuales fue construido desde Asignacion.trabajador (User)
            clave_user_id = str(user.id)

            if clave_user_id in actuales:
                asign = actuales[clave_user_id]
                # Actualizar rol si cambió
                if (asign.rol and rol and asign.rol.id != rol.id) or (asign.rol is None and rol is not None) or (asign.rol is not None and rol is None):
                    asign.rol = rol
                    asign.save()
                actuales.pop(clave_user_id, None)
            else:
                Asignacion.objects.create(trabajador=user, cuadrilla=cuadrilla, rol=rol)

        # Los que quedaron en `actuales` no fueron seleccionados ahora -> eliminarlos
        for rest_id, asign in list(actuales.items()):
            asign.delete()

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


# ------------------------------------------------------------------
# Código comentado: Vista personalizada de cambio de contraseña
# - Este bloque está listo para habilitar cuando quieras probar el
#   flujo de forzado de cambio de password (password inicial = RUT).
# - Para habilitar: descomentar la clase, importar en `personal/urls.py`
#   y registrar la ruta `password_change` apuntando a esta vista.
# ------------------------------------------------------------------
class TrabajadorPasswordChangeView(PasswordChangeView):
    """Sobrescribe form_valid para marcar password_inicial=False en el Trabajador

    Esta vista mantiene la sesión del usuario después del cambio de contraseña
    y marca el flag `password_inicial=False` en el modelo `Trabajador`.
    """

    def form_valid(self, form):
        response = super().form_valid(form)

        trabajador = getattr(self.request.user, 'trabajador_profile', None)
        if trabajador:
            trabajador.password_inicial = False
            trabajador.save()

        update_session_auth_hash(self.request, form.user)
        return response
