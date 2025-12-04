# Usuarios de Prueba - Casa de la Pradera

## Script de Generación

El archivo `generar_usuarios_prueba.py` permite crear usuarios de prueba con datos completos.

### Ejecutar el Script

```bash
python generar_usuarios_prueba.py
```

## Usuarios Generados

El script crea automáticamente:

### 1 Jefe de Proyecto
- **RUT**: 189135574
- **Usuario**: 189135574
- **Contraseña**: 189135574
- **Nombre**: Jefe1 Proyecto1
- **Email**: jefe.proyecto1@casapradera.cl
- **Grupo**: JefeProyecto

### 3 Líderes de Cuadrilla

| RUT | Usuario | Contraseña | Nombre | Email |
|-----|---------|------------|--------|-------|
| 199637214 | 199637214 | 199637214 | Lider1 Cuadrilla1 | lider.cuadrilla1@casapradera.cl |
| 160332084 | 160332084 | 160332084 | Lider2 Cuadrilla2 | lider.cuadrilla2@casapradera.cl |
| 140885182 | 140885182 | 140885182 | Lider3 Cuadrilla3 | lider.cuadrilla3@casapradera.cl |

**Grupo**: LiderCuadrilla

### 10 Trabajadores

| RUT | Usuario | Contraseña | Nombre | Especialidad | Email |
|-----|---------|------------|--------|--------------|-------|
| 182851279 | 182851279 | 182851279 | Trabajador1 Operario1 | Electricidad | trabajador1@casapradera.cl |
| 145189342 | 145189342 | 145189342 | Trabajador2 Operario2 | Ayudante | trabajador2@casapradera.cl |
| 179848787 | 179848787 | 179848787 | Trabajador3 Operario3 | Ayudante | trabajador3@casapradera.cl |
| 129880980 | 129880980 | 129880980 | Trabajador4 Operario4 | Soldadura | trabajador4@casapradera.cl |
| 198613201 | 198613201 | 198613201 | Trabajador5 Operario5 | Ayudante | trabajador5@casapradera.cl |
| 173505435 | 173505435 | 173505435 | Trabajador6 Operario6 | Gasfitería | trabajador6@casapradera.cl |
| 194571210 | 194571210 | 194571210 | Trabajador7 Operario7 | Albañilería | trabajador7@casapradera.cl |
| 198356042 | 198356042 | 198356042 | Trabajador8 Operario8 | Soldadura | trabajador8@casapradera.cl |
| 173428102 | 173428102 | 173428102 | Trabajador9 Operario9 | Instalaciones | trabajador9@casapradera.cl |
| 173485082 | 173485082 | 173485082 | Trabajador10 Operario10 | Pintura | trabajador10@casapradera.cl |

**Grupo**: Trabajador

## Datos Incluidos

Cada usuario tiene:

✅ **Datos Personales**:
- RUT único
- Nombre y apellido
- Email
- Teléfono
- Dirección
- Fecha de nacimiento

✅ **Datos Laborales**:
- Tipo de trabajador (jefe/lider/trabajador)
- Especialidad
- Estado (disponible)
- Fecha de ingreso
- Años de experiencia

✅ **Competencias**:
- Jefes: 3 competencias nivel avanzado/experto
- Líderes: 3 competencias nivel intermedio/avanzado
- Trabajadores: 2-4 competencias nivel básico/intermedio/avanzado

✅ **Experiencia Laboral**:
- Todos los jefes y líderes tienen experiencia
- 70% de los trabajadores tienen experiencia

✅ **Usuario Django**:
- Usuario creado automáticamente
- Contraseña = RUT
- Grupos asignados correctamente
- Marcado como password inicial (debe cambiar en primer login)

❌ **Certificaciones PDF**:
- Deben agregarse manualmente
- No incluidas en el script

## Cómo Agregar Certificaciones

Las certificaciones deben agregarse manualmente desde:

1. Panel de administración: `/admin/personal/certificaciontrabajador/`
2. O desde la interfaz de usuario correspondiente

## Limpiar Usuarios de Prueba

Si necesitas eliminar los usuarios de prueba creados:

```python
# Desde Django shell
from personal.models import Trabajador
from django.contrib.auth.models import User

# Eliminar trabajadores de prueba (por patrón de nombre)
Trabajador.objects.filter(nombre__startswith='Jefe').delete()
Trabajador.objects.filter(nombre__startswith='Lider').delete()
Trabajador.objects.filter(nombre__startswith='Trabajador').delete()

# O eliminar por RUTs específicos
ruts = ['189135574', '199637214', '160332084', ...]
Trabajador.objects.filter(rut__in=ruts).delete()
```

## Notas Importantes

- Los RUTs son generados aleatoriamente (9 dígitos)
- Las contraseñas son iguales al RUT para facilitar testing
- Todos los usuarios están activos por defecto
- El campo `password_inicial=True` indica que debe cambiar la contraseña
