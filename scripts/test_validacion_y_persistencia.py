"""
Test Suite Completo para Validación y Persistencia
====================================================
Cubre los principales modelos del sistema Casa de la Pradera:
- personal.models: Trabajador, Cuadrilla, Asignacion, Competencias, Certificaciones, Experiencias
- proyectos.models: Proyecto
- comunicacion.models: Conversation, Message, WorkerRequest, IncidentNotice
"""

from django.test import TestCase
from django.db import transaction, IntegrityError
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
import json

from personal.models import (
    Trabajador, Cuadrilla, Asignacion, Rol, TrabajadorPerfil,
    Competencia, Certificacion, Experiencia,
    CompetenciaTrabajador, CertificacionTrabajador, ExperienciaTrabajador,
    Notificacion
)
from proyectos.models import Proyecto
from comunicacion.models import Conversation, Message, WorkerRequest, IncidentNotice, ChatArchivado


# =============================================================================
# TESTS PARA MODELO TRABAJADOR
# =============================================================================

class TrabajadorValidacionTests(TestCase):
    """Tests de validación para el modelo Trabajador"""

    def setUp(self):
        """Configuración inicial para cada test"""
        self.datos_validos = {
            'rut': '123456789',
            'nombre': 'Juan',
            'apellido': 'Pérez',
            'email': 'juan.perez@example.com',
            'tipo_trabajador': 'trabajador',
            'estado': 'disponible'
        }

    def test_crear_trabajador_valido(self):
        """Test: Crear trabajador con datos válidos"""
        trabajador = Trabajador.objects.create(**self.datos_validos)
        self.assertIsNotNone(trabajador.pk)
        self.assertEqual(trabajador.rut, '123456789')
        self.assertEqual(trabajador.nombre, 'Juan')

    def test_rut_unico(self):
        """Test: El RUT debe ser único"""
        Trabajador.objects.create(**self.datos_validos)
        with self.assertRaises(IntegrityError):
            Trabajador.objects.create(**self.datos_validos)

    def test_rut_exactamente_9_digitos(self):
        """Test: RUT debe tener exactamente 9 dígitos"""
        # RUT con menos de 9 dígitos
        trabajador = Trabajador(**{**self.datos_validos, 'rut': '12345678'})
        with self.assertRaises(ValidationError):
            trabajador.full_clean()

        # RUT con más de 9 dígitos
        trabajador = Trabajador(**{**self.datos_validos, 'rut': '1234567890'})
        with self.assertRaises(ValidationError):
            trabajador.full_clean()

    def test_campos_obligatorios(self):
        """Test: Campos obligatorios no pueden ser nulos"""
        with self.assertRaises(IntegrityError):
            Trabajador.objects.create(nombre='Test', apellido='Test', email='test@test.com')

    def test_estado_choices_validos(self):
        """Test: Solo se aceptan estados válidos"""
        trabajador = Trabajador.objects.create(**self.datos_validos)
        trabajador.estado = 'disponible'
        trabajador.save()
        
        trabajador.estado = 'asignado'
        trabajador.save()
        
        trabajador.estado = 'vacaciones'
        trabajador.save()

    def test_tipo_trabajador_choices(self):
        """Test: Tipos de trabajador válidos"""
        for tipo in ['trabajador', 'lider', 'jefe']:
            datos = {**self.datos_validos, 'rut': f'12345678{tipo[0]}'}
            trabajador = Trabajador.objects.create(**datos, tipo_trabajador=tipo)
            self.assertEqual(trabajador.tipo_trabajador, tipo)

    def test_email_formato_valido(self):
        """Test: Email debe tener formato válido"""
        trabajador = Trabajador(**{**self.datos_validos, 'email': 'email_invalido'})
        with self.assertRaises(ValidationError):
            trabajador.full_clean()


