from django.contrib import admin
from finance.models import Customer, CementType, Order


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'address', 'total_debt')
    search_fields = ('name', 'phone')
    ordering = ('-total_debt',)


@admin.register(CementType)
class CementTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'cement_type', 'order_date', 'quantity', 'total_price')
    search_fields = ('customer__name', 'cement_type__name')
    list_filter = ('order_date', 'cement_type')
    ordering = ('-order_date',)
    readonly_fields = ('total_price', 'total_sum', 'remaining_debt')
