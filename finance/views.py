from datetime import date
from django.shortcuts import redirect, render
from django.db import models
from django.views import View
from finance.models import Customer, CementType, Order, PaymentHistory
from finance.filters import OrderFilter
from finance.forms import CementTypeForm, OrderForm, CustomerForm, PaymentForm


class OrderView(View):
    template_name = 'order.html'

    def get(self, request):
        orders = Order.objects.order_by('-order_date')
        return render(request, self.template_name, context={
            'orders': OrderFilter(request.GET, queryset=orders).qs,
            'customers': Customer.objects.all(),
            'cement_types': CementType.objects.all(),
            'today': date.today().strftime('%Y-%m-%d'),
            'page': 'dashboard',
        })
    
    def post(self, request):
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
        return redirect('dashboard') 


class CustomerView(View):
    template_name = 'customer.html'

    def get(self, request):
        customers = Customer.objects.order_by('-total_debt')
        return render(request, self.template_name, context={
            'customers': customers,
            'today': date.today().strftime('%Y-%m-%d'),
            'page': 'customer',
        })
    
    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer')
        return redirect('customer')


class DebtView(View):
    template_name = 'debt.html'

    def get(self, request):
        customers = Customer.objects.order_by('-total_debt')
        return render(request, self.template_name, context={
            'customers': customers,
            'payments': PaymentHistory.objects.order_by('-paid_at'),
            'today': date.today().strftime('%Y-%m-%d'),
            'page': 'debt',
        })
    
    def post(self, request):
        form = PaymentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('debts')
        return redirect('debts')


class CementTypeView(View):
    template_name = 'cement_type.html'

    def get(self, request):
        cement_types = CementType.objects.all()
        return render(request, self.template_name, context={
            'cement_types': cement_types,
            'page': 'cement_type',
        })
    
    def post(self, request):
        form = CementTypeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('cement_type')
        return redirect('cement_type')
    
class CementTypeDeleteView(View):

    def post(self, request, pk):
        CementType.objects.filter(pk=pk).delete()
        return redirect('cement_type')
    

class StatisticsView(View):
    template_name = 'stats.html'

    def get(self, request):
        orders = Order.objects.all()
        total_orders = orders.count()
        total_revenue = sum(order.total_price for order in orders)
        total_debt = sum(customer.total_debt for customer in Customer.objects.all())
        total_quantity = sum(order.quantity for order in orders)

        most_cement_types = CementType.objects.annotate(
            total_quantity=models.Sum('orders__quantity')
        ).order_by('-total_quantity')[:3]
        
        return render(request, self.template_name, context={
            'total_orders': total_orders,
            'total_revenue': total_revenue - total_debt,
            'total_debt': total_debt,
            'total_quantity': total_quantity,
            'most_cement_types': most_cement_types,
            'page': 'stats',
        })
