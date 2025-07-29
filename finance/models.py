from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    total_debt = models.IntegerField(default=0)

    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.name


class CementType(models.Model):

    class ColorChoices(models.TextChoices):
        BLUE = '🟦', "🟦 Ko'k"
        GREEN = '🟩', "🟩 Yashil"
        RED = "🟥", "🟥 Qizil"
        YELLOW = "🟨", "🟨 Sariq"

    name = models.CharField(max_length=50)
    color = models.CharField(max_length=10, choices=ColorChoices)

    class Meta:
        db_table = 'cement_types'
        verbose_name = 'Cement Type'
        verbose_name_plural = 'Cement Types'

    def __str__(self):
        return self.name


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, related_name='orders', null=True)
    cement_type = models.ForeignKey(CementType, on_delete=models.SET_NULL, related_name='orders', null=True)
    
    quantity = models.IntegerField(verbose_name="Quantity (kgs)")
    price_per_kg = models.IntegerField()
    road_cost = models.IntegerField()
    paid_amount = models.IntegerField()
    car_number = models.CharField(max_length=20)
    order_date = models.DateField(auto_now_add=True)

    total_price = models.IntegerField()  
    total_sum = models.IntegerField()    
    remaining_debt = models.IntegerField()

    class Meta:
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price_per_kg
        self.total_sum = self.total_price - self.road_cost
        self.remaining_debt = self.total_sum - self.paid_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.name} - {self.cement_type.name} - {self.order_date}"
    

class PaymentHistory(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='payment_histories')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_histories'
        verbose_name = 'Payment History'
        verbose_name_plural = 'Payment Histories'

    def __str__(self):
        return f"{self.customer.name} - {self.amount} so'm - {self.paid_at.strftime('%Y-%m-%d %H:%M')}"

