"""
URL configuration for LaCasaDeLaPradera project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from personal.views import TrabajadorPasswordChangeView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),              # Página principal y dashboard
    path('usuarios/', include('usuarios.urls')),
    # Endpoint personalizado para cambio de password (sobrescribe la ruta)
    path('accounts/password_change/', TrabajadorPasswordChangeView.as_view(), name='password_change'),
    # Endpoints de autenticación (login/logout/password change)
    path('accounts/', include('django.contrib.auth.urls')),
    path('personal/', include('personal.urls')),
    path('proyectos/', include('proyectos.urls')),
    path('tareas/', include('tareas.urls')),
    path('recursos/', include('recursos.urls')),
    path('comunicacion/', include('comunicacion.urls')),
]
# Servir archivos media en desarrollo (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)