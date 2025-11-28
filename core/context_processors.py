def notificaciones_no_leidas(request):
    if request.user.is_authenticated:
        return {
            "notifs_no_leidas": request.user.notificaciones.filter(leida=False).count()
        }
    return {"notifs_no_leidas": 0}


def archivos_archivados_count(request):
    """Provee el número de chats archivados accesibles para el usuario.

    Regla de acceso:
    - Para chats personales: solo participantes.
    - Para chats grupales: todos los integrantes del chat grupal.

    Usamos `participants_snapshot` (si existe) como fuente principal; si no,
    se usa la relación `conversation.participants` cuando la conversación
    aún existe.
    """
    if not request.user.is_authenticated:
        return {"archivos_archivados_count": 0}

    try:
        from comunicacion.models import ChatArchivado
        import json
        count = 0
        # Iteramos sobre los archivos y comprobamos si el usuario figura
        # en `participants_snapshot` o en la conversación original.
        for a in ChatArchivado.objects.all():
            allowed = False
            # Preferente: participants_snapshot
            try:
                parts = json.loads(a.participants_snapshot or '[]')
                if isinstance(parts, (list, tuple)) and request.user.id in parts:
                    allowed = True
            except Exception:
                pass

            if not allowed and a.conversation:
                try:
                    if a.conversation.participants.filter(pk=request.user.pk).exists():
                        allowed = True
                except Exception:
                    pass

            if not allowed and a.archived_by_id == request.user.id:
                allowed = True

            if allowed:
                count += 1
    except Exception:
        count = 0

    return {"archivos_archivados_count": count}
