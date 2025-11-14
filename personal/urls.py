from django.urls import path
from . import views

app_name = 'personal'

urlpatterns = [
    path('cuadrilla/<int:cuadrilla_id>/', views.detalle_cuadrilla, name='detalle_cuadrilla'),
    path('cuadrilla/nueva/', views.crear_cuadrilla, name='crear_cuadrilla'),
    path('cuadrilla/<int:cuadrilla_id>/editar/', views.editar_cuadrilla, name='editar_cuadrilla'),
]

# ------------------------------------------------------------------
# Ruta comentada para la vista de cambio de contraseña personalizada.
# Para habilitar el flujo de cambio obligatorio:
# 1) Descomenta las líneas abajo.
# 2) Asegúrate de que la clase `TrabajadorPasswordChangeView` esté
#    descomentada en `personal/views.py`.
# 3) Opcional: ajusta templates bajo `templates/registration/` si lo deseas.
# ------------------------------------------------------------------
"""
from django.contrib.auth import views as auth_views

# Sobrescribe la vista por defecto con la personalizada
urlpatterns += [
    path('password_change/', views.TrabajadorPasswordChangeView.as_view(), name='password_change'),
]
"""