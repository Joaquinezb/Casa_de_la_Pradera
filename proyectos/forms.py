from django import forms
from .models import Proyecto
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Row, Column, Div

class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'tipo', 'complejidad', 'descripcion', 'fecha_inicio', 'fecha_termino']
        labels = {
            'nombre': 'Nombre del Proyecto',
            'tipo': 'Tipo de Proyecto',
            'complejidad': 'Complejidad',
            'descripción': 'Descripción',
            'fecha_inicio': 'Fecha de Inicio',
            'fecha_termino': 'Fecha de Término'
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_termino': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('nombre', placeholder='Ingrese el nombre del proyecto'),
            Row(
                Column('tipo', css_class='form-group col-md-6'),
                Column('complejidad', css_class='form-group col-md-6'),
            ),
            Field('descripcion', placeholder='Describa el proyecto'),
            Row(
                Column('fecha_inicio', css_class='form-group col-md-6'),
                Column('fecha_termino', css_class='form-group col-md-6'),
            ),
            Submit('submit', 'Guardar Proyecto', css_class='btn btn-success mt-3')
        )

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_termino = cleaned_data.get('fecha_termino')

        if fecha_inicio and fecha_termino:
            if fecha_termino < fecha_inicio:
                raise forms.ValidationError(
                    'La fecha de término no puede ser anterior a la fecha de inicio.'
                )

        return cleaned_data
