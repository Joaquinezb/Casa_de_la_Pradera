from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth import update_session_auth_hash

from proyectos.models import Proyecto
from .models import (
    Cuadrilla, Asignacion, Rol, Trabajador, TrabajadorPerfil,
    CompetenciaTrabajador, CertificacionTrabajador, ExperienciaTrabajador,
    Notificacion,
)
from .utils_notificaciones import crear_notificacion


# -----------------------------------------------------
#  PERMISO: Solo Jefe de Proyecto
# -----------------------------------------------------
def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


# =====================================================
# 1. CREAR CUADRILLA (CORREGIDO)
# =====================================================
@login_required
@user_passes_test(es_jefe)
def crear_cuadrilla(request):

    proyectos = Proyecto.objects.filter(jefe=request.user)

    trabajadores = (
        Trabajador.objects.filter(activo=True)
        .select_related("user")
        .prefetch_related("certificaciones_trabajador")
    )

    roles = Rol.objects.all()

    # Enriquecer trabajadores
    for t in trabajadores:

        t.ocupado = Asignacion.objects.filter(trabajador=t.user).exists() if t.user else False

        perfil = TrabajadorPerfil.objects.filter(user=t.user).first() if t.user else None
        t.estado_real = perfil.estado_efectivo if perfil else t.estado

        certs = CertificacionTrabajador.objects.filter(trabajador=t)
        t.certificacion_lista = [c.nombre for c in certs]
        t.tiene_certificaciones = certs.exists()

    especialidades = (
        Trabajador.objects.exclude(especialidad__isnull=True)
        .exclude(especialidad__exact="")
        .values_list("especialidad", flat=True)
        .distinct()
    )

    certificaciones = CertificacionTrabajador.objects.values_list("nombre", flat=True).distinct()

    if request.method == "POST":

        nombre = request.POST.get("nombre")
        proyecto_id = request.POST.get("proyecto")
        lider_id = request.POST.get("lider")
        seleccionados = request.POST.getlist("trabajadores")

        proyecto = get_object_or_404(Proyecto, id=proyecto_id)

        cuadrilla = Cuadrilla.objects.create(
            nombre=nombre,
            proyecto=proyecto,
            lider=User.objects.filter(id=lider_id).first() if lider_id else None
        )

        trabajadores_asignados = []

        for trabajador_id in seleccionados:

            trabajador = Trabajador.objects.get(id=trabajador_id)

            if not trabajador.user:
                user = trabajador.crear_usuario()
                Trabajador.objects.filter(pk=trabajador.pk).update(user_id=user.id)
                trabajador.user = user

            rol_id = request.POST.get(f"roles_{trabajador_id}")
            rol = Rol.objects.filter(id=rol_id).first() if rol_id and rol_id.isdigit() else None

            Asignacion.objects.create(
                trabajador=trabajador.user,
                cuadrilla=cuadrilla,
                rol=rol
            )

            trabajadores_asignados.append((trabajador.user, rol))

        # NOTIFICACIONES
        for user, rol in trabajadores_asignados:
            msg = f"Has sido asignado a la cuadrilla '{cuadrilla.nombre}'"
            if cuadrilla.proyecto:
                msg += f" en el proyecto '{cuadrilla.proyecto.nombre}'."
            else:
                msg += "."
            if rol:
                msg += f" Rol: {rol.nombre}."
            crear_notificacion(user, msg)

        if cuadrilla.lider:
            crear_notificacion(
                cuadrilla.lider,
                f"Eres líder de la nueva cuadrilla '{cuadrilla.nombre}'."
            )

        return redirect("personal:detalle_cuadrilla", cuadrilla.id)

    return render(request, "cuadrilla_form.html", {
        "proyectos": proyectos,
        "trabajadores": trabajadores,
        "roles": roles,
        "especialidades": especialidades,
        "certificaciones": certificaciones,
    })


