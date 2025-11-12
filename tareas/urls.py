from django.urls import path
from . import views

app_name = 'tareas'

urlpatterns = [
    path('bitacoras/', views.bitacoras_view, name='bitacoras'),
    path('asignaciones/', views.asignaciones_view, name='asignaciones'),
]