class TrabajadorPersistenciaTests(TestCase):
    """Tests de persistencia y sincronización para Trabajador"""

    def test_persistencia_basica(self):
        """Test: Trabajador se persiste correctamente"""
        trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='Pedro',
            apellido='González',
            email='pedro@example.com'
        )
        self.assertTrue(Trabajador.objects.filter(id=trabajador.id).exists())

    def test_creacion_usuario_automatica(self):
        """Test: Se crea User automáticamente al crear Trabajador"""
        trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='María',
            apellido='López',
            email='maria@example.com'
        )
        user = trabajador.crear_usuario()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, '123456789')
        self.assertEqual(user.email, 'maria@example.com')

    def test_sincronizacion_datos_a_user(self):
        """Test: Cambios en Trabajador se sincronizan con User"""
        trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='Carlos',
            apellido='Ruiz',
            email='carlos@example.com'
        )
        user = trabajador.crear_usuario()
        
        # Modificar trabajador
        trabajador.email = 'carlos.nuevo@example.com'
        trabajador.nombre = 'Carlos Alberto'
        trabajador.save()
        trabajador.sincronizar_a_user()
        
        user.refresh_from_db()
        self.assertEqual(user.email, 'carlos.nuevo@example.com')
        self.assertEqual(user.first_name, 'Carlos Alberto')

    def test_rollback_transaccional(self):
        """Test: Rollback en transacciones funciona correctamente"""
        try:
            with transaction.atomic():
                Trabajador.objects.create(
                    rut='999999999',
                    nombre='Temporal',
                    apellido='Test',
                    email='temp@test.com'
                )
                raise ValueError("Error simulado")
        except ValueError:
            pass
        
        self.assertFalse(Trabajador.objects.filter(rut='999999999').exists())

    def test_soft_delete_con_activo(self):
        """Test: Campo 'activo' funciona como soft delete"""
        trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='Test',
            apellido='Inactivo',
            email='test@example.com',
            activo=True
        )
        
        trabajador.activo = False
        trabajador.save()
        
        self.assertFalse(trabajador.activo)
        self.assertTrue(Trabajador.objects.filter(rut='123456789').exists())


class TrabajadorAsignacionGruposTests(TestCase):
    """Tests de asignación de grupos según tipo de trabajador"""

    def setUp(self):
        """Crear grupos necesarios"""
        Group.objects.create(name='LiderCuadrilla')
        Group.objects.create(name='JefeProyecto')
        Group.objects.create(name='Trabajador')

    def test_lider_asignado_a_grupo(self):
        """Test: Líder se asigna al grupo LiderCuadrilla"""
        trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='Líder',
            apellido='Test',
            email='lider@test.com',
            tipo_trabajador='lider'
        )
        user = trabajador.crear_usuario()
        self.assertTrue(user.groups.filter(name='LiderCuadrilla').exists())

    def test_jefe_asignado_a_grupo(self):
        """Test: Jefe se asigna al grupo JefeProyecto"""
        trabajador = Trabajador.objects.create(
            rut='987654321',
            nombre='Jefe',
            apellido='Test',
            email='jefe@test.com',
            tipo_trabajador='jefe'
        )
        user = trabajador.crear_usuario()
        self.assertTrue(user.groups.filter(name='JefeProyecto').exists())


# =============================================================================
# TESTS PARA MODELO CUADRILLA
# =============================================================================

class CuadrillaValidacionTests(TestCase):
    """Tests de validación para Cuadrilla"""

    def setUp(self):
        self.user_lider = User.objects.create_user(username='lider1', password='pass123')
        self.proyecto = Proyecto.objects.create(
            nombre='Proyecto Test',
            fecha_inicio=date.today(),
            jefe=self.user_lider
        )

    def test_crear_cuadrilla_valida(self):
        """Test: Crear cuadrilla con datos válidos"""
        cuadrilla = Cuadrilla.objects.create(
            nombre='Cuadrilla A',
            proyecto=self.proyecto,
            lider=self.user_lider
        )
        self.assertIsNotNone(cuadrilla.pk)
        self.assertEqual(cuadrilla.nombre, 'Cuadrilla A')

    def test_cuadrilla_sin_proyecto(self):
        """Test: Cuadrilla puede existir sin proyecto asignado"""
        cuadrilla = Cuadrilla.objects.create(nombre='Cuadrilla Sin Proyecto')
        self.assertIsNone(cuadrilla.proyecto)

    def test_cuadrilla_sin_lider(self):
        """Test: Cuadrilla puede existir sin líder asignado"""
        cuadrilla = Cuadrilla.objects.create(nombre='Cuadrilla Sin Líder')
        self.assertIsNone(cuadrilla.lider)

    def test_nombre_obligatorio(self):
        """Test: Nombre es campo obligatorio"""
        with self.assertRaises(IntegrityError):
            Cuadrilla.objects.create(nombre=None)


