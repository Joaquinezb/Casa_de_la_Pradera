def notificaciones_no_leidas(request):
    if request.user.is_authenticated:
        return {
            "notifs_no_leidas": request.user.notificaciones.filter(leida=False).count()
        }
    return {"notifs_no_leidas": 0}
