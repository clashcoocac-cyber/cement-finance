from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from finance.forms import parse_money
from finance.models import CementType, Customer, Order, PaymentHistory, change_customer_debt


class LedgerTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("clerk", password="pw-clerk-12345", is_staff=True)
        self.client = Client()
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(name="Ali", phone="1", address="x", default_debt=1000, total_debt=1000)
        self.other = Customer.objects.create(name="Vali", phone="2", address="y", default_debt=0, total_debt=0)
        self.cement = CementType.objects.create(name="M400", color="#FF0000")

    def debt(self, customer=None):
        return Customer.objects.get(pk=(customer or self.customer).pk).total_debt

    def expected_debt(self, customer=None):
        customer = customer or self.customer
        orders = sum(o.remaining_debt for o in Order.objects.filter(customer=customer))
        paid = sum(p.amount for p in PaymentHistory.objects.filter(customer=customer))
        return customer.default_debt + orders - int(paid)

    def new_order(self, customer=None, **over):
        data = {"customer_id": (customer or self.customer).pk, "cement_type_id": self.cement.pk, "quantity": 100,
                "price_per_kg": 10, "road_cost": 50, "paid_amount": 200, "car_number": "01A123"}
        data.update(over)
        return self.client.post(reverse("dashboard"), data)

    def pay(self, amount, customer=None, **over):
        data = {"customer_id": (customer or self.customer).pk, "payment_amount": amount, "payment_type": "cash",
                "comment": ""}
        data.update(over)
        return self.client.post(reverse("debts"), data)


class DebtBookkeepingTests(LedgerTestCase):
    def test_new_order_adds_its_remaining_debt(self):
        self.new_order()   # total 1000 - road 50 = 950, paid 200 -> remaining 750
        self.assertEqual(Order.objects.get().remaining_debt, 750)
        self.assertEqual(self.debt(), 1750)
        self.assertEqual(self.debt(), self.expected_debt())

    def test_editing_an_order_moves_only_the_difference(self):
        self.new_order()
        order = Order.objects.get()
        self.client.post(reverse("order_edit", args=[order.pk]), {
            "customer_id": self.customer.pk, "cement_type_id": self.cement.pk, "quantity": 100,
            "price_per_kg": 10, "road_cost": 50, "paid_amount": 950, "car_number": "01A123"})   # now fully paid
        self.assertEqual(self.debt(), 1000)
        self.assertEqual(self.debt(), self.expected_debt())

    def test_moving_an_order_to_another_customer_moves_the_debt_with_it(self):
        self.new_order()
        order = Order.objects.get()
        self.client.post(reverse("order_edit", args=[order.pk]), {
            "customer_id": self.other.pk, "cement_type_id": self.cement.pk, "quantity": 100,
            "price_per_kg": 10, "road_cost": 50, "paid_amount": 200, "car_number": "01A123"})
        self.assertEqual(self.debt(), 1000)
        self.assertEqual(self.debt(self.other), 750)

    def test_deleting_an_order_removes_its_debt_and_needs_a_post(self):
        self.new_order()
        order = Order.objects.get()
        self.assertEqual(self.client.get(reverse("order_delete", args=[order.pk])).status_code, 405)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.client.post(reverse("order_delete", args=[order.pk]))
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.debt(), 1000)

    def test_payments_create_edit_and_delete_keep_the_debt_exact(self):
        self.pay("300")
        self.assertEqual(self.debt(), 700)
        payment = PaymentHistory.objects.get()
        self.client.post(reverse("payment_edit", args=[payment.pk]), {"payment_amount": "500", "payment_type": "cash", "comment": ""})
        self.assertEqual(self.debt(), 500)
        self.assertEqual(self.client.get(reverse("payment_delete", args=[payment.pk])).status_code, 405)
        self.client.post(reverse("payment_delete", args=[payment.pk]))
        self.assertEqual(self.debt(), 1000)
        self.assertEqual(self.debt(), self.expected_debt())

    def test_a_negative_payment_is_money_paid_out_and_raises_the_debt(self):
        # The business records cash given to a customer as a negative payment: it must keep working.
        self.pay("-400")
        self.assertEqual(PaymentHistory.objects.get().amount, Decimal("-400"))
        self.assertEqual(self.debt(), 1400)

    def test_amounts_with_separators_are_read_as_whole_numbers(self):
        self.pay("1 500")
        self.pay("2,500")
        self.pay("3.000")
        self.assertEqual(sorted(int(p.amount) for p in PaymentHistory.objects.all()), [1500, 2500, 3000])

    def test_garbage_amounts_are_refused_with_a_message_not_a_crash(self):
        for bad in ("abc", "12abc", "0", "", "1e5", "--5"):
            with self.subTest(bad=bad):
                response = self.pay(bad)
                self.assertEqual(response.status_code, 302)
        self.assertFalse(PaymentHistory.objects.exists())
        self.assertEqual(self.debt(), 1000)
        page = self.client.get(reverse("debts")).content.decode()
        self.assertIn("role=\"alert\"", page)

    def test_order_numbers_must_make_sense_but_a_negative_road_cost_is_allowed(self):
        self.new_order(quantity=0)
        self.new_order(price_per_kg=-5)
        self.new_order(paid_amount=-1)
        self.assertFalse(Order.objects.exists())
        self.new_order(road_cost=-380)   # a surcharge the business already records
        self.assertEqual(Order.objects.count(), 1)

    def test_change_customer_debt_is_a_single_atomic_update(self):
        with self.assertNumQueries(1):
            change_customer_debt(self.customer.pk, -250)
        self.assertEqual(self.debt(), 750)
        change_customer_debt(None, 5)          # an order without a customer: nothing to move
        change_customer_debt(self.customer.pk, 0)


