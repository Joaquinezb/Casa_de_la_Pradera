from personal.models import Trabajador
from django.core.exceptions import ValidationError

RUTS = ['218391519','218391521','218391522','218391523','218391524','218391525']

print('Verificando trabajadores creados...')
for rut in RUTS:
    t = Trabajador.objects.filter(rut=rut).first()
    if not t:
        print('FALLO: no existe', rut)
    else:
        try:
            t.full_clean()
            print('OK:', rut, 'user_id=', t.user_id)
        except ValidationError as e:
            print('VALIDATION ERROR en', rut, e)

print('\nProbando validación con RUT inválido (debe fallar)...')
bad = Trabajador(rut='123', nombre='Inv', apellido='Val', email='inv@example.com', tipo_trabajador='trabajador')
try:
    bad.full_clean()
    print('ERROR: el RUT inválido fue aceptado por full_clean()')
except ValidationError as e:
    print('OK: validación rechazó el RUT inválido ->', e)
