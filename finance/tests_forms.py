"""
Tests for finance/forms.py business logic.

Covers:
- OrderForm: derived-field save side-effect on customer.total_debt, FK existence
  validation, update paths (same + changed customer), debt-difference math.
- CustomerForm: debt-string parsing (commas/spaces/dots), create + update paths.
- PaymentForm: amount parsing, customer.total_debt DECREASE on payment.
- PaymentEditForm: amount-diff debt adjustment on edit.
- CementTypeForm: basic save.

No production code is modified. Characterization tests are marked with a NOTE.
"""
from decimal import Decimal

from django.test import TestCase

from finance.forms import (
    CementTypeForm,
    CustomerForm,
    OrderForm,
    PaymentEditForm,
    PaymentForm,
)
from finance.models import CementType, Customer, Order, PaymentHistory


class OrderFormTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Ali", phone="998900000001", address="Toshkent", total_debt=0
        )
        self.cement = CementType.objects.create(name="M400", color="#FF0000")

    def _order_data(self, **overrides):
        data = {
            "customer_id": self.customer.id,
            "cement_type_id": self.cement.id,
            "quantity": 100,
            "price_per_kg": 10,
            "road_cost": 200,
            "paid_amount": 300,
            "car_number": "01A123BC",
        }
        data.update(overrides)
        return data

    def test_new_order_saves_with_derived_fields(self):
        form = OrderForm(data=self._order_data())
        self.assertTrue(form.is_valid(), form.errors)
        order = form.save()
        # total_price = 100 * 10 = 1000
        # total_sum = 1000 - 200 = 800
        # remaining_debt = 800 - 300 = 500
        order.refresh_from_db()
        self.assertEqual(order.total_price, 1000)
        self.assertEqual(order.total_sum, 800)
        self.assertEqual(order.remaining_debt, 500)
        self.assertEqual(order.customer_id, self.customer.id)
        self.assertEqual(order.cement_type_id, self.cement.id)

    def test_new_order_increases_customer_total_debt(self):
        before = self.customer.total_debt
        form = OrderForm(data=self._order_data())
        self.assertTrue(form.is_valid())
        form.save()
        self.customer.refresh_from_db()
        # remaining_debt 500 -> customer debt goes +500
        self.assertEqual(self.customer.total_debt, before + 500)

    def test_new_order_overpayment_gives_negative_remaining_debt(self):
        form = OrderForm(data=self._order_data(paid_amount=2000))
        self.assertTrue(form.is_valid())
        order = form.save()
        order.refresh_from_db()
        # total_sum 800 - paid 2000 = -1200
        self.assertEqual(order.remaining_debt, -1200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_debt, -1200)

    def test_missing_customer_id_raises_validation_error(self):
        form = OrderForm(data=self._order_data(customer_id=999999))
        self.assertFalse(form.is_valid())
        self.assertIn("Tanlangan mijoz mavjud emas.", form.errors.get("__all__", []))

    def test_missing_cement_type_id_raises_validation_error(self):
        form = OrderForm(data=self._order_data(cement_type_id=999999))
        self.assertFalse(form.is_valid())
        self.assertIn("Tanlangan sement turi mavjud emas.", form.errors.get("__all__", []))

    def test_new_order_does_not_save_when_invalid(self):
        form = OrderForm(data=self._order_data(customer_id=999999))
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValueError):
            form.save()
        self.assertFalse(Order.objects.exists())

    def test_update_same_customer_applies_debt_difference(self):
        order = OrderForm(data=self._order_data()).save()
        cust = Customer.objects.get(id=self.customer.id)
        self.assertEqual(cust.total_debt, 500)

        # Change quantity so remaining_debt swings to 1200 (diff +700)
        form = OrderForm(
            data=self._order_data(quantity=200, price_per_kg=10, road_cost=200,
                                  paid_amount=1000, car_number="01A123BC"),
            instance=order,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        order.refresh_from_db()
        # 200*10=2000; -200 = 1800; -1000 = 800 remaining
        self.assertEqual(order.remaining_debt, 800)
        cust.refresh_from_db()
        # old 500 + diff (800-500)=300 -> 800
        self.assertEqual(cust.total_debt, 800)

    def test_update_changed_customer_moves_debt(self):
        order = OrderForm(data=self._order_data()).save()
        cust_a = Customer.objects.get(id=self.customer.id)
        cust_b = Customer.objects.create(
            name="Bob", phone="998900000002", address="X", total_debt=0
        )
        self.assertEqual(cust_a.total_debt, 500)
        self.assertEqual(cust_b.total_debt, 0)

        # Repoint order to cust_b, keep same derived values (~500)
        form = OrderForm(
            data=self._order_data(
                customer_id=cust_b.id, quantity=100, price_per_kg=10,
                road_cost=200, paid_amount=300, car_number="01A123BC",
            ),
            instance=order,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        cust_a.refresh_from_db()
        cust_b.refresh_from_db()
        # old customer loses old remaining_debt (500 -> 0)
        self.assertEqual(cust_a.total_debt, 0)
        # new customer gains new remaining_debt (500)
        self.assertEqual(cust_b.total_debt, 500)

    def test_update_changed_customer_with_different_debt(self):
        order = OrderForm(data=self._order_data()).save()
        cust_a = Customer.objects.get(id=self.customer.id)
        cust_b = Customer.objects.create(
            name="Bob", phone="998900000003", address="X", total_debt=0
        )

        # New customer, larger order: remaining_debt becomes 5000
        form = OrderForm(
            data=self._order_data(
                customer_id=cust_b.id, quantity=1000, price_per_kg=10,
                road_cost=200, paid_amount=4800, car_number="01A123BC",
            ),
            instance=order,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        order.refresh_from_db()
        self.assertEqual(order.remaining_debt, 5000)

        cust_a.refresh_from_db()
        cust_b.refresh_from_db()
        self.assertEqual(cust_a.total_debt, 0)
        self.assertEqual(cust_b.total_debt, 5000)


class CustomerFormTests(TestCase):
    def test_create_sets_both_total_and_default_debt(self):
        form = CustomerForm(data={
            "name": "New", "phone": "998900000010", "address": "Y",
            "debt": "1,000,000",
        })
        self.assertTrue(form.is_valid(), form.errors)
        cust = form.save()
        self.assertEqual(cust.total_debt, 1000000)
        self.assertEqual(cust.default_debt, 1000000)

    def test_create_with_spaces_and_dots_parsing(self):
        form = CustomerForm(data={
            "name": "New2", "phone": "998900000011", "address": "Y",
            "debt": "1 000.000",
        })
        self.assertTrue(form.is_valid(), form.errors)
        cust = form.save()
        # NOTE: characterization - dots are stripped too, so 1 000.000 -> 1000000
        self.assertEqual(cust.total_debt, 1000000)

    def test_create_empty_debt_defaults_zero(self):
        form = CustomerForm(data={
            "name": "New3", "phone": "998900000012", "address": "Y", "debt": ""
        })
        self.assertTrue(form.is_valid(), form.errors)
        cust = form.save()
        self.assertEqual(cust.total_debt, 0)

    def test_update_sets_total_debt_and_adjusts_default(self):
        cust = Customer.objects.create(
            name="Upd", phone="998900000013", address="Z",
            default_debt=200, total_debt=500,
        )
        form = CustomerForm(
            data={"name": "Upd", "phone": "998900000013", "address": "Z",
                  "debt": "1000"},
            instance=cust,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save(update=True)
        saved.refresh_from_db()
        # total_debt = int(debt) = 1000
        # default_debt = old_default(200) + (1000 - 500) = 700
        self.assertEqual(saved.total_debt, 1000)
        self.assertEqual(saved.default_debt, 700)

    def test_update_from_zero_to_debt(self):
        cust = Customer.objects.create(
            name="Upd2", phone="998900000014", address="Z",
            default_debt=0, total_debt=0,
        )
        form = CustomerForm(
            data={"name": "Upd2", "phone": "998900000014", "address": "Z",
                  "debt": "250"},
            instance=cust,
        )
        self.assertTrue(form.is_valid())
        saved = form.save(update=True)
        saved.refresh_from_db()
        self.assertEqual(saved.total_debt, 250)
        self.assertEqual(saved.default_debt, 250)


class PaymentFormTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="PayC", phone="998900000020", address="P", total_debt=1000
        )

    def test_valid_payment_decreases_customer_debt(self):
        form = PaymentForm(data={
            "customer_id": self.customer.id,
            "payment_amount": "500",
            "payment_type": "cash",
            "comment": "test",
        })
        self.assertTrue(form.is_valid(), form.errors)
        payment = form.save()
        payment.refresh_from_db()
        self.assertEqual(payment.customer_id, self.customer.id)
        self.assertEqual(payment.amount, Decimal("500"))
        self.customer.refresh_from_db()
        # 1000 - 500 = 500
        self.assertEqual(self.customer.total_debt, 500)

    def test_payment_amount_with_commas(self):
        form = PaymentForm(data={
            "customer_id": self.customer.id,
            "payment_amount": "1,000,000",
        })
        self.assertTrue(form.is_valid(), form.errors)
        payment = form.save()
        # NOTE: characterization - commas stripped, 1000000
        self.assertEqual(payment.amount, Decimal("1000000"))

    def test_payment_amount_with_dot_strips_decimals(self):
        # NOTE: characterization - parse strips '.', so "1,000,000.50" -> 100000050
        form = PaymentForm(data={
            "customer_id": self.customer.id,
            "payment_amount": "1,000,000.50",
        })
        self.assertTrue(form.is_valid(), form.errors)
        payment = form.save()
        self.assertEqual(payment.amount, Decimal("100000050"))

    def test_invalid_customer_id_raises_on_save(self):
        form = PaymentForm(data={
            "customer_id": 999999, "payment_amount": "100",
        })
        self.assertTrue(form.is_valid())
        from finance.models import Customer
        with self.assertRaises(Customer.DoesNotExist):
            form.save()


class PaymentEditFormTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="EdC", phone="998900000030", address="E", total_debt=1000
        )
        self.payment = PaymentHistory.objects.create(
            customer=self.customer, amount=Decimal("400"),
            payment_type="cash",
        )

    def test_edit_increase_amount_decreases_debt_by_difference(self):
        # old amount 400, new 600 -> difference +200 -> debt -= 200: 1000-200=800
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_debt, 1000)
        form = PaymentEditForm(
            data={"customer": self.customer.id, "payment_amount": "600", "payment_type": "cash"},
            instance=self.payment,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount, Decimal("600"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_debt, 800)

    def test_edit_decrease_amount_increases_debt_by_difference(self):
        form = PaymentEditForm(
            data={"customer": self.customer.id, "payment_amount": "200", "payment_type": "cash"},
            instance=self.payment,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount, Decimal("200"))
        self.customer.refresh_from_db()
        # 1000 - (200-400) = 1000 + 200 = 1200
        self.assertEqual(self.customer.total_debt, 1200)

    def test_edit_initial_populated_from_instance(self):
        form = PaymentEditForm(instance=self.payment)
        self.assertEqual(form.fields["payment_amount"].initial, str(self.payment.amount))


class CementTypeFormTests(TestCase):
    def test_valid_save(self):
        form = CementTypeForm(data={"name": "M500", "color": "#00B050"})
        self.assertTrue(form.is_valid(), form.errors)
        ct = form.save()
        self.assertEqual(ct.name, "M500")
        self.assertEqual(ct.color, "#00B050")
