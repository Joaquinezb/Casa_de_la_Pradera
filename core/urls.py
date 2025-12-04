from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='inicio'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('asignar-cuadrilla/<int:cuadrilla_id>/', views.asignar_cuadrilla_individual, name='asignar_cuadrilla_individual'),
    path('asignar-cuadrillas-masivo/', views.asignar_cuadrillas_masivo, name='asignar_cuadrillas_masivo'),
]
