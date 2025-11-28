from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Conversation, Message, WorkerRequest, IncidentNotice
from .models import ChatArchivado
from .forms import MessageForm, WorkerRequestForm, IncidentForm
from django.db.models import Q
from personal.models import Asignacion, Cuadrilla


@login_required
def conversations_list(request):
    """Lista las conversaciones en las que participa el usuario y muestra
    las cuadrillas donde participa para iniciar conversaciones privadas.
    """
    qs = Conversation.objects.filter(participants=request.user).select_related('cuadrilla')

    from personal.models import Asignacion, Cuadrilla

    cuad_ids = set(Asignacion.objects.filter(trabajador=request.user).values_list('cuadrilla_id', flat=True))
    lider_ids = set(Cuadrilla.objects.filter(lider=request.user).values_list('id', flat=True))
    cuad_ids |= lider_ids

    mis_cuadrillas = []
    if cuad_ids:
        cuad_qs = Cuadrilla.objects.filter(id__in=cuad_ids)
        for c in cuad_qs:
            asigns = Asignacion.objects.filter(cuadrilla=c).select_related('trabajador', 'rol').exclude(trabajador=request.user)
            miembros = []
            for a in asigns:
                miembros.append({
                    'user': a.trabajador,
                    'rol': a.rol.nombre if a.rol else None
                })
            mis_cuadrillas.append({'cuadrilla': c, 'miembros': miembros})

    # Si el usuario es Jefe de Proyecto, obtener líderes de cuadrillas de sus proyectos
    is_jefe = request.user.groups.filter(name='JefeProyecto').exists()
    lideres_proyecto = []
    if is_jefe:
        proyectos_cuadrillas = Cuadrilla.objects.filter(proyecto__jefe=request.user)
        for c in proyectos_cuadrillas:
            if c.lider and c.lider != request.user:
                lideres_proyecto.append(c.lider)

    return render(request, 'comunicacion/conversations_list.html', {
        'conversations': qs,
        'mis_cuadrillas': mis_cuadrillas,
        'lideres_proyecto': lideres_proyecto,
        'is_jefe': is_jefe,
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
    from personal.models import Asignacion, Cuadrilla

    # Permitir mensajes privados si comparten cuadrilla
    cuadras_mias = Asignacion.objects.filter(trabajador=request.user).values_list('cuadrilla_id', flat=True)
    cuadras_otro = Asignacion.objects.filter(trabajador=other).values_list('cuadrilla_id', flat=True)
    comparte_cuadrilla = bool(set(cuadras_mias) & set(cuadras_otro))

    permitido = comparte_cuadrilla or request.user.is_staff or request.user.is_superuser

    # Permitir si el usuario es Jefe de Proyecto y el otro es líder de una cuadrilla de sus proyectos
    if not permitido and request.user.groups.filter(name='JefeProyecto').exists():
        cuadrillas_jefe = Cuadrilla.objects.filter(proyecto__jefe=request.user)
        if cuadrillas_jefe.filter(lider=other).exists():
            permitido = True

    if not permitido:
        return redirect('comunicacion:conversations_list')

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
def archived_chats_list(request):
    """Lista de chats archivados accesibles para el usuario.

    Reglas simples de permiso:
    - Chats personales: accesibles si el usuario fue participante.
    - Chats grupales: accesibles si el usuario fue participante o es líder/jefe
      del proyecto/cuadrilla asociada.
    """
    from django.db.models import Q

    qs = ChatArchivado.objects.filter(
        Q(conversation__participants=request.user) |
        Q(conversation__cuadrilla__lider=request.user) |
        Q(archived_by=request.user)
    ).distinct()

    # Además: si la conversación original fue eliminada tras el archivado,
    # `conversation` puede ser NULL y la búsqueda por relaciones fallará.
    # En ese caso buscamos en los snapshots JSON aquellos archivos donde
    # el usuario aparece en `participants_snapshot` (preferente) o como
    # `sender_id` en los mensajes. Esto cubre casos donde la conversación
    # fue borrada y aun así debe estar accesible para los participantes originales.
    import json
    extra = []
    null_convs = ChatArchivado.objects.filter(conversation__isnull=True)
    for a in null_convs:
        added = False
        # Preferente: comprobar participants_snapshot
        try:
            parts = json.loads(a.participants_snapshot or '[]')
            if isinstance(parts, (list, tuple)) and request.user.id in parts:
                extra.append(a)
                added = True
        except Exception:
            pass
        if added:
            continue
        # Fallback: comprobar sender_id dentro de messages_snapshot
        try:
            msgs = json.loads(a.messages_snapshot or '[]')
        except Exception:
            msgs = []
        sender_ids = {m.get('sender_id') for m in msgs if m.get('sender_id') is not None}
        if request.user.id in sender_ids:
            extra.append(a)

    # Combinar queryset y lista de objetos extra (convertir queryset a lista)
    archivos = list(qs) + extra

    # Preparar `display_name` para cada archivo: si la conversación existe,
    # usar su representación; si no, reconstruir a partir de
    # `participants_snapshot` buscando los usuarios correspondientes.
    import json
    from django.contrib.auth.models import User

    for a in archivos:
        # Si hay conversación, la representación ya cubre nombres
        if getattr(a, 'conversation', None):
            try:
                a.display_name = str(a.conversation)
                continue
            except Exception:
                pass

        # Conversación eliminada: intentar reconstruir desde participants_snapshot
        a.display_name = None
        try:
            parts = json.loads(a.participants_snapshot or '[]')
            if isinstance(parts, (list, tuple)) and parts:
                users = User.objects.filter(id__in=parts)
                names = [u.get_full_name() or u.username for u in users]
                if names:
                    a.display_name = ', '.join(names)
        except Exception:
            a.display_name = None

        if not a.display_name:
            # Fallback textual label
            a.display_name = 'Conversación archivada'

    return render(request, 'comunicacion/archived_list.html', {'archivos': archivos})


@login_required
def archived_chat_detail(request, archivo_id):
    archivo = get_object_or_404(ChatArchivado, pk=archivo_id)

    # Permisos: permitir si el usuario participó en la conversación original,
    # o si es líder de la cuadrilla asociada, o si fue quien archivó.
    conv = archivo.conversation
    allowed = False
    if conv:
        if conv.participants.filter(pk=request.user.pk).exists():
            allowed = True
        if conv.cuadrilla and conv.cuadrilla.lider_id == request.user.id:
            allowed = True
    if archivo.archived_by_id == request.user.id:
        allowed = True
    # Si no está permitido por relaciones directas, comprobar si el usuario
    # aparece en el snapshot de mensajes (útil cuando la Conversation fue
    # eliminada tras el archivado y no quedan relaciones). Esto permite que
    # participantes originales sigan accediendo.
    if not allowed:
        try:
            import json
            msgs_tmp = json.loads(archivo.messages_snapshot or '[]')
            sender_ids = {m.get('sender_id') for m in msgs_tmp if m.get('sender_id') is not None}
            if request.user.id in sender_ids:
                allowed = True
        except Exception:
            pass

    if not allowed and not (request.user.is_staff or request.user.is_superuser):
        return redirect('comunicacion:conversations_list')

    # Parsear snapshot de mensajes
    import json
    try:
        mensajes = json.loads(archivo.messages_snapshot or '[]')
    except Exception:
        mensajes = []

    return render(request, 'comunicacion/archived_detail.html', {
        'archivo': archivo,
        'mensajes': mensajes,
    })



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
