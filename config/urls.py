from django.contrib import admin
from django.urls import path
from finance.views import OrderView, CustomerView, DebtView, CementTypeView, StatisticsView, CementTypeDeleteView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', OrderView.as_view(), name='dashboard'),
    path('customer/', CustomerView.as_view(), name='customer'),
    path('debt/', DebtView.as_view(), name='debts'),
    path('cement-type/', CementTypeView.as_view(), name='cement_type'),
    path('cement-type/delete/<int:pk>/', CementTypeDeleteView.as_view(), name='cement_type_delete'),
    path('statistics/', StatisticsView.as_view(), name='stats'),
]