class CuadrillaPersistenciaTests(TestCase):
    """Tests de persistencia para Cuadrilla"""

    def setUp(self):
        self.user = User.objects.create_user(username='test', password='pass123')
        self.proyecto = Proyecto.objects.create(
            nombre='Proyecto',
            fecha_inicio=date.today(),
            jefe=self.user
        )

    def test_persistencia_basica(self):
        """Test: Cuadrilla se persiste correctamente"""
        cuadrilla = Cuadrilla.objects.create(nombre='Cuadrilla 1', proyecto=self.proyecto)
        self.assertTrue(Cuadrilla.objects.filter(id=cuadrilla.id).exists())

    def test_relacion_con_proyecto(self):
        """Test: Relación con Proyecto funciona correctamente"""
        cuadrilla = Cuadrilla.objects.create(nombre='Cuadrilla Test', proyecto=self.proyecto)
        self.assertEqual(cuadrilla.proyecto, self.proyecto)
        self.assertIn(cuadrilla, self.proyecto.cuadrillas.all())

    def test_cascada_eliminacion_proyecto(self):
        """Test: Eliminar proyecto elimina cuadrillas asociadas"""
        cuadrilla = Cuadrilla.objects.create(nombre='Cuadrilla', proyecto=self.proyecto)
        cuadrilla_id = cuadrilla.id
        
        self.proyecto.delete()
        self.assertFalse(Cuadrilla.objects.filter(id=cuadrilla_id).exists())


# =============================================================================
# TESTS PARA MODELO ASIGNACION
# =============================================================================

class AsignacionTests(TestCase):
    """Tests para asignaciones de trabajadores a cuadrillas"""

    def setUp(self):
        self.user_jefe = User.objects.create_user(username='jefe', password='pass')
        self.user_trabajador = User.objects.create_user(username='trab1', password='pass')
        self.proyecto = Proyecto.objects.create(
            nombre='Proyecto',
            fecha_inicio=date.today(),
            jefe=self.user_jefe
        )
        self.cuadrilla = Cuadrilla.objects.create(nombre='Cuadrilla A', proyecto=self.proyecto)
        self.rol = Rol.objects.create(nombre='Operario')

    def test_crear_asignacion(self):
        """Test: Crear asignación válida"""
        asignacion = Asignacion.objects.create(
            trabajador=self.user_trabajador,
            cuadrilla=self.cuadrilla,
            rol=self.rol
        )
        self.assertIsNotNone(asignacion.pk)

    def test_asignacion_sin_rol(self):
        """Test: Asignación puede existir sin rol"""
        asignacion = Asignacion.objects.create(
            trabajador=self.user_trabajador,
            cuadrilla=self.cuadrilla
        )
        self.assertIsNone(asignacion.rol)

    def test_cascada_eliminacion_cuadrilla(self):
        """Test: Eliminar cuadrilla elimina asignaciones"""
        asignacion = Asignacion.objects.create(
            trabajador=self.user_trabajador,
            cuadrilla=self.cuadrilla,
            rol=self.rol
        )
        asignacion_id = asignacion.id
        
        self.cuadrilla.delete()
        self.assertFalse(Asignacion.objects.filter(id=asignacion_id).exists())


# =============================================================================
# TESTS PARA COMPETENCIAS Y CERTIFICACIONES
# =============================================================================

class CompetenciaTrabajadorTests(TestCase):
    """Tests para CompetenciaTrabajador"""

    def setUp(self):
        self.trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='Test',
            apellido='Competencias',
            email='test@test.com'
        )

    def test_crear_competencia(self):
        """Test: Crear competencia para trabajador"""
        comp = CompetenciaTrabajador.objects.create(
            trabajador=self.trabajador,
            nombre='Soldadura',
            nivel='intermedio'
        )
        self.assertEqual(comp.nombre, 'Soldadura')
        self.assertEqual(comp.nivel, 'intermedio')

    def test_competencia_unica_por_trabajador(self):
        """Test: No se pueden duplicar competencias por trabajador"""
        CompetenciaTrabajador.objects.create(
            trabajador=self.trabajador,
            nombre='Soldadura',
            nivel='basico'
        )
        with self.assertRaises(IntegrityError):
            CompetenciaTrabajador.objects.create(
                trabajador=self.trabajador,
                nombre='Soldadura',
                nivel='avanzado'
            )

    def test_niveles_validos(self):
        """Test: Niveles de competencia válidos"""
        niveles = ['basico', 'intermedio', 'avanzado', 'experto']
        for nivel in niveles:
            comp = CompetenciaTrabajador.objects.create(
                trabajador=self.trabajador,
                nombre=f'Competencia {nivel}',
                nivel=nivel
            )
            self.assertEqual(comp.nivel, nivel)


