from django.test import TestCase
from django.contrib.auth.models import User

from personal.models import Cuadrilla, Asignacion
from .models import Conversation


class ConversationSignalsTest(TestCase):
    """Tests básicos para la creación/ eliminación automática de conversaciones grupales."""

    def setUp(self):
        self.cuad = Cuadrilla.objects.create(nombre='Cuadrilla Test')
        self.u1 = User.objects.create_user(username='user1', password='pass')
        self.u2 = User.objects.create_user(username='user2', password='pass')

    def test_conversation_created_when_two_members(self):
        # Con un solo miembro no debe crearse la conversación
        Asignacion.objects.create(trabajador=self.u1, cuadrilla=self.cuad)
        self.assertFalse(Conversation.objects.filter(cuadrilla=self.cuad, is_group=True).exists())

        # Al agregar un segundo miembro se debe crear la conversación grupal
        Asignacion.objects.create(trabajador=self.u2, cuadrilla=self.cuad)
        conv = Conversation.objects.filter(cuadrilla=self.cuad, is_group=True).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.participants.count(), 2)

    def test_conversation_deleted_when_members_less_than_two(self):
        a1 = Asignacion.objects.create(trabajador=self.u1, cuadrilla=self.cuad)
        a2 = Asignacion.objects.create(trabajador=self.u2, cuadrilla=self.cuad)
        conv = Conversation.objects.filter(cuadrilla=self.cuad, is_group=True).first()
        self.assertIsNotNone(conv)

        # Al eliminar una asignación, la conversación debería desaparecer si queda <2
        a2.delete()
        self.assertFalse(Conversation.objects.filter(cuadrilla=self.cuad, is_group=True).exists())


class PrivateConversationTest(TestCase):
    """Tests para asegurar que solo miembros de la misma cuadrilla pueden iniciar mensajes privados."""

    def setUp(self):
        self.cuad = Cuadrilla.objects.create(nombre='Cuadrilla PM')
        self.u1 = User.objects.create_user(username='pm1', password='pass')
        self.u2 = User.objects.create_user(username='pm2', password='pass')
        self.u3 = User.objects.create_user(username='outsider', password='pass')

    def test_only_members_can_create_private(self):
        # Asignar u1 y u2 a la misma cuadrilla
        Asignacion.objects.create(trabajador=self.u1, cuadrilla=self.cuad)
        Asignacion.objects.create(trabajador=self.u2, cuadrilla=self.cuad)

        # Simular login de u1 y petición para crear privada con u2
        self.client.login(username='pm1', password='pass')
        resp = self.client.get(f'/comunicacion/crear_privada/{self.u2.pk}/')
        # Redirección al detalle del chat
        self.assertEqual(resp.status_code, 302)

    def test_cannot_create_with_non_member(self):
        # u1 está en la cuadrilla, u3 no
        Asignacion.objects.create(trabajador=self.u1, cuadrilla=self.cuad)

        self.client.login(username='pm1', password='pass')
        resp = self.client.get(f'/comunicacion/crear_privada/{self.u3.pk}/')
        # Debe redirigir a la lista de conversaciones (no autorizado)
        self.assertEqual(resp.status_code, 302)

    def test_miembros_view_lists_members_and_links(self):
        # Asignar u1 y u2 a la misma cuadrilla
        Asignacion.objects.create(trabajador=self.u1, cuadrilla=self.cuad)
        Asignacion.objects.create(trabajador=self.u2, cuadrilla=self.cuad)

        self.client.login(username='pm1', password='pass')
        resp = self.client.get('/comunicacion/miembros/')
        self.assertEqual(resp.status_code, 200)
        # Debe contener enlace para crear privada con u2
        self.assertIn(f'/comunicacion/crear_privada/{self.u2.pk}/', resp.content.decode())
