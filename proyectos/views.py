from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Proyecto
from .forms import ProyectoForm
from personal.models import Cuadrilla
from django.db.models import Q
from personal.utils_notificaciones import crear_notificacion
from django.contrib import messages

def es_jefe(user):
    return user.groups.filter(name='JefeProyecto').exists()


@login_required
@user_passes_test(es_jefe)
def crear_proyecto(request):
    if request.method == 'POST':
        form = ProyectoForm(request.POST)
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.jefe = request.user  # asigna automáticamente el jefe
            proyecto.created_by = request.user
            proyecto.save()
            return redirect('proyectos:panel')
    else:
        form = ProyectoForm()
    return render(request, 'nuevo_proyecto.html', {'form': form})


@login_required
@user_passes_test(es_jefe)
def editar_proyecto(request, proyecto_id):
    """Editar un proyecto existente. Solo accesible por el jefe del proyecto."""
    proyecto = get_object_or_404(Proyecto, id=proyecto_id, jefe=request.user)

    if request.method == 'POST':
        # Para evitar problemas con campos fecha obligatorios que no se muestran
        # en el formulario (los mostramos como texto), clonamos POST y añadimos
        # los valores actuales de las fechas para que la validación del form pase.
        data = request.POST.copy()
        data['fecha_inicio'] = proyecto.fecha_inicio.isoformat()
        data['fecha_termino'] = proyecto.fecha_termino.isoformat() if proyecto.fecha_termino else ''

        form = ProyectoForm(data, instance=proyecto)
        if form.is_valid():
            proyecto_obj = form.save(commit=False)
            # Forzar que las fechas no cambien aunque alguien manipule el payload
            proyecto_obj.fecha_inicio = proyecto.fecha_inicio
            proyecto_obj.fecha_termino = proyecto.fecha_termino
            proyecto_obj.save()
            messages.success(request, f"Proyecto '{proyecto.nombre}' actualizado correctamente.")
            return redirect('proyectos:panel')
    else:
        form = ProyectoForm(instance=proyecto)

    return render(request, 'editar_proyecto.html', {'form': form, 'proyecto': proyecto})


