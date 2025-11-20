from django.urls import path
from . import views

app_name = 'personal'

urlpatterns = [

    # ============================================================
    # Cuadrillas (CRUD)
    # ============================================================

    path(
        'cuadrilla/nueva/',
        views.crear_cuadrilla,
        name='crear_cuadrilla'
    ),

    path(
        'cuadrilla/<int:cuadrilla_id>/',
        views.detalle_cuadrilla,
        name='detalle_cuadrilla'
    ),

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

    path(
        'mover_trabajador/',
        views.mover_trabajador,
        name='mover_trabajador'
    ),

    # ============================================================
    # Notificaciones internas
    # ============================================================

    path(
        'notificaciones/',
        views.mis_notificaciones,
        name='mis_notificaciones'
    ),

    path(
        'notificaciones/leidas/',
        views.marcar_todas_leidas,
        name='notifs_leidas'
    ),

    # ============================================================
    # Cambio de contraseña (opcional)
    # ============================================================
    # path(
    #     'password_change/',
    #     views.TrabajadorPasswordChangeView.as_view(),
    #     name='password_change'
    # ),
]
