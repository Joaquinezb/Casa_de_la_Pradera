from django.urls import path
from . import views

app_name = 'comunicacion'

urlpatterns = [
    path('', views.conversations_list, name='conversations_list'),
    path('chat/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('crear_privada/<int:user_id>/', views.create_private_conversation, name='crear_privada'),
    path('enviar_solicitud/', views.enviar_solicitud, name='enviar_solicitud'),
    path('reportar_incidente/', views.reportar_incidente, name='reportar_incidente'),
    path('solicitudes/', views.solicitudes_list, name='solicitudes_list'),
    path('solicitudes/<int:solicitud_id>/actualizar/', views.actualizar_solicitud, name='actualizar_solicitud'),
    path('incidentes/', views.incidentes_list, name='incidentes_list'),
    path('incidentes/<int:incidente_id>/marcar_visto/', views.marcar_incidente_visto, name='marcar_incidente_visto'),
]
