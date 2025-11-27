from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Conversation, Message, WorkerRequest, IncidentNotice
from .forms import MessageForm, WorkerRequestForm, IncidentForm
from django.db.models import Q
from personal.models import Asignacion, Cuadrilla


@login_required
def conversations_list(request):
    """Lista las conversaciones en las que participa el usuario y muestra
    las cuadrillas donde participa para iniciar conversaciones privadas.
    """
    qs = Conversation.objects.filter(participants=request.user).select_related('cuadrilla')

    # Obtener las cuadrillas donde el usuario es asignado o líder
    from personal.models import Asignacion, Cuadrilla

    cuad_ids = set(Asignacion.objects.filter(trabajador=request.user).values_list('cuadrilla_id', flat=True))
    # Incluir las cuadrillas donde es líder
    lider_ids = set(Cuadrilla.objects.filter(lider=request.user).values_list('id', flat=True))
    cuad_ids |= lider_ids

    mis_cuadrillas = []
    if cuad_ids:
        cuad_qs = Cuadrilla.objects.filter(id__in=cuad_ids)
        for c in cuad_qs:
            # Obtener asignaciones para esta cuadrilla y construir lista de miembros con rol
            asigns = Asignacion.objects.filter(cuadrilla=c).select_related('trabajador', 'rol').exclude(trabajador=request.user)
            miembros = []
            for a in asigns:
                miembros.append({
                    'user': a.trabajador,
                    'rol': a.rol.nombre if a.rol else None
                })
            mis_cuadrillas.append({'cuadrilla': c, 'miembros': miembros})

    return render(request, 'comunicacion/conversations_list.html', {
        'conversations': qs,
        'mis_cuadrillas': mis_cuadrillas,
    })


@login_required
def conversation_detail(request, conversation_id):
    """Detalle de una conversación.

    Verifica que el usuario sea participante antes de mostrar la conversación.
    Maneja el envío de mensajes por POST.
    """
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not conv.participants.filter(pk=request.user.pk).exists():
        return redirect('comunicacion:conversations_list')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conv
            msg.sender = request.user
            msg.save()
            # marcar que el emisor ya leyó su propio mensaje
            msg.read_by.add(request.user)
            return redirect('comunicacion:conversation_detail', conversation_id=conv.pk)
    else:
        form = MessageForm()

    mensajes = conv.mensajes.select_related('sender')
    return render(request, 'comunicacion/conversation_detail.html', {
        'conversation': conv,
        'mensajes': mensajes,
        'form': form,
    })


@login_required
def create_private_conversation(request, user_id):
    other = get_object_or_404(User, pk=user_id)
    # Permitir mensajes privados solo entre miembros que comparten una cuadrilla
    from personal.models import Asignacion

    # Obtener cuadrillas del usuario actual y del otro
    cuadras_mias = Asignacion.objects.filter(trabajador=request.user).values_list('cuadrilla_id', flat=True)
    cuadras_otro = Asignacion.objects.filter(trabajador=other).values_list('cuadrilla_id', flat=True)

    comparte_cuadrilla = bool(set(cuadras_mias) & set(cuadras_otro))

    # Permitir también si el usuario es staff/superuser (administrador)
    if not comparte_cuadrilla and not (request.user.is_staff or request.user.is_superuser):
        # No autorizado a iniciar conversación privada con ese usuario
        return redirect('comunicacion:conversations_list')

    # Buscar conversación privada existente entre ambos (sin grupo)
    conv = Conversation.objects.filter(is_group=False, participants=request.user).filter(participants=other).distinct().first()
    if not conv:
        conv = Conversation.objects.create(is_group=False)
        conv.participants.add(request.user, other)
    return redirect('comunicacion:conversation_detail', conversation_id=conv.pk)


@login_required
def miembros_cuadrilla(request):
    """Lista y permite buscar miembros de las cuadrillas asociadas al usuario.

    Muestra enlaces para iniciar conversación privada con cada miembro (si procede).
    """
    # Obtener cuadrillas donde el usuario tiene asignación
    cuad_ids = set(Asignacion.objects.filter(trabajador=request.user).values_list('cuadrilla_id', flat=True))
    # Añadir cuadrillas donde el usuario es líder
    cuad_ids |= set(Cuadrilla.objects.filter(lider=request.user).values_list('id', flat=True))

    members = User.objects.none()
    if cuad_ids:
        members = User.objects.filter(asignacion__cuadrilla__id__in=cuad_ids).distinct()

    q = request.GET.get('q')
    if q:
        members = members.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )

    # Excluir al propio usuario
    members = members.exclude(pk=request.user.pk)

    return render(request, 'comunicacion/miembros_cuadrilla.html', {
        'members': members,
        'query': q or '',
    })