class CertificacionTrabajadorTests(TestCase):
    """Tests para CertificacionTrabajador"""

    def setUp(self):
        self.trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='Test',
            apellido='Certificaciones',
            email='test@test.com'
        )

    def test_crear_certificacion(self):
        """Test: Crear certificación válida"""
        cert = CertificacionTrabajador.objects.create(
            trabajador=self.trabajador,
            nombre='Certificación ISO',
            entidad='ISO',
            fecha_emision=date.today()
        )
        self.assertIsNotNone(cert.pk)

    def test_certificacion_vigente_sin_expiracion(self):
        """Test: Certificación sin fecha de expiración está vigente"""
        cert = CertificacionTrabajador.objects.create(
            trabajador=self.trabajador,
            nombre='Certificación Permanente',
            fecha_emision=date.today()
        )
        self.assertTrue(cert.vigente())

    def test_certificacion_vigente_con_expiracion_futura(self):
        """Test: Certificación con expiración futura está vigente"""
        cert = CertificacionTrabajador.objects.create(
            trabajador=self.trabajador,
            nombre='Certificación Temporal',
            fecha_emision=date.today(),
            fecha_expiracion=date.today() + timedelta(days=365)
        )
        self.assertTrue(cert.vigente())

    def test_certificacion_vencida(self):
        """Test: Certificación con expiración pasada no está vigente"""
        cert = CertificacionTrabajador.objects.create(
            trabajador=self.trabajador,
            nombre='Certificación Vencida',
            fecha_emision=date.today() - timedelta(days=730),
            fecha_expiracion=date.today() - timedelta(days=1)
        )
        self.assertFalse(cert.vigente())


# =============================================================================
# TESTS PARA MODELO PROYECTO
# =============================================================================

class ProyectoValidacionTests(TestCase):
    """Tests de validación para Proyecto"""

    def setUp(self):
        self.user_jefe = User.objects.create_user(username='jefe', password='pass')

    def test_crear_proyecto_valido(self):
        """Test: Crear proyecto con datos válidos"""
        proyecto = Proyecto.objects.create(
            nombre='Proyecto Test',
            descripcion='Descripción del proyecto',
            tipo='construccion',
            complejidad='media',
            fecha_inicio=date.today(),
            jefe=self.user_jefe
        )
        self.assertIsNotNone(proyecto.pk)

    def test_tipo_proyecto_valido(self):
        """Test: Tipos de proyecto válidos"""
        tipos = ['construccion', 'mantenimiento', 'instalacion', 'otro']
        for idx, tipo in enumerate(tipos):
            proyecto = Proyecto.objects.create(
                nombre=f'Proyecto {tipo}',
                tipo=tipo,
                fecha_inicio=date.today(),
                jefe=self.user_jefe
            )
            self.assertEqual(proyecto.tipo, tipo)

    def test_complejidad_valida(self):
        """Test: Niveles de complejidad válidos"""
        complejidades = ['baja', 'media', 'alta']
        for idx, comp in enumerate(complejidades):
            proyecto = Proyecto.objects.create(
                nombre=f'Proyecto {comp}',
                complejidad=comp,
                fecha_inicio=date.today(),
                jefe=self.user_jefe
            )
            self.assertEqual(proyecto.complejidad, comp)

    def test_proyecto_sin_fecha_termino(self):
        """Test: Proyecto puede existir sin fecha de término"""
        proyecto = Proyecto.objects.create(
            nombre='Proyecto Abierto',
            fecha_inicio=date.today(),
            jefe=self.user_jefe
        )
        self.assertIsNone(proyecto.fecha_termino)


# =============================================================================
# TESTS PARA COMUNICACIÓN
# =============================================================================

