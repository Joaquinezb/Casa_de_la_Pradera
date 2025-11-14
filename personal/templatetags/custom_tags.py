from django import template
register = template.Library()

# --- Filtro 1: obtener item desde diccionario ---
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

# --- Filtro 2: obtener item desde queryset (Asig. por trabajador) ---
#@register.filter
#def get_asignacion(queryset, user_id):
    #return queryset.filter(trabajador_id=user_id).first()
