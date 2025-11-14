import os
import sys
import traceback

# Ajustar ruta al proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LaCasaDeLaPradera.settings')

import django
from django.conf import settings
from django.template.loader import get_template

try:
    django.setup()
    print('INSTALLED_APPS:', settings.INSTALLED_APPS)
    print('\nTEMPLATES setting:')
    from pprint import pprint
    pprint(settings.TEMPLATES)

    print('\nIntentando cargar plantilla cuadrilla_form.html...')
    tpl = get_template('cuadrilla_form.html')
    print('Plantilla encontrada:', tpl)
    origin = getattr(tpl, 'origin', None)
    print('Origin / info:', origin)
except Exception as e:
    print('\nERROR al cargar plantilla:')
    traceback.print_exc()