class ConversationTests(TestCase):
    """Tests para Conversation"""

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')

    def test_crear_conversacion_privada(self):
        """Test: Crear conversación privada"""
        conv = Conversation.objects.create(is_group=False)
        conv.participants.add(self.user1, self.user2)
        self.assertFalse(conv.is_group)
        self.assertEqual(conv.participants.count(), 2)

    def test_crear_conversacion_grupal(self):
        """Test: Crear conversación grupal"""
        conv = Conversation.objects.create(
            nombre='Grupo Test',
            is_group=True
        )
        conv.participants.add(self.user1, self.user2)
        self.assertTrue(conv.is_group)

    def test_add_participants(self):
        """Test: Agregar participantes a conversación"""
        conv = Conversation.objects.create()
        conv.add_participants([self.user1, self.user2])
        self.assertEqual(conv.participants.count(), 2)

    def test_archived_default_false(self):
        """Test: Conversación no archivada por defecto"""
        conv = Conversation.objects.create()
        self.assertFalse(conv.archived)


class MessageTests(TestCase):
    """Tests para Message"""

    def setUp(self):
        self.user = User.objects.create_user(username='sender', password='pass')
        self.conversation = Conversation.objects.create()

    def test_crear_mensaje_texto(self):
        """Test: Crear mensaje de texto"""
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            content='Hola mundo',
            message_type='text'
        )
        self.assertEqual(msg.message_type, 'text')
        self.assertEqual(msg.content, 'Hola mundo')

    def test_mensaje_tipos_validos(self):
        """Test: Tipos de mensaje válidos"""
        tipos = ['text', 'request', 'incident']
        for tipo in tipos:
            msg = Message.objects.create(
                conversation=self.conversation,
                sender=self.user,
                content=f'Mensaje tipo {tipo}',
                message_type=tipo
            )
            self.assertEqual(msg.message_type, tipo)

    def test_mensaje_sistema_sin_sender(self):
        """Test: Mensaje del sistema sin sender"""
        msg = Message.objects.create(
            conversation=self.conversation,
            content='Mensaje del sistema',
            sender=None
        )
        self.assertIsNone(msg.sender)

    def test_read_by_tracking(self):
        """Test: Tracking de lectura de mensajes"""
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            content='Test'
        )
        user2 = User.objects.create_user(username='reader', password='pass')
        msg.read_by.add(user2)
        self.assertIn(user2, msg.read_by.all())


class WorkerRequestTests(TestCase):
    """Tests para WorkerRequest"""

    def setUp(self):
        self.trabajador = User.objects.create_user(username='worker', password='pass')

    def test_crear_solicitud(self):
        """Test: Crear solicitud de trabajador"""
        request = WorkerRequest.objects.create(
            trabajador=self.trabajador,
            asunto='Solicitud de cambio',
            descripcion='Descripción detallada',
            estado='pending'
        )
        self.assertEqual(request.estado, 'pending')

    def test_estados_validos(self):
        """Test: Estados válidos de solicitud"""
        estados = ['pending', 'accepted', 'rejected']
        for idx, estado in enumerate(estados):
            request = WorkerRequest.objects.create(
                trabajador=self.trabajador,
                asunto=f'Solicitud {idx}',
                estado=estado
            )
            self.assertEqual(request.estado, estado)


class IncidentNoticeTests(TestCase):
    """Tests para IncidentNotice"""

    def setUp(self):
        self.user = User.objects.create_user(username='reporter', password='pass')

    def test_crear_incidente(self):
        """Test: Crear aviso de incidente"""
        incident = IncidentNotice.objects.create(
            reporter=self.user,
            descripcion='Incidente de prueba',
            severidad='low'
        )
        self.assertEqual(incident.severidad, 'low')
        self.assertFalse(incident.acknowledged)

    def test_severidades_validas(self):
        """Test: Severidades válidas de incidente"""
        severidades = ['low', 'medium', 'high']
        for sev in severidades:
            incident = IncidentNotice.objects.create(
                reporter=self.user,
                descripcion=f'Incidente {sev}',
                severidad=sev
            )
            self.assertEqual(incident.severidad, sev)

    def test_acknowledged_workflow(self):
        """Test: Workflow de reconocimiento de incidente"""
        incident = IncidentNotice.objects.create(
            reporter=self.user,
            descripcion='Test',
            severidad='high'
        )
        self.assertFalse(incident.acknowledged)
        
        incident.acknowledged = True
        incident.save()
        self.assertTrue(incident.acknowledged)


# =============================================================================
# TESTS DE INTEGRIDAD Y RELACIONES
# =============================================================================

