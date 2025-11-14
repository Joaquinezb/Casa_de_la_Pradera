from django.urls import path
from . import views

app_name = 'personal'

urlpatterns = [
    path('cuadrilla/<int:cuadrilla_id>/', views.detalle_cuadrilla, name='detalle_cuadrilla'),
    path('cuadrilla/nueva/', views.crear_cuadrilla, name='crear_cuadrilla'),
    path('cuadrilla/<int:cuadrilla_id>/editar/', views.editar_cuadrilla, name='editar_cuadrilla'),
]