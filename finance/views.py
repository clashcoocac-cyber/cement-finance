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
        # Prepare query parameters with default dates if needed
        query_params = request.GET.copy()
        if not query_params.get('customer_id'):
            query_params['date_from'] = query_params.get('date_from') or date.today()
            query_params['date_to'] = query_params.get('date_to') or date.today()

        # Get filtered orders with related data
        filtered_orders = OrderFilter(
            query_params, 
            queryset=Order.objects.order_by('-order_date').select_related('customer', 'cement_type')
        ).qs

        # Calculate order totals
        order_aggs = filtered_orders.aggregate(
            total_quantity=models.Sum('quantity'),
            total_price=models.Sum('total_sum'),
            total_paid_amount=models.Sum('paid_amount'),
            total_debt=models.Sum('remaining_debt')
        )

        totals = {
            'total_quantity': order_aggs['total_quantity'] or 0,
            'total_price': order_aggs['total_price'] or 0,
            'total_paid_amount': order_aggs['total_paid_amount'] or 0,
            'total_debt': order_aggs['total_debt'] or 0,
        }

        # Prepare order data for template
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
            'car_number': order.car_number,
            'remaining_debt': order.remaining_debt,
        } for order in filtered_orders]

        # Prepare context and render
        context = {
            'orders': order_data,
            'customers': Customer.objects.all(),
            'cement_types': CementType.objects.all(),
            'today': date.today().strftime('%Y-%m-%d'),
            'total_quantity': totals['total_quantity'],
            'total_price': totals['total_price'],
            'total_paid_amount': totals['total_paid_amount'],
            'total_debt': totals['total_debt'],
            'page': 'dashboard',
            'customer': order_data[0]['customer'] if request.GET.get('customer_id') and len(order_data) > 0 else None,
        }
        
        return render(request, self.template_name, context=context)
    
    def post(self, request):
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
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
        # Get filtered customers and calculate totals
        customers = CustomerFilter(request.GET, Customer.objects.order_by('-total_debt')).qs
        all_customers = Customer.objects.order_by('-total_debt').values('id', 'name', 'phone', 'total_debt')
        total_debt = customers.aggregate(total=models.Sum('total_debt'))['total'] or 0

        # Prepare context and render
        context = {
            'customers': customers,
            'all_customers': all_customers,
            'today': date.today().strftime('%Y-%m-%d'),
            'total_debt': total_debt,
            'page': 'customer',
        }
        return render(request, self.template_name, context=context)
    
    def post(self, request):
        if request.POST.get('_method') == 'PUT':
            return self.put(request)
        
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
        return redirect('customer')

    def put(self, request):
        customer_id = request.POST.get('id')
        customer = Customer.objects.get(id=customer_id)
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
        return redirect('customer')


class CustomerDeleteView(LoginRequiredMixin, View):

    def delete(self, request, pk):
        Customer.objects.filter(id=pk).delete()
        return HttpResponse(status=204)


class DebtView(LoginRequiredMixin, View):
    template_name = 'debt.html'

    def _get_context_data(self, request):
        """Prepare context data for debt view"""
        customers = Customer.objects.order_by('-total_debt')
        payments = PaymentFilter(request.GET, PaymentHistory.objects.order_by('-paid_at')).qs
        
        return {
            'customers': customers,
            'payments': payments,
            'total_amount': sum(payment.amount for payment in PaymentHistory.objects.all()),
            'today': date.today().strftime('%Y-%m-%d'),
            'payment_type_choices': PaymentHistory.PaymentTypeChoices.choices,
            'page': 'debt',
        }

    def get(self, request):
        context = self._get_context_data(request)
        return render(request, self.template_name, context=context)
    
    def post(self, request):
        form = PaymentForm(request.POST)
        if form.is_valid():
            form.save()
        return redirect('debts')
    

class PaymentDeleteView(LoginRequiredMixin, View):

    def get(self, request, pk):
        payment = PaymentHistory.objects.get(id=pk)
        customer = payment.customer
        customer.total_debt += payment.amount
        customer.save()
        payment.delete()
        return redirect('debts')


class CementTypeView(LoginRequiredMixin, View):
    template_name = 'cement_type.html'

    def _parse_month_parameter(self, month_str):
        """Parse month parameter and return year, month tuple"""
        try:
            year, month_num = month_str.split('-')
            return int(year), int(month_num)
        except ValueError:
            today = date.today()
            return today.year, today.month

    def _get_month_filter_annotation(self, year, month):
        """Create month filter annotation for cement types"""
        return models.Sum(
            models.Case(
                models.When(
                    orders__order_date__year=year,
                    orders__order_date__month=month,
                    then='orders__quantity'
                ),
                default=0
            )
        )

    def _get_context_data(self, cement_types, selected_month):
        """Prepare context data for template"""
        return {
            'cement_types': cement_types,
            'colors': CementType.ColorChoices,
            'total_quantity': sum(cement_type.total_quantity or 0 for cement_type in cement_types),
            'page': 'cement_type',
            'selected_month': selected_month,
        }

    def get(self, request):
        # Get month parameter with fallback to current month
        current_month = date.today().strftime('%Y-%m')
        selected_month = request.GET.get('month') or current_month
        
        # Parse month for filtering
        year, month = self._parse_month_parameter(selected_month)
        
        # Get cement types with month-filtered quantities
        cement_types = CementType.objects.annotate(
            total_quantity=self._get_month_filter_annotation(year, month)
        )
        
        # Prepare context and render
        context = self._get_context_data(cement_types, selected_month)
        return render(request, self.template_name, context=context)
    
    def post(self, request):
        form = CementTypeForm(request.POST)
        if form.is_valid():
            form.save()
        return redirect('cement_type')
    
class CementTypeDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk):
        CementType.objects.filter(pk=pk).delete()
        return redirect('cement_type')
    

class StatisticsView(LoginRequiredMixin, View):
    template_name = 'stats.html'

    def _calculate_statistics(self):
        """Calculate all statistics for the dashboard"""
        orders = Order.objects.all()
        customers = Customer.objects.all()
        
        return {
            'total_orders': orders.count(),
            'total_revenue': sum(order.total_price for order in orders),
            'total_debt': sum(customer.total_debt for customer in customers),
            'total_quantity': sum(order.quantity for order in orders),
        }

    def _get_top_cement_types(self):
        """Get top 3 cement types by total quantity"""
        return CementType.objects.annotate(
            total_quantity=models.Sum('orders__quantity')
        ).order_by('-total_quantity')[:3]

    def get(self, request):
        # Calculate statistics
        stats = self._calculate_statistics()
        
        # Get top cement types
        most_cement_types = self._get_top_cement_types()
        
        # Prepare context and render
        context = {
            'total_orders': stats['total_orders'],
            'total_revenue': stats['total_revenue'] - stats['total_debt'],
            'total_debt': stats['total_debt'],
            'total_quantity': stats['total_quantity'],
            'most_cement_types': most_cement_types,
            'page': 'stats',
        }
        
        return render(request, self.template_name, context=context)