class IntegridadRelacionesTests(TestCase):
    """Tests de integridad referencial y relaciones entre modelos"""

    def setUp(self):
        self.user = User.objects.create_user(username='test', password='pass')
        self.proyecto = Proyecto.objects.create(
            nombre='Proyecto',
            fecha_inicio=date.today(),
            jefe=self.user
        )

    def test_cascada_proyecto_a_cuadrillas(self):
        """Test: Eliminar proyecto elimina cuadrillas"""
        cuadrilla = Cuadrilla.objects.create(nombre='C1', proyecto=self.proyecto)
        cuadrilla_id = cuadrilla.id
        
        self.proyecto.delete()
        self.assertFalse(Cuadrilla.objects.filter(id=cuadrilla_id).exists())

    def test_set_null_en_lider(self):
        """Test: Eliminar user establece NULL en líder"""
        lider = User.objects.create_user(username='lider', password='pass')
        cuadrilla = Cuadrilla.objects.create(nombre='C1', lider=lider)
        
        lider.delete()
        cuadrilla.refresh_from_db()
        self.assertIsNone(cuadrilla.lider)

    def test_cascada_trabajador_a_competencias(self):
        """Test: Eliminar trabajador elimina sus competencias"""
        trabajador = Trabajador.objects.create(
            rut='123456789',
            nombre='Test',
            apellido='Test',
            email='test@test.com'
        )
        comp = CompetenciaTrabajador.objects.create(
            trabajador=trabajador,
            nombre='Competencia',
            nivel='basico'
        )
        comp_id = comp.id
        
        trabajador.delete()
        self.assertFalse(CompetenciaTrabajador.objects.filter(id=comp_id).exists())


# =============================================================================
# TESTS DE TRANSACCIONES Y ROLLBACK
# =============================================================================

class TransaccionesTests(TestCase):
    """Tests de comportamiento transaccional"""

    def test_rollback_multiple_objetos(self):
        """Test: Rollback afecta a todos los objetos en transacción"""
        try:
            with transaction.atomic():
                Trabajador.objects.create(
                    rut='111111111',
                    nombre='T1',
                    apellido='Test',
                    email='t1@test.com'
                )
                Trabajador.objects.create(
                    rut='222222222',
                    nombre='T2',
                    apellido='Test',
                    email='t2@test.com'
                )
                raise ValueError("Error forzado")
        except ValueError:
            pass
        
        self.assertEqual(Trabajador.objects.count(), 0)

    def test_savepoint_parcial(self):
        """Test: Savepoint permite rollback parcial"""
        trabajador1 = Trabajador.objects.create(
            rut='111111111',
            nombre='T1',
            apellido='Test',
            email='t1@test.com'
        )
        
        try:
            with transaction.atomic():
                Trabajador.objects.create(
                    rut='222222222',
                    nombre='T2',
                    apellido='Test',
                    email='t2@test.com'
                )
                raise ValueError("Error")
        except ValueError:
            pass
        
        # Primer trabajador debe existir, segundo no
        self.assertTrue(Trabajador.objects.filter(rut='111111111').exists())
        self.assertFalse(Trabajador.objects.filter(rut='222222222').exists())


# =============================================================================
# TESTS DE NOTIFICACIONES
# =============================================================================

class NotificacionTests(TestCase):
    """Tests para sistema de notificaciones"""

    def setUp(self):
        self.user = User.objects.create_user(username='user', password='pass')

    def test_crear_notificacion(self):
        """Test: Crear notificación para usuario"""
        notif = Notificacion.objects.create(
            user=self.user,
            mensaje='Notificación de prueba'
        )
        self.assertFalse(notif.leida)
        self.assertEqual(notif.mensaje, 'Notificación de prueba')

    def test_marcar_como_leida(self):
        """Test: Marcar notificación como leída"""
        notif = Notificacion.objects.create(
            user=self.user,
            mensaje='Test'
        )
        notif.leida = True
        notif.save()
        self.assertTrue(notif.leida)

    def test_ordenamiento_por_fecha(self):
        """Test: Notificaciones ordenadas por fecha descendente"""
        n1 = Notificacion.objects.create(user=self.user, mensaje='Primera')
        n2 = Notificacion.objects.create(user=self.user, mensaje='Segunda')
        
        notifs = list(Notificacion.objects.all())
        self.assertEqual(notifs[0], n2)
        self.assertEqual(notifs[1], n1)
