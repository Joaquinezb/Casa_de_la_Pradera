"""
Script para generar usuarios de prueba:
- 1 Jefe de Proyecto
- 3 Líderes de Cuadrilla
- 10 Trabajadores

Uso:
    python manage.py shell < generar_usuarios_prueba.py
    o
    python generar_usuarios_prueba.py (si se configura Django)
"""

import os
import sys
import django
from datetime import date, timedelta
from random import choice, randint, sample

# Configurar Django si se ejecuta como script standalone
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LaCasaDeLaPradera.settings')
    django.setup()

from django.contrib.auth.models import User, Group
from personal.models import Trabajador, CompetenciaTrabajador, ExperienciaTrabajador

# Configuraciones
ESPECIALIDADES_JEFE = ['Gestión de Proyectos', 'Ingeniería Civil', 'Arquitectura']
ESPECIALIDADES_LIDER = ['Construcción', 'Instalaciones', 'Acabados', 'Estructuras']
ESPECIALIDADES_TRABAJADOR = [
    'Albañilería', 'Carpintería', 'Electricidad', 'Gasfitería',
    'Pintura', 'Soldadura', 'Instalaciones', 'Ayudante'
]

COMPETENCIAS = {
    'jefe': ['Gestión de equipos', 'Planificación', 'Control de presupuesto', 'Liderazgo'],
    'lider': ['Coordinación', 'Supervisión', 'Lectura de planos', 'Control de calidad'],
    'trabajador': ['Trabajo en equipo', 'Seguridad laboral', 'Uso de herramientas', 'Lectura de planos']
}

def generar_rut():
    """Genera un RUT aleatorio de 9 dígitos"""
    return str(randint(100000000, 199999999))

def generar_telefono():
    """Genera un teléfono chileno"""
    return f"+569{randint(10000000, 99999999)}"

def crear_grupos_si_no_existen():
    """Crea los grupos necesarios si no existen"""
    grupos = ['JefeProyecto', 'LiderCuadrilla', 'Trabajador']
    for grupo_nombre in grupos:
        Group.objects.get_or_create(name=grupo_nombre)
    print("[OK] Grupos verificados/creados")

def crear_jefe_proyecto(numero):
    """Crea un Jefe de Proyecto"""
    rut = generar_rut()
    nombre = f"Jefe{numero}"
    apellido = f"Proyecto{numero}"
    email = f"jefe.proyecto{numero}@casapradera.cl"

    # Crear Trabajador
    trabajador = Trabajador.objects.create(
        rut=rut,
        nombre=nombre,
        apellido=apellido,
        email=email,
        telefono=generar_telefono(),
        direccion=f"Calle Principal {randint(100, 999)}, Santiago",
        fecha_nacimiento=date(1975 + numero, randint(1, 12), randint(1, 28)),
        tipo_trabajador='jefe',
        especialidad=choice(ESPECIALIDADES_JEFE),
        estado='disponible',
        fecha_ingreso=date(2015 + numero, randint(1, 12), 1),
        anos_experiencia=randint(10, 20),
        activo=True,
        password_inicial=True
    )

    # Crear User asociado
    user = trabajador.crear_usuario()

    # Agregar competencias
    for comp in sample(COMPETENCIAS['jefe'], k=min(3, len(COMPETENCIAS['jefe']))):
        CompetenciaTrabajador.objects.create(
            trabajador=trabajador,
            nombre=comp,
            nivel=choice(['avanzado', 'experto']),
            fecha_adquisicion=date(2010 + randint(0, 10), randint(1, 12), 1)
        )

    # Agregar experiencia
    ExperienciaTrabajador.objects.create(
        trabajador=trabajador,
        proyecto=f"Proyecto Habitacional {randint(1, 50)}",
        empresa_externa="Constructora Anterior S.A.",
        rol="Jefe de Obra",
        fecha_inicio=date(2010 + randint(0, 5), 1, 1),
        fecha_termino=date(2015 + numero - 1, 12, 31),
        calificacion='muy_recomendado'
    )

    print(f"[OK] Jefe Proyecto creado: {rut} - {nombre} {apellido} (user: {user.username}, pass: {rut})")
    return trabajador

