import django_filters
from finance.models import Order


class OrderFilter(django_filters.FilterSet):
    customer_id = django_filters.CharFilter(lookup_expr='iexact', field_name='customer__id')
    cement_type_id = django_filters.CharFilter(lookup_expr='iexact', field_name='cement_type__id')
    date_from = django_filters.DateFilter(field_name='order_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='order_date', lookup_expr='lte')

    class Meta:
        model = Order
        fields = ['customer', 'cement_type', 'date_from', 'date_to']
