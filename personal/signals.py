from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Group
from .models import Trabajador, TrabajadorPerfil


# ============================================================
# 1. Al crear un trabajador → crear usuario automáticamente
# ============================================================
@receiver(post_save, sender=Trabajador)
def crear_usuario_automatico(sender, instance: Trabajador, created, **kwargs):
    """
    Crea el User asociado al Trabajador (solo en creación).
    """
    if not created:
        return

    try:
        user = instance.crear_usuario()
        if user:
            # evitar loops usando update()
            Trabajador.objects.filter(pk=instance.pk).update(user_id=user.id, password_inicial=True)
    except Exception:
        pass


# ============================================================
# 2. Sincronizar SIEMPRE el User al guardar Trabajador
#    - nombre, apellido, email
#    - grupo según tipo
# ============================================================
@receiver(post_save, sender=Trabajador)
def sincronizar_usuario(sender, instance: Trabajador, **kwargs):
    """
    Sincroniza campos del usuario y el grupo según el tipo de trabajador.
    """
    user = instance.user
    if not user:
        return

    # -----------------------------------
    # 1. Sincronizar nombre y email
    # -----------------------------------
    try:
        user.first_name = instance.nombre
        user.last_name = instance.apellido
        user.email = instance.email or ""
        user.save(update_fields=["first_name", "last_name", "email"])
    except Exception:
        pass

    # -----------------------------------
    # 2. Sincronizar grupo según tipo
    # -----------------------------------
    tipo = (instance.tipo or "").strip().lower()

    mapping = {
        "jefe": "JefeProyecto",
        "líder": "LiderCuadrilla",
        "lider": "LiderCuadrilla",
        "trabajador": "Trabajador",
    }

    grupo_nombre = mapping.get(tipo)

    if grupo_nombre:
        try:
            grupo = Group.objects.get(name=grupo_nombre)
            user.groups.clear()
            user.groups.add(grupo)
        except Group.DoesNotExist:
            pass


# ============================================================
# 3. Crear perfil en TrabajadorPerfil al crear un User
# ============================================================
@receiver(post_save, sender=User)
def crear_perfil_trabajador(sender, instance, created, **kwargs):
    """
    Crea un TrabajadorPerfil solo si el User pertenece a un Trabajador.
    Evita creación innecesaria en admin/staff.
    """
    if not created:
        return

    # Si ya tiene perfil → no hacer nada
    if hasattr(instance, "perfil_trabajador"):
        return

    # Solo crear si este User está asignado a algún Trabajador
    trabajador = getattr(instance, "trabajador_profile", None)

    if trabajador:
        TrabajadorPerfil.objects.create(user=instance)
