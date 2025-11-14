from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth import update_session_auth_hash

from proyectos.models import Proyecto
from .models import (
    Cuadrilla, Asignacion, Rol, Trabajador, TrabajadorPerfil,
    CompetenciaTrabajador, CertificacionTrabajador, ExperienciaTrabajador
)


# -----------------------------------------------------
#  PERMISO: Solo Jefe de Proyecto
# -----------------------------------------------------
def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


# =====================================================
# 1. CREAR CUADRILLA (VERSIÓN MEJORADA Y ESCALABLE)
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

    # =============================================================
    # Atributos dinámicos para la tabla y los filtros
    # =============================================================
    for t in trabajadores:

        # 1) Está ocupado si tiene una asignación en cualquier cuadrilla
        if t.user:
            t.ocupado = Asignacion.objects.filter(trabajador=t.user).exists()
        else:
            t.ocupado = False

        # 2) Perfil opcional (si existe)
        perfil = TrabajadorPerfil.objects.filter(user=t.user).first() if t.user else None

        # 3) Estado lógico
        if perfil:
            t.estado_real = perfil.estado_efectivo
        else:
            t.estado_real = t.estado  # estado simple del modelo Trabajador

        # 4) Certificaciones
        certs = CertificacionTrabajador.objects.filter(trabajador=t)
        t.certificacion_lista = [c.nombre for c in certs]
        t.tiene_certificaciones = certs.exists()

    # =============================================================
    # Filtros dinámicos
    # =============================================================
    especialidades = (
        Trabajador.objects.exclude(especialidad__isnull=True)
        .exclude(especialidad__exact="")
        .values_list("especialidad", flat=True)
        .distinct()
    )

    certificaciones = (
        CertificacionTrabajador.objects.values_list("nombre", flat=True).distinct()
    )

    # =============================================================
    # PROCESAR FORMULARIO
    # =============================================================
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

        # ---------------------------------------------------------
        # Procesar cada trabajador seleccionado
        # ---------------------------------------------------------
        for trabajador_id in seleccionados:

            trabajador = Trabajador.objects.get(id=trabajador_id)

            # Crear user si no tiene
            if not trabajador.user:
                user = trabajador.crear_usuario()
                Trabajador.objects.filter(pk=trabajador.pk).update(user_id=user.id)
                trabajador.user = user

            # === ROL → Protección para evitar errores ===
            rol_id = request.POST.get(f"roles_{trabajador_id}")

            if rol_id and rol_id.isdigit():
                rol = Rol.objects.filter(id=int(rol_id)).first()
            else:
                rol = None

            # Crear asignación
            Asignacion.objects.create(
                trabajador=trabajador.user,
                cuadrilla=cuadrilla,
                rol=rol
            )

        return redirect("personal:detalle_cuadrilla", cuadrilla.id)

    # =============================================================
    # RENDER
    # =============================================================
    return render(request, "cuadrilla_form.html", {
        "proyectos": proyectos,
        "trabajadores": trabajadores,
        "roles": roles,
        "especialidades": especialidades,
        "certificaciones": certificaciones,
    })

