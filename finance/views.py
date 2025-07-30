from datetime import date
from django.shortcuts import redirect, render
from django.db import models
from django.views import View
from django.contrib.auth.views import LoginView as LView
from django.contrib.auth.mixins import LoginRequiredMixin
from finance.models import Customer, CementType, Order, PaymentHistory
from finance.filters import OrderFilter, CustomerFilter, PaymentFilter
from finance.forms import CementTypeForm, OrderForm, CustomerForm, PaymentForm


class LoginView(LView):
    template_name = 'login.html'
    redirect_authenticated_user = True


class LogoutView(View):

    def get(self, request):
        from django.contrib.auth import logout
        logout(request)
        return redirect('login')


class OrderView(LoginRequiredMixin, View):
    template_name = 'order.html'

    def get(self, request):
        filtered_orders = OrderFilter(request.GET, queryset=Order.objects.order_by('-order_date')).qs
        total_quantity = filtered_orders.aggregate(models.Sum('quantity'))['quantity__sum'] or 0
        total_price = filtered_orders.aggregate(models.Sum('total_sum'))['total_sum__sum'] or 0
        total_paid_amount = filtered_orders.aggregate(models.Sum('paid_amount'))['paid_amount__sum'] or 0
        total_debt = filtered_orders.aggregate(models.Sum('remaining_debt'))['remaining_debt__sum'] or 0

        return render(request, self.template_name, context={
            'orders': filtered_orders,
            'customers': Customer.objects.all(),
            'cement_types': CementType.objects.all(),
            'today': date.today().strftime('%Y-%m-%d'),
            'total_quantity': total_quantity,
            'total_price': total_price,
            'total_paid_amount': total_paid_amount,
            'total_debt': total_debt,
            'page': 'dashboard',
        })
    
    def post(self, request):
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
        return redirect('dashboard') 


class CustomerView(LoginRequiredMixin, View):
    template_name = 'customer.html'

    def get(self, request):
        customers = CustomerFilter(request.GET, Customer.objects.order_by('-total_debt')).qs
        all_customers = Customer.objects.order_by('-total_debt')

        return render(request, self.template_name, context={
            'customers': customers,
            'all_customers': all_customers,
            'today': date.today().strftime('%Y-%m-%d'),
            'total_debt': sum(customer.total_debt for customer in customers),
            'page': 'customer',
        })
    
    def post(self, request):
        if request.POST.get('_method') == 'PUT':
            return self.put(request)
        
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer')
        print(form.errors)
        return redirect('customer')


    def put(self, request):
        customer_id = request.POST.get('id')
        customer = Customer.objects.get(id=customer_id)
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('customer')
        print(form.errors)
        return redirect('customer')


class DebtView(LoginRequiredMixin, View):
    template_name = 'debt.html'

    def get(self, request):
        customers = Customer.objects.order_by('-total_debt')
        return render(request, self.template_name, context={
            'customers': customers,
            'payments': PaymentFilter(request.GET, PaymentHistory.objects.order_by('-paid_at')).qs,
            'total_amount': sum(payment.amount for payment in PaymentHistory.objects.all()),
            'today': date.today().strftime('%Y-%m-%d'),
            'page': 'debt',
        })
    
    def post(self, request):
        form = PaymentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('debts')
        return redirect('debts')


class CementTypeView(LoginRequiredMixin, View):
    template_name = 'cement_type.html'

    def get(self, request):
        cement_types = CementType.objects.annotate(
            total_quantity=models.Sum('orders__quantity')
        )
        return render(request, self.template_name, context={
            'cement_types': cement_types,
            'colors': CementType.ColorChoices,
            'total_quantity': sum(cement_type.total_quantity or 0 for cement_type in cement_types),
            'page': 'cement_type',
        })
    
    def post(self, request):
        form = CementTypeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('cement_type')
        return redirect('cement_type')
    
class CementTypeDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk):
        CementType.objects.filter(pk=pk).delete()
        return redirect('cement_type')
    

class StatisticsView(LoginRequiredMixin, View):
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