def crear_lider_cuadrilla(numero):
    """Crea un Líder de Cuadrilla"""
    rut = generar_rut()
    nombre = f"Lider{numero}"
    apellido = f"Cuadrilla{numero}"
    email = f"lider.cuadrilla{numero}@casapradera.cl"

    # Crear Trabajador
    trabajador = Trabajador.objects.create(
        rut=rut,
        nombre=nombre,
        apellido=apellido,
        email=email,
        telefono=generar_telefono(),
        direccion=f"Avenida Los Robles {randint(100, 999)}, Santiago",
        fecha_nacimiento=date(1980 + numero, randint(1, 12), randint(1, 28)),
        tipo_trabajador='lider',
        especialidad=choice(ESPECIALIDADES_LIDER),
        estado='disponible',
        fecha_ingreso=date(2017 + numero % 3, randint(1, 12), 1),
        anos_experiencia=randint(5, 15),
        activo=True,
        password_inicial=True
    )

    # Crear User asociado
    user = trabajador.crear_usuario()

    # Agregar competencias
    for comp in sample(COMPETENCIAS['lider'], k=min(3, len(COMPETENCIAS['lider']))):
        CompetenciaTrabajador.objects.create(
            trabajador=trabajador,
            nombre=comp,
            nivel=choice(['intermedio', 'avanzado']),
            fecha_adquisicion=date(2015 + randint(0, 7), randint(1, 12), 1)
        )

    # Agregar experiencia
    ExperienciaTrabajador.objects.create(
        trabajador=trabajador,
        proyecto=f"Edificio Residencial {randint(1, 30)}",
        empresa_externa="Constructora Regional Ltda.",
        rol="Capataz",
        fecha_inicio=date(2012 + randint(0, 5), 1, 1),
        fecha_termino=date(2017 + numero % 3 - 1, 12, 31),
        calificacion=choice(['recomendado', 'muy_recomendado'])
    )

    print(f"[OK] Lider Cuadrilla creado: {rut} - {nombre} {apellido} (user: {user.username}, pass: {rut})")
    return trabajador

def crear_trabajador(numero):
    """Crea un Trabajador"""
    rut = generar_rut()
    nombre = f"Trabajador{numero}"
    apellido = f"Operario{numero}"
    email = f"trabajador{numero}@casapradera.cl"

    # Crear Trabajador
    trabajador = Trabajador.objects.create(
        rut=rut,
        nombre=nombre,
        apellido=apellido,
        email=email,
        telefono=generar_telefono(),
        direccion=f"Pasaje Los Álamos {randint(100, 999)}, Santiago",
        fecha_nacimiento=date(1985 + numero % 10, randint(1, 12), randint(1, 28)),
        tipo_trabajador='trabajador',
        especialidad=choice(ESPECIALIDADES_TRABAJADOR),
        estado='disponible',
        fecha_ingreso=date(2019 + numero % 5, randint(1, 12), 1),
        anos_experiencia=randint(1, 10),
        activo=True,
        password_inicial=True
    )

    # Crear User asociado
    user = trabajador.crear_usuario()

    # Agregar competencias
    num_competencias = randint(2, 4)
    for comp in sample(COMPETENCIAS['trabajador'], k=min(num_competencias, len(COMPETENCIAS['trabajador']))):
        CompetenciaTrabajador.objects.create(
            trabajador=trabajador,
            nombre=comp,
            nivel=choice(['basico', 'intermedio', 'avanzado']),
            fecha_adquisicion=date(2018 + randint(0, 5), randint(1, 12), 1)
        )

    # Agregar experiencia (opcional, 70% de probabilidad)
    if randint(1, 10) <= 7:
        ExperienciaTrabajador.objects.create(
            trabajador=trabajador,
            proyecto=f"Obra {randint(1, 100)}",
            empresa_externa=choice([
                "Constructora del Sur S.A.",
                "Obras Civiles Ltda.",
                "Edificaciones Modernas",
                None
            ]),
            rol=trabajador.especialidad,
            fecha_inicio=date(2015 + randint(0, 4), 1, 1),
            fecha_termino=date(2019 + numero % 5 - 1, 12, 31),
            calificacion=choice(['recomendado', 'muy_recomendado', 'no_recomendado'])
        )

    print(f"[OK] Trabajador creado: {rut} - {nombre} {apellido} (user: {user.username}, pass: {rut})")
    return trabajador

def main():
    print("=" * 60)
    print("GENERACIÓN DE USUARIOS DE PRUEBA")
    print("=" * 60)
    print()

    # Verificar/crear grupos
    crear_grupos_si_no_existen()
    print()

    # Crear 1 Jefe de Proyecto
    print("Creando Jefe de Proyecto...")
    print("-" * 60)
    jefe = crear_jefe_proyecto(1)
    print()

    # Crear 3 Líderes de Cuadrilla
    print("Creando Líderes de Cuadrilla...")
    print("-" * 60)
    lideres = []
    for i in range(1, 4):
        lideres.append(crear_lider_cuadrilla(i))
    print()

    # Crear 10 Trabajadores
    print("Creando Trabajadores...")
    print("-" * 60)
    trabajadores = []
    for i in range(1, 11):
        trabajadores.append(crear_trabajador(i))
    print()

    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Total usuarios creados: {1 + 3 + 10} = 14")
    print()
    print("CREDENCIALES DE ACCESO:")
    print("Usuario: [RUT sin puntos ni guión]")
    print("Contraseña: [mismo RUT]")
    print()
    print("NOTA: Las certificaciones con archivos PDF deben agregarse")
    print("      manualmente desde el panel de administración o la interfaz.")
    print("=" * 60)

if __name__ == '__main__':
    main()
