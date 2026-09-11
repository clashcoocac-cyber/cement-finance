from django.contrib import admin
from django.urls import path
from finance.views import (
    LoginView, LogoutView,
    OrderView, CustomerView, DebtView, CementTypeView, StatisticsView, CementTypeDeleteView,
    OrderEditView, OrderDeleteView, CustomerDeleteView, PaymentDeleteView, PaymentEditView
)
from finance.excel_views import (
    OrderExportView, CustomerExportView, DebtExportView, CementTypeExportView,
)


urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('', OrderView.as_view(), name='dashboard'),
    path('export/orders/', OrderExportView.as_view(), name='export_orders'),
    path('export/customers/', CustomerExportView.as_view(), name='export_customers'),
    path('export/debts/', DebtExportView.as_view(), name='export_debts'),
    path('export/cement-types/', CementTypeExportView.as_view(), name='export_cement_types'),
    path('order/edit/<int:pk>/', OrderEditView.as_view(), name='order_edit'),
    path('order/delete/<int:pk>/', OrderDeleteView.as_view(), name='order_delete'),
    path('customer/', CustomerView.as_view(), name='customer'),
    path('customer/delete/<int:pk>/', CustomerDeleteView.as_view(), name='customer_delete'),
    path('debt/', DebtView.as_view(), name='debts'),
    path('cement-type/', CementTypeView.as_view(), name='cement_type'),
    path('cement-type/delete/<int:pk>/', CementTypeDeleteView.as_view(), name='cement_type_delete'),
    path('statistics/', StatisticsView.as_view(), name='stats'),
    path('payments/edit/<int:pk>/', PaymentEditView.as_view(), name='payment_edit'),
    path('payments/delete/<int:pk>/', PaymentDeleteView.as_view(), name='payment_delete'),
]
