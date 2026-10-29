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


class PolishTests(LedgerTestCase):
    def test_amounts_use_non_breaking_spaces_so_they_never_wrap(self):
        from finance.templatetags.custom_filters import format_currency
        self.assertEqual(format_currency(40000000), "40 000 000")
        self.assertEqual(format_currency(-1500), "-1 500")

    def test_order_list_shows_dd_mm_yyyy_on_one_line_and_uses_the_uzbek_date_picker(self):
        self.new_order()
        html = self.client.get(reverse("dashboard") + "?date_from=2000-01-01&date_to=2999-12-31").content.decode()
        order = Order.objects.get()
        self.assertIn(order.order_date.strftime("%d.%m.%Y"), html)
        self.assertNotIn('type="date"', html)
        self.assertEqual(html.count("data-uz-date"), 2 + html.count("input[data-uz-date]"))
        # the filter script reads these ids, so they must stay on the real inputs
        self.assertIn('id="filterDateFrom"', html)
        self.assertIn('id="filterDateTo"', html)

    def test_debt_page_dates_and_amounts(self):
        self.pay("5000000")
        html = self.client.get(reverse("debts")).content.decode()
        payment = PaymentHistory.objects.get()
        self.assertIn(payment.paid_at.astimezone().strftime("%d.%m.%Y"), html)
        self.assertNotRegex(html, r"\d{4}-\d{2}-\d{2}\s*<span")           # the old yyyy-mm-dd + time layout
        self.assertIn("5 000 000&nbsp;so'm", html)
        self.assertNotIn('type="date"', html)
        self.assertIn('class="block text-sm font-medium text-gray-700 mb-1">Mijoz</label>', html)

    def test_cement_type_month_filter_is_an_uzbek_select(self):
        html = self.client.get(reverse("cement_type") + "?month=2026-10").content.decode()
        self.assertIn('<select onchange="setFilter()" name="month" id="filterMonth" data-selected="2026-10"', html)
        self.assertNotIn('type="month"', html)
        self.assertIn("'Oktabr'", html)


class CritiqueFixTests(LedgerTestCase):
    """Fixes that came out of the design critique."""

    def page(self, name, *args):
        return self.client.get(reverse(name, args=args)).content.decode()

    # --- the person is told what happened -------------------------------------------------------------------
    def test_saving_an_order_says_so_with_the_customer_and_the_amounts(self):
        response = self.new_order()
        page = self.client.get(response["Location"]).content.decode()
        self.assertIn('role="alert"', page)
        self.assertIn("Buyurtma saqlandi: Ali", page)
        self.assertIn("qolgan qarz 750", page)

    def test_saving_a_payment_reports_the_customers_new_debt(self):
        self.pay("300")
        page = self.page("debts")
        self.assertIn("To&#x27;lov saqlandi: Ali, 300", page)
        self.assertIn("joriy qarzi: 700", page)

    def test_cash_given_out_is_worded_differently_from_a_payment(self):
        self.pay("-400")
        page = self.page("debts")
        self.assertIn("Mijozga berilgan pul saqlandi: Ali, 400", page)
        self.assertIn("mijozga berilgan pul</span>", page)       # and the history row says so too
        self.assertIn("text-red-700", page)

    def test_deleting_says_so(self):
        self.pay("300")
        payment = PaymentHistory.objects.get()
        self.client.post(reverse("payment_delete", args=[payment.pk]))
        self.assertIn("o&#x27;chirildi", self.page("debts"))

    def test_the_delete_confirmation_names_the_customer_amount_and_date(self):
        self.pay("5000")
        page = self.page("debts")
        self.assertIn("Ali: 5 000 so'm", page)
        self.assertIn("to'lovi o'chirilsinmi?", page)

    # --- customers reach the scripts as data, never pasted into a JS string ------------------------------------
    def test_a_customer_name_with_quotes_backslashes_and_markup_cannot_break_the_page_script(self):
        import json
        import re
        nasty = 'A\\B"\'</script><b>&'
        Customer.objects.create(name=nasty, phone="9", address="z", default_debt=0, total_debt=1234)
        for name in ("dashboard", "debts", "customer"):
            html = self.page(name)
            match = re.search(r'<script id="clients-data" type="application/json">(.*?)</script>', html, re.S)
            self.assertIsNotNone(match, name)
            data = json.loads(match.group(1))
            self.assertIn(nasty, [c["name"] for c in data], name)
            self.assertNotIn("</script><b>", match.group(1))
        debts = json.loads(re.search(r'id="clients-data" type="application/json">(.*?)</script>', self.page("debts"), re.S).group(1))
        self.assertEqual({c["name"]: c["debt"] for c in debts}[nasty], 1234)

    def test_debt_page_shows_the_balance_hint_grouping_and_year_tabs_that_follow_the_calendar(self):
        import datetime
        page = self.page("debts")
        self.assertIn('oninput="groupAmount(this)"', page)
        self.assertIn("Manfiy summa", page)
        self.assertIn('id="clientDebtInfo"', page)
        self.assertIn(f"?year={datetime.date.today().year}", page)
        self.assertNotIn("Bobur Hamroev", page)                   # the dead placeholder text is gone

    # --- one visual dialect -----------------------------------------------------------------------------------
    def test_no_page_uses_the_undefined_glass_card_or_the_hover_lift_on_forms(self):
        import re
        self.new_order()
        order = Order.objects.get()
        self.pay("10")
        payment = PaymentHistory.objects.get()
        urls = [reverse(n) for n in ("dashboard", "customer", "debts", "cement_type", "stats")]
        urls += [reverse("order_edit", args=[order.pk]), reverse("payment_edit", args=[payment.pk])]
        for url in urls:
            html = self.client.get(url).content.decode()
            classes = " ".join(re.findall(r'class="([^"]*)"', html))
            self.assertNotIn("glass-card", classes, url)
            self.assertNotIn("card-hover", classes, url)
            self.assertNotIn("from-green-100", classes, url)

    def test_money_columns_are_right_aligned_tabular_numerals(self):
        self.new_order()
        html = self.client.get(reverse("dashboard") + "?date_from=2000-01-01&date_to=2999-12-31").content.decode()
        self.assertGreaterEqual(html.count("text-right tabular-nums"), 6)

    # --- accessibility ---------------------------------------------------------------------------------------
    def test_every_label_points_at_a_real_field_and_no_id_is_used_twice(self):
        import re
        from collections import Counter
        self.new_order()
        order = Order.objects.get()
        self.pay("10")
        payment = PaymentHistory.objects.get()
        urls = [reverse(n) for n in ("dashboard", "customer", "debts", "cement_type", "stats")]
        urls += [reverse("order_edit", args=[order.pk]), reverse("payment_edit", args=[payment.pk])]
        for url in urls:
            html = self.client.get(url).content.decode()
            ids = Counter(re.findall(r'\sid="([^"]+)"', html))
            self.assertEqual([i for i, n in ids.items() if n > 1], [], f"duplicate ids on {url}")
            for target in re.findall(r'<label[^>]*\sfor="([^"]+)"', html):
                self.assertIn(target, ids, f"label for={target} has no field on {url}")
            self.assertGreaterEqual(len(re.findall(r'<label[^>]*\sfor="', html)), 1 if "<label" in html else 0)

    def test_login_and_edit_pages_use_the_same_font_as_the_rest(self):
        login = Client().get(reverse("login")).content.decode()
        self.assertIn("Onest", login)
        self.assertNotIn("Mona", login)
        self.new_order()
        order = Order.objects.get()
        self.assertNotIn("Mona", self.client.get(reverse("order_edit", args=[order.pk])).content.decode())

    def test_buttons_are_real_buttons_and_nothing_uses_the_invalid_none_type(self):
        self.new_order()
        order = Order.objects.get()
        for html in (self.page("customer"), self.client.get(reverse("order_edit", args=[order.pk])).content.decode()):
            self.assertNotIn('type="none"', html)
        self.assertIn('<button type="button" onclick="deleteCustomer(this)"', self.page("customer"))

    def test_clickable_rows_get_keyboard_support_from_the_base_template(self):
        html = self.page("dashboard")
        self.assertIn("tr[onclick], td[onclick]", html)
        self.assertIn("e.key === 'Enter'", html)


