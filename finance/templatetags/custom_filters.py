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


@register.filter
def customers_data(customers):
    """Customers as plain dicts for `json_script`: names go to the page scripts as data, never pasted into a
    JavaScript string (a backslash or a line break in a name used to break the whole page script)."""
    def field(customer, name):
        return customer[name] if isinstance(customer, dict) else getattr(customer, name)
    return [{'id': str(field(c, 'id')), 'name': field(c, 'name'), 'phone': field(c, 'phone'),
             'debt': field(c, 'total_debt')} for c in customers]
