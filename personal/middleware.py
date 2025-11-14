from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings


class ForcePasswordChangeMiddleware:
    """
    Middleware que fuerza al trabajador a cambiar su password si `password_inicial` es True.
    Excluye la propia URL de cambio de contraseña y los endpoints de logout/login.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Solo aplica si la funcionalidad está activada en settings
        if not getattr(settings, 'PERSONAL_FORCE_PASSWORD_CHANGE', False):
            return self.get_response(request)

        # Solo aplica si hay usuario autenticado
        if request.user.is_authenticated:
            # Evitar errores si no tiene relación con Trabajador
            trabajador = getattr(request.user, 'trabajador_profile', None)
            if trabajador and trabajador.password_inicial:
                path = request.path
                # Intentamos obtener rutas conocidas; si no existen, ignoramos reverses
                allowed_prefixes = ['/admin/']
                try:
                    allowed_prefixes.append(reverse('password_change'))
                except Exception:
                    pass
                try:
                    allowed_prefixes.append(reverse('password_change_done'))
                except Exception:
                    pass
                try:
                    allowed_prefixes.append(reverse('logout'))
                except Exception:
                    pass

                # Si la petición no apunta a ninguna ruta permitida, redirigimos
                if not any(path.startswith(pref) for pref in allowed_prefixes):
                    return redirect('password_change')
        return self.get_response(request)
