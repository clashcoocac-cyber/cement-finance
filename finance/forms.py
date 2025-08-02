from django import forms
from finance.models import Customer, CementType, Order, PaymentHistory


class OrderForm(forms.ModelForm):    
    customer_id = forms.IntegerField()
    cement_type_id = forms.IntegerField()

    class Meta:
        model = Order
        fields = ['customer_id', 'cement_type_id', 'quantity', 'price_per_kg', 'road_cost', 'paid_amount', 'car_number']

    def save(self, commit = True):
        order = super().save(commit=False)
        order.customer = Customer.objects.get(id=self.cleaned_data['customer_id'])
        order.cement_type = CementType.objects.get(id=self.cleaned_data['cement_type_id'])
        if commit:
            order.save()
            customer = order.customer
            customer.total_debt += order.remaining_debt
            customer.save()
        return order


class CustomerForm(forms.ModelForm):
    debt = forms.CharField(required=False, initial='0')

    class Meta:
        model = Customer
        fields = ['name', 'phone', 'address', 'debt']

    def save(self, commit=True):
        customer = super().save(commit=False)
        debt = self.cleaned_data.get('debt').replace(',', '').replace(' ', '').replace('.', '') or 0

        if commit:
            customer.total_debt = int(debt)
            customer.default_debt = int(debt)
            customer.save()
        return customer


class PaymentForm(forms.ModelForm):
    customer_id = forms.IntegerField()
    payment_amount = forms.CharField()

    class Meta:
        model = PaymentHistory
        fields = ['customer_id', 'payment_amount', 'payment_type']

    def save(self, commit=True):
        payment_history = super().save(commit=False)
        payment_history.customer = Customer.objects.get(id=self.cleaned_data['customer_id'])
        if commit:
            payment_history.amount = float(self.cleaned_data['payment_amount'].replace(',', '').replace(' ', '').replace('.', ''))
            payment_history.save()
            customer = payment_history.customer
            customer.total_debt -= payment_history.amount
            customer.save()
        return payment_history


class CementTypeForm(forms.ModelForm):
    
    class Meta:
        model = CementType
        fields = ['name', 'color']

    def save(self, commit=True):
        cement_type = super().save(commit=False)
        if commit:
            cement_type.save()
        return cement_type
