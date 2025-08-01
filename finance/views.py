from datetime import date
from itertools import chain
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.db import models
from django.views import View
from django.contrib.auth.views import LoginView as LView
from django.utils.timezone import make_naive
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
        filtered_payments = PaymentFilter(request.GET, queryset=PaymentHistory.objects.order_by('-paid_at')).qs

        order_data = [{
            'type': 'order',
            'id': order.id,
            'customer': order.customer if order.customer else '',
            'cement_type': order.cement_type if order.cement_type else '',
            'quantity': order.quantity,
            'price_per_kg': order.price_per_kg,
            'paid_amount': order.paid_amount,
            'order_date': order.order_date,
            'total_price': order.total_price,
            'total_sum': order.total_sum,
            'road_cost': order.road_cost,
            'remaining_debt': order.remaining_debt,
        } for order in filtered_orders]

        payment_data = [{
            'type': 'payment',
            'customer': payment.customer if payment.customer else '',
            'paid_amount': float(payment.amount),
            'order_date': make_naive(payment.paid_at).date(),
        } for payment in filtered_payments]

        combined_data = sorted(
            chain(order_data, payment_data),
            key=lambda x: x['order_date'],
            reverse=True
        )

        total_quantity = filtered_orders.aggregate(models.Sum('quantity'))['quantity__sum'] or 0 
        total_price = filtered_orders.aggregate(models.Sum('total_sum'))['total_sum__sum'] or 0
        total_paid_amount = (filtered_orders.aggregate(models.Sum('paid_amount'))['paid_amount__sum'] or 0) + (filtered_payments.aggregate(models.Sum('amount'))['amount__sum'] or 0)
        total_debt = (filtered_orders.aggregate(models.Sum('remaining_debt'))['remaining_debt__sum'] or 0) - (filtered_payments.aggregate(models.Sum('amount'))['amount__sum'] or 0)

        return render(request, self.template_name, context={
            'orders': combined_data,
            'customers': Customer.objects.all(),
            'cement_types': CementType.objects.all(),
            'today': date.today().strftime('%Y-%m-%d'),
            'total_quantity': total_quantity,
            'total_price': total_price,
            'total_paid_amount': total_paid_amount,
            'total_debt': total_debt,
            'page': 'dashboard',
            'customer': combined_data[0]['customer'] if request.GET.get('customer_id') else None,
        })
    
    def post(self, request):
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
        return redirect('dashboard') 
    

class OrderEditView(LoginRequiredMixin, View):
    template_name = 'order_edit.html'

    def get(self, request, pk):
        order = Order.objects.get(id=pk)
        form = OrderForm(instance=order)
        return render(request, self.template_name, context={
            'form': form,
            'order': order,
            'customers': Customer.objects.all(),
            'cement_types': CementType.objects.all(),
            'page': 'dashboard',
        })
    
    def post(self, request, pk):
        order = Order.objects.get(id=pk)
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
        return redirect('dashboard')
    

class OrderDeleteView(LoginRequiredMixin, View):

    def get(self, request, pk):
        order = Order.objects.get(id=pk)
        customer = order.customer
        customer.total_debt -= order.remaining_debt
        customer.save()
        order.delete()
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
            return redirect('customer')


class CustomerDeleteView(LoginRequiredMixin, View):

    def delete(self, request, pk):
        Customer.objects.filter(id=pk).delete()
        return HttpResponse(status=204)


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
