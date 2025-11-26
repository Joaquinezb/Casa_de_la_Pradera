from django import forms
from .models import Message, WorkerRequest, IncidentNotice


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows':2, 'placeholder':'Escribe un mensaje...'})
        }


class WorkerRequestForm(forms.ModelForm):
    class Meta:
        model = WorkerRequest
        fields = ['asunto', 'descripcion']


class IncidentForm(forms.ModelForm):
    class Meta:
        model = IncidentNotice
        fields = ['descripcion', 'severidad']