class OrdersWithoutACustomerTests(LedgerTestCase):
    def orphan(self):
        order = Order.objects.create(customer=self.customer, cement_type=self.cement, quantity=10, price_per_kg=10,
                                     road_cost=0, paid_amount=0, car_number="x")
        Order.objects.filter(pk=order.pk).update(customer=None)   # what deleting the customer used to leave behind
        return Order.objects.get(pk=order.pk)

    def test_such_an_order_can_be_shown_edited_and_deleted_without_a_500(self):
        order = self.orphan()
        self.assertIn("o'chirilgan", str(order))
        self.assertEqual(self.client.get(reverse("order_edit", args=[order.pk])).status_code, 200)
        response = self.client.post(reverse("order_edit", args=[order.pk]), {
            "customer_id": self.other.pk, "cement_type_id": self.cement.pk, "quantity": 10, "price_per_kg": 10,
            "road_cost": 0, "paid_amount": 0, "car_number": "x"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.debt(self.other), 100)            # the order's debt now belongs to its new customer
        Order.objects.filter(pk=order.pk).update(customer=None)
        self.assertEqual(self.client.post(reverse("order_delete", args=[order.pk])).status_code, 302)
        self.assertFalse(Order.objects.exists())


class CustomerDeleteGuardTests(LedgerTestCase):
    def delete(self, customer):
        return self.client.delete(reverse("customer_delete", args=[customer.pk]), HTTP_X_CSRFTOKEN="x")

    def test_a_customer_with_a_debt_orders_or_payments_cannot_be_deleted(self):
        response = self.delete(self.customer)          # owes 1000
        self.assertEqual(response.status_code, 409)
        self.assertIn("o'chirib bo'lmaydi", response.json()["error"])
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())

        self.new_order(self.other)
        Customer.objects.filter(pk=self.other.pk).update(total_debt=0)
        self.assertEqual(self.delete(self.other).status_code, 409)   # still has an order

    def test_a_customer_with_no_trace_can_be_deleted(self):
        clean = Customer.objects.create(name="Nobody", phone="3", address="z", default_debt=0, total_debt=0)
        self.assertEqual(self.delete(clean).status_code, 204)
        self.assertFalse(Customer.objects.filter(pk=clean.pk).exists())


class ParseMoneyTests(TestCase):
    def test_valid_and_invalid_texts(self):
        self.assertEqual(parse_money("1 500 000"), 1500000)
        self.assertEqual(parse_money("1,500,000"), 1500000)
        self.assertEqual(parse_money("-35 000"), -35000)
        self.assertEqual(parse_money("", allow_blank=True), 0)
        for bad in ("abc", "12x", "1e5", "9" * 20, "- 5 -"):
            with self.subTest(bad=bad):
                with self.assertRaises(Exception):
                    parse_money(bad)