# =====================================================
# 2. EDITAR CUADRILLA
# =====================================================
@login_required
@user_passes_test(es_jefe)
def editar_cuadrilla(request, cuadrilla_id):

    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)

    trabajadores = Trabajador.objects.filter(activo=True).select_related("user")
    roles = Rol.objects.all()
    proyectos = Proyecto.objects.filter(jefe=request.user)

    # Mapa: id_user -> asignación
    asignaciones_actuales = {
        str(a.trabajador.id): a
        for a in Asignacion.objects.filter(cuadrilla=cuadrilla)
    }

    # Ligamos asignaciones al objeto trabajador
    for t in trabajadores:
        if t.user and str(t.user.id) in asignaciones_actuales:
            t.asignacion = asignaciones_actuales[str(t.user.id)]
        else:
            t.asignacion = None

    if request.method == "POST":

        # -------------------------
        # Nombre
        # -------------------------
        cuadrilla.nombre = request.POST.get("nombre")

        # -------------------------
        # LÍDER (validación segura)
        # -------------------------
        lider_id = request.POST.get("lider")
        if lider_id and lider_id.isdigit():
            cuadrilla.lider = User.objects.filter(id=int(lider_id)).first()
        else:
            cuadrilla.lider = None

        # -------------------------
        # PROYECTO (validación segura)
        # -------------------------
        proyecto_id = request.POST.get("proyecto")
        if proyecto_id and proyecto_id.isdigit():
            cuadrilla.proyecto = Proyecto.objects.filter(
                id=int(proyecto_id),
                jefe=request.user
            ).first()
        else:
            cuadrilla.proyecto = None

        cuadrilla.save()

        # Lista de trabajadores seleccionados
        seleccionados = set(request.POST.getlist("trabajadores"))

        # Copia de asignaciones para eliminar luego las no usadas
        restantes = asignaciones_actuales.copy()

        # ------------------------------------------------------
        # Crear / actualizar asignaciones
        # ------------------------------------------------------
        for trabajador_id in seleccionados:

            trabajador_obj = Trabajador.objects.get(id=trabajador_id)

            # Crear usuario si no existe
            if not trabajador_obj.user:
                user = trabajador_obj.crear_usuario()
                Trabajador.objects.filter(pk=trabajador_obj.pk).update(user_id=user.id)
                trabajador_obj.user = user

            user = trabajador_obj.user
            clave = str(user.id)

            # Rol seguro
            rol_id = request.POST.get(f"roles_{trabajador_id}")
            if rol_id and rol_id.isdigit():
                rol = Rol.objects.filter(id=int(rol_id)).first()
            else:
                rol = None

            if clave in restantes:
                asign = restantes.pop(clave)
                asign.rol = rol
                asign.save()

            else:
                Asignacion.objects.create(
                    trabajador=user,
                    cuadrilla=cuadrilla,
                    rol=rol
                )

        # ------------------------------------------------------
        # Eliminar asignaciones no seleccionadas
        # ------------------------------------------------------
        for asign in restantes.values():
            asign.delete()

        return redirect("proyectos:panel")

    return render(request, "cuadrilla_editar.html", {
        "cuadrilla": cuadrilla,
        "trabajadores": trabajadores,
        "roles": roles,
        "proyectos": proyectos,
    })
# =====================================================
# 3. DETALLE DE CUADRILLA
# =====================================================
@login_required
@user_passes_test(es_jefe)
def detalle_cuadrilla(request, cuadrilla_id):

    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    asignaciones = Asignacion.objects.filter(cuadrilla=cuadrilla)

    users = [a.trabajador for a in asignaciones]

    perfiles = TrabajadorPerfil.objects.filter(user__in=users)
    competencias = CompetenciaTrabajador.objects.filter(trabajador_id__in=[u.id for u in users])
    certificaciones = CertificacionTrabajador.objects.filter(trabajador_id__in=[u.id for u in users])
    experiencias = ExperienciaTrabajador.objects.filter(trabajador_id__in=[u.id for u in users])

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
# 4. DETALLE INDIVIDUAL DE TRABAJADOR
# =====================================================
@login_required
@user_passes_test(es_jefe)
def detalle_trabajador(request, trabajador_id):

    trabajador = get_object_or_404(Trabajador, id=trabajador_id)

    # Perfil (opcional)
    perfil = TrabajadorPerfil.objects.filter(user=trabajador.user).first()

    # Competencias
    competencias = CompetenciaTrabajador.objects.filter(trabajador=trabajador)

    # Certificaciones
    certificaciones = CertificacionTrabajador.objects.filter(trabajador=trabajador)

    # Experiencias laborales
    experiencias = ExperienciaTrabajador.objects.filter(trabajador=trabajador)

    # Asignaciones actuales (en qué cuadrilla está)
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
# 5. CAMBIO DE ESTADO DEL TRABAJADOR
# =====================================================
@login_required
@user_passes_test(es_jefe)
def editar_estado_trabajador(request, trabajador_id):

    # Buscar trabajador por ID (NO perfil)
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)

    # Tomar perfil opcional
    perfil = TrabajadorPerfil.objects.filter(user=trabajador.user).first()

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")

        # El estado real del trabajador está en Trabajador.estado
        if nuevo_estado in ["disponible", "asignado", "vacaciones", "licencia", "inactivo"]:
            trabajador.estado = nuevo_estado
            trabajador.save()

        return redirect("personal:detalle_trabajador", trabajador.id)

    return render(request, "editar_estado_trabajador.html", {
        "trabajador": trabajador,
        "perfil": perfil,
    })

# =====================================================
# 6. CAMBIO DE CONTRASEÑA PERSONALIZADO
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
