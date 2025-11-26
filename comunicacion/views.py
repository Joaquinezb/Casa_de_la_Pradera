from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Conversation, Message, WorkerRequest, IncidentNotice
from .forms import MessageForm, WorkerRequestForm, IncidentForm
from django.db.models import Q


@login_required
def conversations_list(request):
    # Listar conversaciones donde participa el usuario
    qs = Conversation.objects.filter(participants=request.user).select_related('cuadrilla')
    return render(request, 'comunicacion/conversations_list.html', {'conversations': qs})


@login_required
def conversation_detail(request, conversation_id):
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
    # Buscar conversación privada existente entre ambos (sin grupo)
    conv = Conversation.objects.filter(is_group=False, participants=request.user).filter(participants=other).distinct().first()
    if not conv:
        conv = Conversation.objects.create(is_group=False)
        conv.participants.add(request.user, other)
    return redirect('comunicacion:conversation_detail', conversation_id=conv.pk)


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
        asignaciones = Asignacion.objects.filter(trabajador=request.user, rol='lider')
        cuadrillas = [a.cuadrilla for a in asignaciones]
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
        if Asignacion.objects.filter(trabajador=request.user, cuadrilla=solicitud.cuadrilla, rol='lider').exists():
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
        asignaciones = Asignacion.objects.filter(trabajador=request.user, rol='lider')
        cuadrillas = [a.cuadrilla for a in asignaciones]
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
        if Asignacion.objects.filter(trabajador=request.user, cuadrilla=incidente.cuadrilla, rol='lider').exists():
            tiene_permiso = True
    elif request.user.groups.filter(name='JefeProyecto').exists():
        tiene_permiso = True

    if tiene_permiso:
        incidente.acknowledged = True
        incidente.save()

    return redirect('comunicacion:incidentes_list')