@login_required
def panel_proyectos(request):
    """Panel de proyectos con visibilidad según rol:

    - JefeProyecto: ve todos sus proyectos (activos y finalizados), puede crear/editar/asignar.
    - LiderCuadrilla: ve proyectos donde lidera al menos una cuadrilla; puede ver todas las cuadrillas del proyecto (solo lectura).
    - Trabajador: ve solo el proyecto asociado a su cuadrilla actual (info básica).
    """
    user = request.user

    # JefeProyecto: ver todos los proyectos y sus cuadrillas (lectura completa).
    # Las acciones de edición/creación siguen restringidas por otras vistas.
    if user.groups.filter(name='JefeProyecto').exists():
        proyectos_activos = Proyecto.objects.filter(activo=True).prefetch_related('cuadrillas')
        proyectos_finalizados = Proyecto.objects.filter(activo=False).prefetch_related('cuadrillas')

        data = []
        for p in proyectos_activos:
            cuadrillas = Cuadrilla.objects.filter(proyecto=p)
            # Construir lista de cuadrillas con permisos por item
            cuad_list = []
            for c in cuadrillas:
                cuad_list.append({
                    'cuadrilla': c,
                    'can_edit': (p.jefe_id == user.id) or (c.lider_id == user.id),
                })

            data.append({
                'proyecto': p,
                'cuadrillas': cuad_list,
                'can_edit_project': (p.jefe_id == user.id),
                'can_assign': (p.jefe_id == user.id),
                'can_finalize': (p.jefe_id == user.id),
                'can_create_cuadrilla': (p.jefe_id == user.id),
            })

        finalizados = []
        for p in proyectos_finalizados:
            cuadrillas = Cuadrilla.objects.filter(proyecto=p)
            cuad_list = []
            for c in cuadrillas:
                cuad_list.append({
                    'cuadrilla': c,
                    'can_edit': (p.jefe_id == user.id) or (c.lider_id == user.id),
                })
            finalizados.append({'proyecto': p, 'cuadrillas': cuad_list, 'can_edit_project': (p.jefe_id == user.id)})

        # Mostrar todas las cuadrillas sin proyecto
        cuadrillas_sin_proyecto = []
        for c in Cuadrilla.objects.filter(proyecto__isnull=True):
            cuadrillas_sin_proyecto.append({
                'cuadrilla': c,
                'can_edit': (c.lider_id == user.id),
                'can_disolver': (c.lider_id == user.id),
            })

        # Construir lista deduplicada de jefes para el selector
        jefes_map = {}
        for item in data:
            j = item['proyecto'].jefe
            if j:
                jefes_map[j.id] = j.get_full_name() or j.username
        for item in finalizados:
            j = item['proyecto'].jefe
            if j:
                jefes_map[j.id] = j.get_full_name() or j.username

        jefes_list = [{'id': k, 'nombre': v} for k, v in jefes_map.items()]

        return render(request, 'panel.html', {
            'data': data,
            'finalizados': finalizados,
            'cuadrillas_sin_proyecto': cuadrillas_sin_proyecto,
            'is_jefe_view': True,
            'jefes_list': jefes_list,
            'current_user_id': user.id,
        })
        

    # LiderCuadrilla: ver proyectos donde tiene cuadrillas asignadas
    if user.groups.filter(name='LiderCuadrilla').exists():
        # Obtener proyectos donde el líder tiene cuadrillas asignadas (activos y finalizados)
        proyectos_activos = Proyecto.objects.filter(cuadrillas__lider=user, activo=True).distinct().prefetch_related('cuadrillas')
        proyectos_finalizados = Proyecto.objects.filter(cuadrillas__lider=user, activo=False).distinct().prefetch_related('cuadrillas')

        data = []
        for p in proyectos_activos:
            # Mostrar TODAS las cuadrillas del proyecto (lectura)
            cuadrillas = Cuadrilla.objects.filter(proyecto=p)
            cuad_list = []
            for c in cuadrillas:
                cuad_list.append({
                    'cuadrilla': c,
                    # Solo puede editar su propia cuadrilla
                    'can_edit': (c.lider_id == user.id),
                })

            data.append({
                'proyecto': p,
                'cuadrillas': cuad_list,
                # Líder NO puede editar proyecto, asignar cuadrillas, finalizar ni crear cuadrillas
                'can_edit_project': False,
                'can_assign': False,
                'can_finalize': False,
                'can_create_cuadrilla': False,
            })

        finalizados = []
        for p in proyectos_finalizados:
            cuadrillas = Cuadrilla.objects.filter(proyecto=p)
            cuad_list = []
            for c in cuadrillas:
                cuad_list.append({
                    'cuadrilla': c,
                    'can_edit': (c.lider_id == user.id),
                })
            finalizados.append({'proyecto': p, 'cuadrillas': cuad_list, 'can_edit_project': False})

        # Líder también puede ver sus cuadrillas sin proyecto asignado
        cuadrillas_sin_proyecto = []
        for c in Cuadrilla.objects.filter(proyecto__isnull=True, lider=user):
            cuadrillas_sin_proyecto.append({
                'cuadrilla': c,
                'can_edit': True,
                'can_disolver': True,
            })

        return render(request, 'panel.html', {
            'data': data,
            'finalizados': finalizados,
            'cuadrillas_sin_proyecto': cuadrillas_sin_proyecto,
            'is_lider_view': True,
        })

    # Trabajador: mostrar solo el proyecto de su cuadrilla actual (si tiene)
    from personal.models import Asignacion
    asign = Asignacion.objects.filter(trabajador=user).select_related('cuadrilla__proyecto').first()
    if asign and asign.cuadrilla and asign.cuadrilla.proyecto:
        p = asign.cuadrilla.proyecto
        # Enviar data simplificada para la plantilla
        data = [{'proyecto': p, 'cuadrillas': [asign.cuadrilla]}]
        return render(request, 'panel.html', {'data': data, 'basic': True})

    # Por defecto mostrar mensaje vacío
    return render(request, 'panel.html', {'data': []})

@login_required
@user_passes_test(es_jefe)
def asignar_cuadrillas(request, proyecto_id):
    proyecto = Proyecto.objects.get(id=proyecto_id, jefe=request.user)
    # Limpiar asociaciones con proyectos finalizados: si una cuadrilla aún apunta
    # a un proyecto que ya fue marcado como inactivo, la desasignamos.
    Cuadrilla.objects.filter(proyecto__activo=False).update(proyecto=None)

    # Cuadrillas disponibles son aquellas sin proyecto, con proyecto inactivo
    # (ya limpiadas arriba) o que ya pertenecen a este proyecto.
    cuadrillas_disponibles = Cuadrilla.objects.filter(Q(proyecto__isnull=True) | Q(proyecto=proyecto))

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


@login_required
@user_passes_test(es_jefe)
def finalizar_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, id=proyecto_id, jefe=request.user)

    if request.method == 'POST':
        # Marcar proyecto como inactivo/finalizado
        proyecto.activo = False
        proyecto.save()

        # Liberar cuadrillas asignadas y notificar a trabajadores
        cuadrillas = Cuadrilla.objects.filter(proyecto=proyecto)
        for c in cuadrillas:
            # Notificar a cada trabajador asignado
            for asig in c.asignaciones.all():
                msg = f"El proyecto '{proyecto.nombre}' ha sido finalizado. Has sido liberado de la cuadrilla '{c.nombre}'."
                crear_notificacion(asig.trabajador, msg)

            # Notificar al líder si existe
            if c.lider:
                crear_notificacion(c.lider, f"La cuadrilla '{c.nombre}' ha sido liberada porque el proyecto '{proyecto.nombre}' finalizó.")

            # Desasignar la cuadrilla del proyecto
            c.proyecto = None
            c.save()

        messages.success(request, f"El proyecto '{proyecto.nombre}' ha sido finalizado y las cuadrillas han sido liberadas.")
        return redirect('proyectos:panel')

    # Si es GET, mostrar confirmación simple (puede mejorarse)
    return render(request, 'confirmar_finalizar_proyecto.html', {'proyecto': proyecto})