class RegressionFromTheReviewTests(LedgerTestCase):
    """Problems the second critique found in the first round of fixes."""

    def test_the_order_edit_page_defines_its_own_postto_and_esc_so_delete_works(self):
        self.new_order()
        order = Order.objects.get()
        html = self.client.get(reverse("order_edit", args=[order.pk])).content.decode()
        self.assertIn("function postTo(url)", html)
        self.assertIn("function esc(value)", html)
        self.assertIn(f"postTo(`/order/delete/{order.pk}/`)", html)

    def test_names_are_escaped_before_they_go_into_innerhtml_on_every_page(self):
        import pathlib
        for path in sorted(pathlib.Path("templates").glob("*.html")):
            source = path.read_text()
            self.assertNotIn("${client.name}", source, path.name)
            self.assertNotIn("${client.phone}", source, path.name)
            if "innerHTML = `" in source and "client." in source:
                self.assertIn("${esc(client.name)}", source, path.name)
        self.assertIn("function esc(value)", Client().get(reverse("login")).content.decode() + self.client.get(reverse("dashboard")).content.decode())

    def test_a_validation_error_on_the_order_edit_page_is_shown(self):
        self.new_order()
        order = Order.objects.get()
        response = self.client.post(reverse("order_edit", args=[order.pk]), {
            "customer_id": self.customer.pk, "cement_type_id": self.cement.pk, "quantity": 0,
            "price_per_kg": 10, "road_cost": 0, "paid_amount": 0, "car_number": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "Miqdor 0 dan katta")

    def test_login_failures_and_the_lockout_are_visible_in_uzbek(self):
        User.objects.create_user("worker", password="right-pass-123")
        bad = Client().post(reverse("login"), {"username": "worker", "password": "nope"})
        self.assertContains(bad, "Login yoki parol noto&#x27;g&#x27;ri")
        for _ in range(5):
            Client().post(reverse("login"), {"username": "worker", "password": "nope"})
        locked = Client().post(reverse("login"), {"username": "worker", "password": "right-pass-123"})
        self.assertEqual(locked.status_code, 429)
        self.assertContains(locked, "Juda ko&#x27;p noto&#x27;g&#x27;ri urinish", status_code=429)

    def test_the_filter_script_no_longer_calls_a_function_that_does_not_exist(self):
        import pathlib
        for path in pathlib.Path("templates").glob("*.html"):
            self.assertNotIn("filterClientsList()", path.read_text(), path.name)