class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user("admin1", password="right-pass-123")

    def attempt(self, password, username="admin1"):
        return Client().post(reverse("login"), {"username": username, "password": password})

    def test_five_wrong_passwords_lock_the_username_even_for_the_right_one(self):
        for _ in range(5):
            self.assertEqual(self.attempt("wrong").status_code, 200)
        self.assertEqual(self.attempt("right-pass-123").status_code, 429)

    def test_a_correct_login_resets_the_counter(self):
        for _ in range(4):
            self.attempt("wrong")
        self.assertEqual(self.attempt("right-pass-123").status_code, 302)
        for _ in range(4):
            self.assertEqual(self.attempt("wrong").status_code, 200)


class SettingsSafetyTests(TestCase):
    def test_no_secret_key_is_committed_in_the_settings_file(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent.parent / "config" / "settings.py").read_text()
        self.assertNotIn("django-insecure-nxg", source)
        self.assertIn("config('SECRET_KEY'", source)
        self.assertIn("config('DEBUG', default=False", source)


class StatementBalanceTests(LedgerTestCase):
    """The customer statement's running balance must be right for ANY period, not only one ending today."""

    def setUp(self):
        super().setUp()
        import datetime
        self.d = lambda n: datetime.date(2026, 1, 1) + datetime.timedelta(days=n)
        # customer opens with a debt of 1000; three orders (remaining 500, 300, 200) and two payments
        self.orders = []
        for day, qty in ((10, 50), (40, 30), (70, 20)):
            o = Order.objects.create(customer=self.customer, cement_type=self.cement, quantity=qty, price_per_kg=10,
                                     road_cost=0, paid_amount=0, car_number="x")
            Order.objects.filter(pk=o.pk).update(order_date=self.d(day))
            self.orders.append(o)
        for day, amount in ((20, 100), (60, 250)):
            p = PaymentHistory.objects.create(customer=self.customer, payment_type="cash", amount=amount)
            PaymentHistory.objects.filter(pk=p.pk).update(paid_at=f"{self.d(day)} 12:00:00+00:00")
        Customer.objects.filter(pk=self.customer.pk).update(total_debt=1000 + 500 + 300 + 200 - 100 - 250)

    def last_balance(self, date_from, date_to):
        from finance.views import OrderView
        view = OrderView()
        orders = Order.objects.filter(customer=self.customer, order_date__gte=date_from, order_date__lte=date_to).order_by("order_date")
        payments = view._get_payment_data(self.customer.pk, date_from, date_to)
        customer = Customer.objects.get(pk=self.customer.pk)
        rows = view._calculate_cumulative_debt(view._prepare_combined_data(orders, payments, customer), customer, date_from)
        return rows[-1]["remaining_debt"] if rows else None

    def test_a_period_ending_today_shows_the_current_debt(self):
        self.assertEqual(self.last_balance(self.d(0), self.d(200)), 1650)

    def test_an_early_period_shows_what_was_owed_then_not_todays_debt(self):
        self.assertEqual(self.last_balance(self.d(0), self.d(45)), 1000 + 500 + 300 - 100)   # after order 2, payment 1
        self.assertEqual(self.last_balance(self.d(0), self.d(15)), 1500)

    def test_a_period_starting_midway_opens_with_the_balance_before_it(self):
        # before day 30: 1000 + 500 - 100 = 1400; then order 2 (+300) and payment 2 (-250) and order 3 (+200)
        self.assertEqual(self.last_balance(self.d(30), self.d(200)), 1400 + 300 - 250 + 200)


class StatisticsYearTests(LedgerTestCase):
    def test_defaults_to_the_current_year_and_offers_it_as_a_tab(self):
        import datetime
        year = datetime.date.today().year
        response = self.client.get(reverse("stats"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_year"], year)
        self.assertIn(year, response.context["years"])
        self.assertIn(2024, response.context["years"])
        self.assertEqual(self.client.get(reverse("stats") + "?year=abc").status_code, 200)

    def test_total_debt_is_the_sum_over_all_customers(self):
        response = self.client.get(reverse("stats"))
        self.assertEqual(response.context["total_debt"], 1000)


class StatisticsLabelTests(LedgerTestCase):
    def test_the_debt_card_says_it_is_the_current_state_not_the_selected_year(self):
        html = self.client.get(reverse("stats") + "?year=2025").content.decode()
        self.assertIn("Jami Qarzlar", html)
        self.assertIn("(hozirgi holat)", html)
