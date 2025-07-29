from django import template

register = template.Library()


@register.filter
def format_currency(value):
    if value is None:
        return ''
    try:
        value = float(value)
        return '{:,.0f}'.format(value).replace(',', ' ')
    except (ValueError, TypeError):
        return value
