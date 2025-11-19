from django import template

register = template.Library()

# --- Filtro 1: obtener item desde un diccionario ---
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

# --- Filtro 2: verificar si el usuario pertenece a un grupo ---
@register.filter
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()

# --- Filtro opcional (comentado): obtener asignación ---
# @register.filter
# def get_asignacion(queryset, user_id):
#     return queryset.filter(trabajador_id=user_id).first()