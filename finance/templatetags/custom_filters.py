from django import template

register = template.Library()


@register.filter
def format_currency(value):
    if value is None:
        return ''
    try:
        value = float(value)
        # non-breaking spaces: an amount must never wrap onto two lines
        return '{:,.0f}'.format(value).replace(',', '\u00a0')
    except (ValueError, TypeError):
        return value
