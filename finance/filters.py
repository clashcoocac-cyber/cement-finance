import datetime
import django_filters
from finance.models import Order, PaymentHistory


class OrderFilter(django_filters.FilterSet):
    customer_id = django_filters.CharFilter(lookup_expr='iexact', field_name='customer__id')
    cement_type_id = django_filters.CharFilter(lookup_expr='iexact', field_name='cement_type__id')
    date_from = django_filters.DateFilter(field_name='order_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='order_date', lookup_expr='lte')

    class Meta:
        model = Order
        fields = ['customer', 'cement_type', 'date_from', 'date_to']


class PaymentFilter(django_filters.FilterSet):
    customer_id = django_filters.CharFilter(lookup_expr='iexact', field_name='customer__id')
    date_from = django_filters.DateFilter(field_name='paid_at', lookup_expr='gte')
    date_to = django_filters.DateFilter(method='filter_date_to')

    class Meta:
        model = PaymentHistory
        fields = ['customer', 'date_from', 'date_to']

    def filter_date_to(self, queryset, name, value):
        end_of_day = datetime.datetime.combine(value + datetime.timedelta(days=1), datetime.time.min)
        return queryset.filter(paid_at__lt=end_of_day)
