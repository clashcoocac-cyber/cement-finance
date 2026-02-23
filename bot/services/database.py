"""
Database service layer for accessing customer data
Uses Django ORM directly with async support
"""
import os
import sys
import django
from pathlib import Path
from typing import Optional, List, Dict
from asgiref.sync import sync_to_async


def setup_django():
    """Set up Django environment"""
    project_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_path))
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()


# Setup Django on import
setup_django()

from finance.models import Customer, Order, PaymentHistory


class CustomerService:
    """Service for accessing customer data"""
    
    @staticmethod
    @sync_to_async
    def get_all_customers() -> List[Dict]:
        """
        Get all customers
        
        Returns:
            List of all customers
        """
        customers = Customer.objects.all().order_by('name')
        
        result = []
        for customer in customers:
            result.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address,
                'default_debt': customer.default_debt,
                'total_debt': customer.total_debt,
            })
        
        return result
    
    @staticmethod
    @sync_to_async
    def get_customer_by_phone(phone: str) -> Optional[Dict]:
        """
        Get customer by phone number
        
        Args:
            phone: Customer phone number
            
        Returns:
            Customer data or None
        """
        try:
            customer = Customer.objects.get(phone=phone)
            return {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address,
                'default_debt': customer.default_debt,
                'total_debt': customer.total_debt,
            }
        except Customer.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def get_customer_orders(customer_id: int) -> List[Dict]:
        """
        Get all orders for a customer
        
        Args:
            customer_id: Customer ID
            
        Returns:
            List of order data
        """
        orders = Order.objects.filter(customer_id=customer_id).select_related(
            'cement_type', 'customer'
        ).order_by('-order_date')
        
        result = []
        for order in orders:
            result.append({
                'id': order.id,
                'cement_type': order.cement_type.name if order.cement_type else 'N/A',
                'quantity': order.quantity,
                'price_per_kg': order.price_per_kg,
                'road_cost': order.road_cost,
                'paid_amount': order.paid_amount,
                'car_number': order.car_number,
                'order_date': order.order_date.strftime('%Y-%m-%d'),
                'total_price': order.total_price,
                'total_sum': order.total_sum,
                'remaining_debt': order.remaining_debt,
            })
        
        return result
    
    @staticmethod
    @sync_to_async
    def get_customer_summary(customer_id: int) -> Dict:
        """
        Get customer summary (total amount, total debt)
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Customer summary data
        """
        customer = Customer.objects.get(id=customer_id)
        orders = Order.objects.filter(customer_id=customer_id)
        
        total_ordered = sum(order.total_sum for order in orders)
        total_paid = sum(order.paid_amount for order in orders)
        total_debt = total_ordered - total_paid
        
        return {
            'total_ordered': total_ordered,
            'total_paid': total_paid,
            'total_debt': total_debt,
            'customer_default_debt': customer.default_debt,
            'orders_count': orders.count(),
        }
    
    @staticmethod
    @sync_to_async
    def get_customer_combined_data(customer_id: int) -> tuple:
        """
        Get combined orders and payments with cumulative debt
        Similar to web app's _calculate_cumulative_debt
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Tuple of (combined_data, customer) with cumulative debt calculated
        """
        customer = Customer.objects.get(id=customer_id)
        orders = Order.objects.filter(customer_id=customer_id).order_by('order_date')
        payments = PaymentHistory.objects.filter(customer_id=customer_id).order_by('paid_at')
        
        combined_data = []
        
        # Add orders
        for order in orders:
            combined_data.append({
                'type': 'order',
                'id': order.id,
                'cement_type': order.cement_type.name if order.cement_type else 'N/A',
                'quantity': order.quantity,
                'price_per_kg': order.price_per_kg,
                'paid_amount': order.paid_amount,
                'date': order.order_date.strftime('%Y-%m-%d'),
                'total_sum': order.total_sum,
                'remaining_debt': order.remaining_debt,
                'car_number': order.car_number,
                'road_cost': order.road_cost,
            })
        
        # Add payments
        for payment in payments:
            payment_type_dict = dict(PaymentHistory.PaymentTypeChoices.choices)
            combined_data.append({
                'type': 'payment',
                'id': payment.id,
                'cement_type': '',
                'quantity': 0,
                'price_per_kg': 0,
                'paid_amount': float(payment.amount),
                'date': payment.paid_at.strftime('%Y-%m-%d'),
                'total_sum': 0,
                'remaining_debt': -float(payment.amount),
                'car_number': '',
                'road_cost': 0,
                'payment_type': payment_type_dict.get(payment.payment_type, payment.payment_type),
                'comment': payment.comment or '',
            })
        
        # Sort by date
        combined_data.sort(key=lambda x: x['date'])
        
        # Calculate cumulative debt
        cumulative_debt = customer.total_debt
        
        # Calculate total from filtered transactions
        total_filtered_debt = sum(
            item['remaining_debt'] for item in combined_data if item['type'] == 'order'
        ) - sum(
            item['paid_amount'] for item in combined_data if item['type'] == 'payment'
        )
        
        # Adjust starting point
        cumulative_debt = cumulative_debt - total_filtered_debt
        
        # Add cumulative debt to each item
        for item in combined_data:
            if item['type'] == 'order':
                cumulative_debt += item['remaining_debt']
            elif item['type'] == 'payment':
                cumulative_debt -= item['paid_amount']
            
            item['cumulative_debt'] = cumulative_debt
        
        return combined_data, customer
