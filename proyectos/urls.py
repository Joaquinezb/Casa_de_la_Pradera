from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    path('panel/', views.panel_proyectos, name='panel'),
    path('nuevo/', views.crear_proyecto, name='nuevo'),
    path('<int:proyecto_id>/asignar-cuadrillas/', views.asignar_cuadrillas, name='asignar_cuadrillas'),
    path('<int:proyecto_id>/finalizar/', views.finalizar_proyecto, name='finalizar'),
]
