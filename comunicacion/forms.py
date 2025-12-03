from django import forms
from .models import Message, WorkerRequest, IncidentNotice
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Row, Column


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        labels = {
            'content': 'Mensaje'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('content', rows=2, placeholder='Escribe un mensaje...')
        )


class WorkerRequestForm(forms.ModelForm):
    class Meta:
        model = WorkerRequest
        fields = ['asunto', 'descripcion']
        labels = {
            'asunto': 'Asunto',
            'descripcion': 'Descripción'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('asunto', placeholder='Ingrese el asunto de su solicitud'),
            Field('descripcion', rows=4, placeholder='Describa su solicitud en detalle'),
            Submit('submit', 'Enviar Solicitud', css_class='btn btn-primary mt-3')
        )


class IncidentForm(forms.ModelForm):
    class Meta:
        model = IncidentNotice
        fields = ['descripcion', 'severidad']
        labels = {
            'descripcion': 'Descripción del Incidente',
            'severidad': 'Severidad'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('descripcion', rows=4, placeholder='Describa el incidente en detalle'),
            Field('severidad', css_class='form-select'),
            Submit('submit', 'Reportar Incidente', css_class='btn btn-danger mt-3')
        )
