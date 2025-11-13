from django import template
register = template.Library()

@register.filter
def get_item(queryset, user_id):
    return queryset.filter(trabajador_id=user_id).first()