# =====================================================
# 2. EDITAR CUADRILLA (CORREGIDO)
# =====================================================
@login_required
@user_passes_test(es_jefe)
def editar_cuadrilla(request, cuadrilla_id):

    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    trabajadores = Trabajador.objects.filter(activo=True).select_related("user")
    roles = Rol.objects.all()
    proyectos = Proyecto.objects.filter(jefe=request.user)

    asignaciones_actuales = {
        str(a.trabajador.id): a for a in Asignacion.objects.filter(cuadrilla=cuadrilla)
    }

    for t in trabajadores:
        t.asignacion = asignaciones_actuales.get(str(t.user.id)) if t.user else None

    if request.method == "POST":

        lider_anterior = cuadrilla.lider
        proyecto_anterior = cuadrilla.proyecto

        cuadrilla.nombre = request.POST.get("nombre")

        lider_id = request.POST.get("lider")
        cuadrilla.lider = User.objects.filter(id=lider_id).first() if lider_id and lider_id.isdigit() else None

        proyecto_id = request.POST.get("proyecto")
        cuadrilla.proyecto = Proyecto.objects.filter(
            id=proyecto_id,
            jefe=request.user
        ).first() if proyecto_id and proyecto_id.isdigit() else None

        cuadrilla.save()

        seleccionados = set(request.POST.getlist("trabajadores"))
        restantes = asignaciones_actuales.copy()

        agregados = []
        removidos = []
        cambios_rol = []

        for trabajador_id in seleccionados:

            trabajador_obj = Trabajador.objects.get(id=trabajador_id)

            if not trabajador_obj.user:
                user = trabajador_obj.crear_usuario()
                Trabajador.objects.filter(pk=trabajador_obj.pk).update(user_id=user.id)
                trabajador_obj.user = user

            user = trabajador_obj.user
            clave = str(user.id)

            rol_id = request.POST.get(f"roles_{trabajador_id}")
            rol = Rol.objects.filter(id=rol_id).first() if rol_id and rol_id.isdigit() else None

            if clave in restantes:
                asign = restantes.pop(clave)
                rol_anterior = asign.rol

                if rol_anterior != rol:
                    cambios_rol.append((user, cuadrilla, rol))

                asign.rol = rol
                asign.save()

            else:
                Asignacion.objects.create(
                    trabajador=user,
                    cuadrilla=cuadrilla,
                    rol=rol
                )
                agregados.append((user, rol))

        for asign in restantes.values():
            removidos.append((asign.trabajador, cuadrilla))
            asign.delete()

        # NOTIFICACIONES
        if lider_anterior != cuadrilla.lider:
            if lider_anterior:
                crear_notificacion(
                    lider_anterior,
                    f"Ya no eres líder de la cuadrilla '{cuadrilla.nombre}'."
                )
            if cuadrilla.lider:
                crear_notificacion(
                    cuadrilla.lider,
                    f"Has sido asignado como líder de la cuadrilla '{cuadrilla.nombre}'."
                )

        if proyecto_anterior != cuadrilla.proyecto:
            for asig in Asignacion.objects.filter(cuadrilla=cuadrilla):
                msg = f"La cuadrilla '{cuadrilla.nombre}' ha cambiado de proyecto."
                if cuadrilla.proyecto:
                    msg += f" Nuevo proyecto: {cuadrilla.proyecto.nombre}."
                crear_notificacion(asig.trabajador, msg)

        for user, rol in agregados:
            msg = f"Has sido agregado a la cuadrilla '{cuadrilla.nombre}'."
            if rol:
                msg += f" Rol: {rol.nombre}."
            crear_notificacion(user, msg)

        for user, cuad in removidos:
            crear_notificacion(user, f"Has sido removido de la cuadrilla '{cuad.nombre}'.")

        for user, cuad, rol in cambios_rol:
            if rol:
                msg = f"Tu rol en la cuadrilla '{cuad.nombre}' ahora es '{rol.nombre}'."
            else:
                msg = f"Tu rol en la cuadrilla '{cuad.nombre}' ha sido removido."
            crear_notificacion(user, msg)

        return redirect("proyectos:panel")

    return render(request, "cuadrilla_editar.html", {
        "cuadrilla": cuadrilla,
        "trabajadores": trabajadores,
        "roles": roles,
        "proyectos": proyectos,
    })


