from datetime import date
from django.http import HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.db import models
from django.views import View
from django.contrib.auth.views import LoginView as LView
from django.utils.timezone import make_naive
from django.contrib.auth.mixins import LoginRequiredMixin
from finance.models import Customer, CementType, Order, PaymentHistory
from finance.filters import OrderFilter, CustomerFilter, PaymentFilter
from finance.forms import CementTypeForm, OrderForm, CustomerForm, PaymentForm, PaymentEditForm


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

    def _get_payment_data(self, customer_id, date_from=None, date_to=None):
        """Get payment data for a specific customer with optional date filtering"""
        payments = PaymentHistory.objects.filter(customer_id=customer_id)
        
        # Apply date filtering if provided
        if date_from:
            payments = payments.filter(paid_at__date__gte=date_from)
        if date_to:
            payments = payments.filter(paid_at__date__lte=date_to)
            
        return payments.order_by('-paid_at')

    def _prepare_combined_data(self, orders, payments, customer):
        """Combine order and payment data into a single list"""
        combined_data = []
        
        # Add orders
        for order in orders:
            combined_data.append({
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
            })
        
        # Add payments
        for payment in payments:
            combined_data.append({
                'type': 'payment',
                'id': payment.id,
                'customer': payment.customer,
                'cement_type': '',  # Payments don't have cement type
                'quantity': 0,  # Payments don't have quantity
                'price_per_kg': 0,  # Payments don't have price
                'paid_amount': payment.amount,  # Negative because it reduces received amount
                'order_date': payment.paid_at.date(),
                'total_price': 0,  # Payments don't have total price
                'total_sum': 0,  # Payments don't contribute to total sum
                'road_cost': 0,  # Payments don't have road cost
                'car_number': '',  # Payments don't have car number
                'remaining_debt': -payment.amount,  # Negative because it reduces debt
                'payment_type': payment.payment_type,
            })
        
        combined_data.sort(key=lambda x: x['order_date'])
        return combined_data

    def get(self, request):
        query_params = request.GET.copy()
        if not query_params.get('customer_id'):
            query_params['date_from'] = query_params.get('date_from') or date.today()
            query_params['date_to'] = query_params.get('date_to') or date.today()

        # Get filtered orders
        filtered_orders = OrderFilter(
            query_params, 
            queryset=Order.objects.order_by('order_date').select_related('customer', 'cement_type')
        ).qs

        customer = None
        if request.GET.get('customer_id'):
            try:
                customer = Customer.objects.get(id=request.GET.get('customer_id'))
            except Customer.DoesNotExist:
                pass

        if customer:
            date_from = query_params.get('date_from')
            date_to = query_params.get('date_to')
            payments = self._get_payment_data(customer.id, date_from, date_to)
            
            # Combine orders and payments
            combined_data = self._prepare_combined_data(filtered_orders, payments, customer)
            
            total_quantity = sum(item['quantity'] for item in combined_data if item['type'] == 'order')
            total_price = sum(item['total_sum'] for item in combined_data if item['type'] == 'order')  # Only orders contribute to total price
            total_paid_amount = sum(item['paid_amount'] for item in combined_data if item['type'] == 'order') + sum(item['paid_amount'] for item in combined_data if item['type'] == 'payment')  # Orders + negative payments = net received
            total_debt = customer.total_debt  # Use customer's actual total debt
            
            order_data = combined_data
        else:
            # Calculate order totals only
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

            # Prepare order data
            order_data = [{
                'type': 'order',
                'id': order.id,
                'customer': order.customer,
                'cement_type': order.cement_type,
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
            
            total_quantity = totals['total_quantity']
            total_price = totals['total_price']
            total_paid_amount = totals['total_paid_amount']
            total_debt = totals['total_debt']

        context = {
            'orders': order_data,
            'customers': Customer.objects.all(),
            'cement_types': CementType.objects.all(),
            'today': date.today().strftime('%Y-%m-%d'),
            'total_quantity': total_quantity,
            'total_price': total_price,
            'total_paid_amount': total_paid_amount,
            'total_debt': total_debt,
            'page': 'dashboard',
            'customer': customer,
        }
        
        return render(request, self.template_name, context=context)
    
    def post(self, request):
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
        return redirect('dashboard')
    

class OrderEditView(LoginRequiredMixin, View):
    template_name = 'order_edit.html'

    def get_context(self, form, order):
        return {
            'form': form,
            'order': order,
            'customers': Customer.objects.all(),
            'cement_types': CementType.objects.all(),
            'page': 'dashboard',
        }

    def get(self, request, pk):
        order = get_object_or_404(Order, id=pk)
        form = OrderForm(instance=order)
        return render(request, self.template_name, self.get_context(form, order))
    
    def post(self, request, pk):
        order = get_object_or_404(Order, id=pk)
        form = OrderForm(request.POST, instance=order)
        
        if form.is_valid():
            form.save()
            return redirect('dashboard')
        
        return render(request, self.template_name, self.get_context(form, order))
    

class OrderDeleteView(LoginRequiredMixin, View):

    def get(self, request, pk):
        order = get_object_or_404(Order, id=pk)
        customer = order.customer
        customer.total_debt -= order.remaining_debt
        customer.save()
        order.delete()
        return redirect('dashboard')


class CustomerView(LoginRequiredMixin, View):
    template_name = 'customer.html'

    def get(self, request):
        customers = CustomerFilter(request.GET, Customer.objects.order_by('-total_debt')).qs
        all_customers = Customer.objects.order_by('-total_debt').values('id', 'name', 'phone', 'total_debt')
        total_debt = customers.aggregate(total=models.Sum('total_debt'))['total'] or 0

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
        customer = get_object_or_404(Customer, id=customer_id)
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save(update=True)
        return redirect('customer')


class CustomerDeleteView(LoginRequiredMixin, View):
    
    def delete(self, request, pk):
        Customer.objects.filter(id=pk).delete()
        return HttpResponse(status=204)


class DebtView(LoginRequiredMixin, View):
    template_name = 'debt.html'

    def get(self, request):
        customers = Customer.objects.order_by('-total_debt')
        payments = PaymentFilter(request.GET, PaymentHistory.objects.order_by('-paid_at')).qs
        
        context = {
            'customers': customers,
            'payments': payments,
            'total_amount': sum(payment.amount for payment in payments),
            'today': date.today().strftime('%Y-%m-%d'),
            'payment_type_choices': PaymentHistory.PaymentTypeChoices.choices,
            'page': 'debt',
        }
        return render(request, self.template_name, context=context)
    
    def post(self, request):
        form = PaymentForm(request.POST)
        if form.is_valid():
            form.save()
        return redirect('debts')
    

class PaymentEditView(LoginRequiredMixin, View):
    template_name = 'payment_edit.html'

    def get_context(self, form, payment):
        return {
            'form': form,
            'payment': payment,
            'payment_type_choices': PaymentHistory.PaymentTypeChoices.choices,
            'page': 'debt',
        }

    def get(self, request, pk):
        payment = get_object_or_404(PaymentHistory, id=pk)
        form = PaymentEditForm(instance=payment)
        return render(request, self.template_name, self.get_context(form, payment))
    
    def post(self, request, pk):
        payment = get_object_or_404(PaymentHistory, id=pk)
        form = PaymentEditForm(request.POST, instance=payment)
        
        if form.is_valid():
            form.save()
            return redirect('debts')
        
        return render(request, self.template_name, self.get_context(form, payment))


class PaymentDeleteView(LoginRequiredMixin, View):

    def get(self, request, pk):
        payment = get_object_or_404(PaymentHistory, id=pk)
        customer = payment.customer
        customer.total_debt += payment.amount
        customer.save()
        payment.delete()
        return redirect('debts')


class CementTypeView(LoginRequiredMixin, View):
    template_name = 'cement_type.html'

    def parse_month(self, month_str):
        try:
            year, month_num = month_str.split('-')
            return int(year), int(month_num)
        except ValueError:
            today = date.today()
            return today.year, today.month

    def get_month_annotation(self, year, month):
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

    def get(self, request):
        current_month = date.today().strftime('%Y-%m')
        selected_month = request.GET.get('month') or current_month
        
        year, month = self.parse_month(selected_month)
        
        cement_types = CementType.objects.annotate(
            total_quantity=self.get_month_annotation(year, month)
        )
        
        context = {
            'cement_types': cement_types,
            'colors': CementType.COLOR_CHOICES,
            'total_quantity': sum(cement_type.total_quantity or 0 for cement_type in cement_types),
            'page': 'cement_type',
            'selected_month': selected_month,
        }
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

    def get(self, request):
        orders = Order.objects.all()
        customers = Customer.objects.all()
        
        stats = {
            'total_orders': orders.count(),
            'total_revenue': sum(order.total_price for order in orders),
            'total_debt': sum(customer.total_debt for customer in customers),
            'total_quantity': sum(order.quantity for order in orders),
        }
        
        most_cement_types = CementType.objects.annotate(
            total_quantity=models.Sum('orders__quantity')
        ).order_by('-total_quantity')[:3]
        
        context = {
            'total_orders': stats['total_orders'],
            'total_revenue': stats['total_revenue'] - stats['total_debt'],
            'total_debt': stats['total_debt'],
            'total_quantity': stats['total_quantity'],
            'most_cement_types': most_cement_types,
            'page': 'stats',
        }
        
        return render(request, self.template_name, context=context)
