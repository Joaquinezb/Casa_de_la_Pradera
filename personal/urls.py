from django.urls import path
from . import views

app_name = 'personal'

urlpatterns = [

    # ============================================================
    # Cuadrillas (CRUD)
    # ============================================================

    # Crear cuadrilla
    path(
        'cuadrilla/nueva/',
        views.crear_cuadrilla,
        name='crear_cuadrilla'
    ),

    # Detalle de cuadrilla
    path(
        'cuadrilla/<int:cuadrilla_id>/',
        views.detalle_cuadrilla,
        name='detalle_cuadrilla'
    ),

    # Editar cuadrilla
    path(
        'cuadrilla/<int:cuadrilla_id>/editar/',
        views.editar_cuadrilla,
        name='editar_cuadrilla'
    ),
    
    path(
    'trabajador/<int:trabajador_id>/estado/',
    views.editar_estado_trabajador,
    name='editar_estado_trabajador'
    ),

    path(
    'trabajador/<int:trabajador_id>/detalle/',
    views.detalle_trabajador,
    name='detalle_trabajador'
    ),


    # ============================================================
    # (Opcional) Cambio de contraseña personalizado para trabajadores
    # Descomentar si activas este flujo
    # ============================================================

    # path(
    #     'password_change/',
    #     views.TrabajadorPasswordChangeView.as_view(),
    #     name='password_change'
    # ),

]