# =====================================================
# 3. DETALLE CUADRILLA (SIN CAMBIOS)
# =====================================================
def detalle_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    asignaciones = Asignacion.objects.filter(cuadrilla=cuadrilla)

    users = [a.trabajador for a in asignaciones]

    perfiles = TrabajadorPerfil.objects.filter(user__in=users)
    competencias = CompetenciaTrabajador.objects.filter(trabajador__in=[u.id for u in users])
    certificaciones = CertificacionTrabajador.objects.filter(trabajador__in=[u.id for u in users])
    experiencias = ExperienciaTrabajador.objects.filter(trabajador__in=[u.id for u in users])

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

    return render(request, "detalle_cuadrilla.html", {
        "cuadrilla": cuadrilla,
        "asignaciones": asignaciones,
        "perfil_map": perfil_map,
        "comp_map": comp_map,
        "cert_map": cert_map,
        "exp_map": exp_map,
    })


# =====================================================
# 4. DETALLE TRABAJADOR (CORREGIDO)
# =====================================================
def detalle_trabajador(request, trabajador_id):

    trabajador = get_object_or_404(Trabajador, id=trabajador_id)

    perfil = TrabajadorPerfil.objects.filter(user=trabajador.user).first()
    competencias = CompetenciaTrabajador.objects.filter(trabajador=trabajador)
    certificaciones = CertificacionTrabajador.objects.filter(trabajador=trabajador)
    experiencias = ExperienciaTrabajador.objects.filter(trabajador=trabajador)

    asignaciones = Asignacion.objects.filter(trabajador=trabajador.user)

    return render(request, "detalle_trabajador.html", {
        "trabajador": trabajador,
        "perfil": perfil,
        "competencias": competencias,
        "certificaciones": certificaciones,
        "experiencias": experiencias,
        "asignaciones": asignaciones,
    })


# =====================================================
# 5. EDITAR ESTADO TRABAJADOR
# =====================================================
def editar_estado_trabajador(request, trabajador_id):

    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    perfil = TrabajadorPerfil.objects.filter(user=trabajador.user).first()

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")

        if nuevo_estado in ["disponible", "asignado", "vacaciones", "licencia", "inactivo"]:
            trabajador.estado = nuevo_estado
            trabajador.save()

            if trabajador.user:
                crear_notificacion(
                    trabajador.user,
                    f"Tu estado laboral ha cambiado a: {nuevo_estado}."
                )

        return redirect("personal:detalle_trabajador", trabajador.id)

    return render(request, "editar_estado_trabajador.html", {
        "trabajador": trabajador,
        "perfil": perfil,
    })


# =====================================================
# 6. NOTIFICACIONES
# =====================================================
@login_required
def mis_notificaciones(request):

    notifs = request.user.notificaciones.all()
    return render(request, "mis_notificaciones.html", {
        "notifs": notifs,
    })


@login_required
def marcar_todas_leidas(request):

    request.user.notificaciones.filter(leida=False).update(leida=True)
    return redirect("personal:mis_notificaciones")


# =====================================================
# 7. PASSWORD CHANGE VIEW
# =====================================================
class TrabajadorPasswordChangeView(PasswordChangeView):

    def form_valid(self, form):
        response = super().form_valid(form)

        trabajador = getattr(self.request.user, 'trabajador_profile', None)
        if trabajador:
            trabajador.password_inicial = False
            trabajador.save()

        update_session_auth_hash(self.request, form.user)
        return response
