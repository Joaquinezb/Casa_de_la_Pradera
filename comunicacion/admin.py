from django.contrib import admin
from . import models


@admin.register(models.Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'is_group', 'created_at')
    filter_horizontal = ('participants',)


@admin.register(models.Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'message_type', 'created_at')
    list_filter = ('message_type',)


@admin.register(models.WorkerRequest)
class WorkerRequestAdmin(admin.ModelAdmin):
    list_display = ('asunto', 'trabajador', 'cuadrilla', 'estado', 'created_at')
    list_filter = ('estado',)


@admin.register(models.IncidentNotice)
class IncidentNoticeAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'cuadrilla', 'severidad', 'created_at', 'acknowledged')
    list_filter = ('severidad', 'acknowledged')
