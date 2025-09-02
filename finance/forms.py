from django import forms
from finance.models import Customer, CementType, Order, PaymentHistory


class OrderForm(forms.ModelForm):    
    customer_id = forms.IntegerField()
    cement_type_id = forms.IntegerField()

    class Meta:
        model = Order
        fields = ['customer_id', 'cement_type_id', 'quantity', 'price_per_kg', 'road_cost', 'paid_amount', 'car_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial values for customer_id and cement_type_id if instance exists
        if self.instance and self.instance.pk:
            self.fields['customer_id'].initial = self.instance.customer.id if self.instance.customer else None
            self.fields['cement_type_id'].initial = self.instance.cement_type.id if self.instance.cement_type else None

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate that customer and cement_type exist
        customer_id = cleaned_data.get('customer_id')
        cement_type_id = cleaned_data.get('cement_type_id')
        
        if customer_id:
            try:
                Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                raise forms.ValidationError("Tanlangan mijoz mavjud emas.")
        
        if cement_type_id:
            try:
                CementType.objects.get(id=cement_type_id)
            except CementType.DoesNotExist:
                raise forms.ValidationError("Tanlangan sement turi mavjud emas.")
        
        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        order.customer = Customer.objects.get(id=self.cleaned_data['customer_id'])
        order.cement_type = CementType.objects.get(id=self.cleaned_data['cement_type_id'])
        
        if commit:
            # If this is an update, we need to handle the debt calculation properly
            if self.instance.pk:  # This is an update
                old_order = Order.objects.get(pk=self.instance.pk)
                old_remaining_debt = old_order.remaining_debt
                old_customer = old_order.customer
                
                # Save the updated order
                order.save()
                new_remaining_debt = order.remaining_debt
                
                # If customer changed, we need to update both customers' debts
                if old_customer != order.customer:
                    # Remove debt from old customer
                    old_customer.total_debt -= old_remaining_debt
                    old_customer.save()
                    
                    # Add debt to new customer
                    order.customer.total_debt += new_remaining_debt
                    order.customer.save()
                else:
                    # Same customer, just update the debt difference
                    debt_difference = new_remaining_debt - old_remaining_debt
                    order.customer.total_debt += debt_difference
                    order.customer.save()
            else:  # This is a new order
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