@login_required
def enviar_solicitud(request):
    if request.method == 'POST':
        form = WorkerRequestForm(request.POST)
        if form.is_valid():
            sol = form.save(commit=False)
            sol.trabajador = request.user
            # intentar asociar cuadrilla si el usuario tiene asignaciones
            from personal.models import Asignacion
            asign = Asignacion.objects.filter(trabajador=request.user).first()
            if asign:
                sol.cuadrilla = asign.cuadrilla
            sol.save()
            return redirect('comunicacion:conversations_list')
    else:
        form = WorkerRequestForm()
    return render(request, 'comunicacion/enviar_solicitud.html', {'form': form})


@login_required
def reportar_incidente(request):
    if request.method == 'POST':
        form = IncidentForm(request.POST)
        if form.is_valid():
            inc = form.save(commit=False)
            inc.reporter = request.user
            # intentar asociar cuadrilla si aplica
            from personal.models import Asignacion
            asign = Asignacion.objects.filter(trabajador=request.user).first()
            if asign:
                inc.cuadrilla = asign.cuadrilla
            inc.save()
            return redirect('comunicacion:conversations_list')
    else:
        form = IncidentForm()
    return render(request, 'comunicacion/reportar_incidente.html', {'form': form})


@login_required
def solicitudes_list(request):
    """Lista de solicitudes de trabajadores (para líderes y jefes)"""
    from personal.models import Asignacion
    # Obtener las cuadrillas donde el usuario es líder
    cuadrillas = []
    if request.user.groups.filter(name='LiderCuadrilla').exists():
        # Los líderes vienen definidos en el FK `Cuadrilla.lider`
        from personal.models import Cuadrilla
        cuadrillas = list(Cuadrilla.objects.filter(lider=request.user))
    elif request.user.groups.filter(name='JefeProyecto').exists():
        # Los jefes de proyecto ven todas las solicitudes
        from personal.models import Cuadrilla
        cuadrillas = Cuadrilla.objects.all()

    # Filtrar solicitudes de esas cuadrillas
    solicitudes = WorkerRequest.objects.filter(cuadrilla__in=cuadrillas).select_related('trabajador', 'cuadrilla')
    return render(request, 'comunicacion/solicitudes_list.html', {'solicitudes': solicitudes})


@login_required
def actualizar_solicitud(request, solicitud_id):
    """Actualizar el estado de una solicitud"""
    solicitud = get_object_or_404(WorkerRequest, pk=solicitud_id)
    # Verificar permisos
    from personal.models import Asignacion
    tiene_permiso = False
    if request.user.groups.filter(name='LiderCuadrilla').exists():
        # permitir si el usuario es el líder de la cuadrilla de la solicitud
        if solicitud.cuadrilla and solicitud.cuadrilla.lider_id == request.user.id:
            tiene_permiso = True
    elif request.user.groups.filter(name='JefeProyecto').exists():
        tiene_permiso = True

    if not tiene_permiso:
        return redirect('comunicacion:solicitudes_list')

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['pending', 'accepted', 'rejected']:
            solicitud.estado = nuevo_estado
            solicitud.save()

    return redirect('comunicacion:solicitudes_list')


@login_required
def incidentes_list(request):
    """Lista de incidentes (para líderes y jefes)"""
    from personal.models import Asignacion
    # Obtener las cuadrillas donde el usuario es líder
    cuadrillas = []
    if request.user.groups.filter(name='LiderCuadrilla').exists():
        from personal.models import Cuadrilla
        cuadrillas = list(Cuadrilla.objects.filter(lider=request.user))
    elif request.user.groups.filter(name='JefeProyecto').exists():
        # Los jefes de proyecto ven todos los incidentes
        from personal.models import Cuadrilla
        cuadrillas = Cuadrilla.objects.all()

    # Filtrar incidentes de esas cuadrillas
    incidentes = IncidentNotice.objects.filter(cuadrilla__in=cuadrillas).select_related('reporter', 'cuadrilla')
    return render(request, 'comunicacion/incidentes_list.html', {'incidentes': incidentes})


@login_required
def marcar_incidente_visto(request, incidente_id):
    """Marcar un incidente como visto/reconocido"""
    incidente = get_object_or_404(IncidentNotice, pk=incidente_id)
    # Verificar permisos
    from personal.models import Asignacion
    tiene_permiso = False
    if request.user.groups.filter(name='LiderCuadrilla').exists():
        if incidente.cuadrilla and incidente.cuadrilla.lider_id == request.user.id:
            tiene_permiso = True
    elif request.user.groups.filter(name='JefeProyecto').exists():
        tiene_permiso = True

    if tiene_permiso:
        incidente.acknowledged = True
        incidente.save()

    return redirect('comunicacion:incidentes_list')
