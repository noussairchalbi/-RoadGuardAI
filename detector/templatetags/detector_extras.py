from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def pct(value):
    """Convertit une proba 0..1 en pourcentage arrondi (ex: 0.873 -> 87.3)."""
    try:
        return round(float(value) * 100, 1)
    except (TypeError, ValueError):
        return value
