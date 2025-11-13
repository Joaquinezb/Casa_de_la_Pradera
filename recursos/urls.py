from django.urls import path
from . import views

app_name = 'recursos'

urlpatterns = [
    path('lider/', views.inventario_lider, name='inventario_lider'),
    path('jefe/', views.inventario_jefe, name='inventario_jefe'),
]
