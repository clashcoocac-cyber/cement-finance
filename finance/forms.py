import re

from django import forms
from django.db import transaction

from finance.models import Customer, CementType, Order, PaymentHistory, change_customer_debt


def parse_money(text, allow_blank=False):
    """Whole so'm typed by a person: spaces, commas and dots are thousands separators ('1 500 000', '1,500,000',
    '1.500.000'); a leading minus is allowed (money paid out to a customer is recorded as a negative payment).
    Anything else (letters, '12abc') is refused instead of crashing the page or becoming a different amount."""
    cleaned = re.sub(r'[\s,.]', '', text or '')
    if not cleaned:
        if allow_blank:
            return 0
        raise forms.ValidationError("Summani kiriting.")
    if not re.fullmatch(r'-?\d{1,15}', cleaned):
        raise forms.ValidationError("Summani faqat raqamlarda kiriting (masalan 1 500 000).")
    return int(cleaned)


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
        
        # road_cost may be negative (a surcharge/credit the business already uses); the rest cannot
        if cleaned_data.get('quantity') is not None and cleaned_data['quantity'] <= 0:
            self.add_error('quantity', "Miqdor 0 dan katta bo'lishi kerak.")
        for name in ('price_per_kg', 'paid_amount'):
            if cleaned_data.get(name) is not None and cleaned_data[name] < 0:
                self.add_error(name, "Qiymat manfiy bo'lishi mumkin emas.")

        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        order.customer = Customer.objects.get(id=self.cleaned_data['customer_id'])
        order.cement_type = CementType.objects.get(id=self.cleaned_data['cement_type_id'])
        
        if commit:
            with transaction.atomic():
                if self.instance.pk:  # update: move the difference between the old and the new remaining debt
                    old_order = Order.objects.get(pk=self.instance.pk)
                    old_remaining_debt = old_order.remaining_debt
                    old_customer_id = old_order.customer_id   # None for an order whose customer was deleted
                    order.save()
                    if old_customer_id == order.customer_id:
                        change_customer_debt(order.customer_id, order.remaining_debt - old_remaining_debt)
                    else:
                        change_customer_debt(old_customer_id, -old_remaining_debt)
                        change_customer_debt(order.customer_id, order.remaining_debt)
                else:  # new order
                    order.save()
                    change_customer_debt(order.customer_id, order.remaining_debt)

        return order


class CustomerForm(forms.ModelForm):
    debt = forms.CharField(required=False, initial='0')

    class Meta:
        model = Customer
        fields = ['name', 'phone', 'address', 'debt']

    def clean_debt(self):
        return parse_money(self.cleaned_data.get('debt'), allow_blank=True)

    def save(self, commit=True, update=False):
        customer = super().save(commit=False)
        debt = self.cleaned_data.get('debt') or 0

        if commit:
            if update:
                old_debt = customer.default_debt
                old_total_debt = customer.total_debt
                debt_difference = int(debt) - old_total_debt
                customer.total_debt = int(debt)
                customer.default_debt = old_debt + debt_difference
                customer.save()
            else:
                customer.total_debt = int(debt)
                customer.default_debt = int(debt)
            customer.save()
        return customer


class PaymentForm(forms.ModelForm):
    customer_id = forms.IntegerField()
    payment_amount = forms.CharField()
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Izoh qoldiring...'}))

    class Meta:
        model = PaymentHistory
        fields = ['customer_id', 'payment_amount', 'payment_type', 'comment']

    def clean_payment_amount(self):
        amount = parse_money(self.cleaned_data['payment_amount'])
        if amount == 0:
            raise forms.ValidationError("To'lov summasi 0 bo'lishi mumkin emas.")
        return amount

    def clean_customer_id(self):
        customer_id = self.cleaned_data['customer_id']
        if not Customer.objects.filter(id=customer_id).exists():
            raise forms.ValidationError("Tanlangan mijoz mavjud emas.")
        return customer_id

    def save(self, commit=True):
        payment_history = super().save(commit=False)
        payment_history.customer = Customer.objects.get(id=self.cleaned_data['customer_id'])
        if commit:
            with transaction.atomic():
                payment_history.amount = self.cleaned_data['payment_amount']
                payment_history.save()
                change_customer_debt(payment_history.customer_id, -payment_history.amount)
        return payment_history


class PaymentEditForm(forms.ModelForm):
    payment_amount = forms.CharField()
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Izoh qoldiring...'}))

    class Meta:
        model = PaymentHistory
        fields = ['payment_amount', 'payment_type', 'comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial value for payment_amount if instance exists
        if self.instance and self.instance.pk:
            self.fields['payment_amount'].initial = str(self.instance.amount)

    def clean_payment_amount(self):
        amount = parse_money(self.cleaned_data['payment_amount'])
        if amount == 0:
            raise forms.ValidationError("To'lov summasi 0 bo'lishi mumkin emas.")
        return amount

    def save(self, commit=True):
        payment_history = super().save(commit=False)
        if commit:
            with transaction.atomic():
                old_amount = PaymentHistory.objects.get(pk=self.instance.pk).amount
                new_amount = self.cleaned_data['payment_amount']
                payment_history.amount = new_amount
                payment_history.save()
                # the customer's debt moves by the difference
                change_customer_debt(payment_history.customer_id, old_amount - new_amount)
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
