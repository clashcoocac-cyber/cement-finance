from django.contrib import admin
from django.urls import path
from finance.views import (
    LoginView, LogoutView,
    OrderView, CustomerView, DebtView, CementTypeView, StatisticsView, CementTypeDeleteView,
    OrderEditView
)


urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    path('', OrderView.as_view(), name='dashboard'),
    path('order/edit/<int:pk>/', OrderEditView.as_view(), name='order_edit'),
    path('customer/', CustomerView.as_view(), name='customer'),
    path('debt/', DebtView.as_view(), name='debts'),
    path('cement-type/', CementTypeView.as_view(), name='cement_type'),
    path('cement-type/delete/<int:pk>/', CementTypeDeleteView.as_view(), name='cement_type_delete'),
    path('statistics/', StatisticsView.as_view(), name='stats'),
]
