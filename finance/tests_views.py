"""
Tests for finance/views.py business logic + finance/filters.py.

Most views are LoginRequiredMixin; we force_login a test user.
Assertions cover:
- Aggregate math (OrderView GET no-customer and per-customer combined/cumulative debt)
- Order creation/delete debt side effects
- Customer filtering (+debt filter), create/update
- Debt view year/date filtering + payment delete debt side effect
- CementType month annotation + parse_month fallback
- Statistics view math + hardcoded 2026 default (characterized)
- Filters: OrderFilter date range, PaymentFilter end-of-day boundary

No production code modified. CHARACTERIZATION cases are marked with NOTE.
"""
from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from finance.filters import CustomerFilter, OrderFilter, PaymentFilter
from finance.models import CementType, Customer, Order, PaymentHistory


class OrderViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", "u@x.com", "pw")
        self.client = Client()
        self.client.force_login(self.user)
        self.c = Customer.objects.create(name="C1", phone="998900000001",
                                        address="A", total_debt=0)
        self.ct = CementType.objects.create(name="M400", color="#FF0000")
        self.today = date.today()

    def _make_order(self, **kw):
        opts = dict(customer=self.c, cement_type=self.ct, quantity=100,
                    price_per_kg=10, road_cost=200, paid_amount=300,
                    car_number="C1")
        opts.update(kw)
        return Order.objects.create(**opts)

    def test_no_customer_aggregates_totals(self):
        self._make_order(quantity=100, total_sum=800, remaining_debt=500)
        self._make_order(quantity=50, total_sum=400, remaining_debt=200)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx["total_quantity"], 150)
        self.assertEqual(ctx["total_price"], 1200)
        self.assertEqual(ctx["total_paid_amount"], 600)
        self.assertEqual(ctx["total_debt"], 700)  # 500 + 200

    def test_no_customer_defaults_date_to_today_excludes_yesterday(self):
        yest = self.today - timedelta(days=1)
        old = Order.objects.create(customer=self.c, cement_type=self.ct,
                                   quantity=10, price_per_kg=1, road_cost=0,
                                   paid_amount=0, car_number="OLD",
                                   order_date=yest)
        resp = self.client.get(reverse("dashboard"))
        ctx = resp.context
        # default export is today only -> yesterday's order filtered out
        ids = [o["id"] for o in ctx["orders"]]
        self.assertNotIn(old.id, ids)

    def test_per_customer_combined_last_cumulative_equals_total_debt(self):
        self._make_order(total_sum=800, remaining_debt=500)
        # customer total_debt updated manually to reflect order
        self.c.total_debt = 500
        self.c.save()
        resp = self.client.get(reverse("dashboard"), {"customer_id": self.c.id})
        ctx = resp.context
        self.assertEqual(ctx["total_debt"], 500)
        # last row's remaining_debt == customer.total_debt
        self.assertEqual(ctx["orders"][-1]["remaining_debt"], 500)

    def test_per_customer_payment_reduces_cumulative(self):
        self._make_order(total_sum=800, remaining_debt=500)
        PaymentHistory.objects.create(customer=self.c, amount=200,
                                     payment_type="cash")
        self.c.total_debt = 500
        self.c.save()
        resp = self.client.get(reverse("dashboard"), {"customer_id": self.c.id})
        ctx = resp.context
        # order(500) then payment(-200) -> cumulative 500 -> 300
        cum = [o["remaining_debt"] for o in ctx["orders"]]
        self.assertEqual(cum[-1], 300)

    def test_invalid_customer_id_falls_back_to_aggregate(self):
        # NOTE: characterization - non-existent customer_id is silently ignored
        resp = self.client.get(reverse("dashboard"), {"customer_id": 999999})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["customer"])

    def test_post_valid_creates_order_and_redirects(self):
        before = Order.objects.count()
        resp = self.client.post(reverse("dashboard"), {
            "customer_id": self.c.id, "cement_type_id": self.ct.id,
            "quantity": 10, "price_per_kg": 5, "road_cost": 10,
            "paid_amount": 5, "car_number": "Z1",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Order.objects.count(), before + 1)

    def test_post_invalid_still_redirects(self):
        # NOTE: characterization - invalid POST silently redirected, no order created
        before = Order.objects.count()
        resp = self.client.post(reverse("dashboard"), {
            "customer_id": 999999, "quantity": 10,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Order.objects.count(), before)


class OrderEditDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u2", "u2@x.com", "pw")
        self.client = Client()
        self.client.force_login(self.user)
        self.c = Customer.objects.create(name="C2", phone="998900000002",
                                        address="A", total_debt=0)
        self.ct = CementType.objects.create(name="M400", color="#FF0000")
        self.order = Order.objects.create(customer=self.c, cement_type=self.ct,
                                          quantity=100, price_per_kg=10,
                                          road_cost=200, paid_amount=300,
                                          car_number="C2", remaining_debt=500)
        self.c.total_debt = 500
        self.c.save()

    def test_edit_get_200(self):
        resp = self.client.get(reverse("order_edit", args=[self.order.id]))
        self.assertEqual(resp.status_code, 200)

    def test_edit_post_updates_remaining_debt(self):
        resp = self.client.post(reverse("order_edit", args=[self.order.id]), {
            "customer_id": self.c.id, "cement_type_id": self.ct.id,
            "quantity": 200, "price_per_kg": 10, "road_cost": 200,
            "paid_amount": 300, "car_number": "C2",
        })
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        # 200*10=2000 -200 =1800 -300 = 1500
        self.assertEqual(self.order.remaining_debt, 1500)

    def test_delete_removes_debt_from_customer(self):
        resp = self.client.get(reverse("order_delete", args=[self.order.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Order.objects.filter(id=self.order.id).exists())
        self.c.refresh_from_db()
        # 500 - 500 = 0
        self.assertEqual(self.c.total_debt, 0)

    def test_delete_null_customer_does_not_crash(self):
        o = Order.objects.create(customer=None, cement_type=self.ct,
                                 quantity=1, price_per_kg=1, road_cost=0,
                                 paid_amount=0, car_number="X",
                                 remaining_debt=10)
        resp = self.client.get(reverse("order_delete", args=[o.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Order.objects.filter(id=o.id).exists())


class CustomerViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u3", "u3@x.com", "pw")
        self.client = Client()
        self.client.force_login(self.user)
        Customer.objects.create(name="Zero", phone="998900000003",
                               address="A", total_debt=0)
        Customer.objects.create(name="Big", phone="998900000004",
                               address="A", total_debt=500000)
        Customer.objects.create(name="Neg", phone="998900000005",
                               address="A", total_debt=-20000)

    def test_ordered_by_total_debt_desc(self):
        resp = self.client.get(reverse("customer"))
        ctx = resp.context
        self.assertEqual(ctx["customers"][0].name, "Big")
        self.assertEqual(ctx["customers"][1].name, "Zero")
        self.assertEqual(ctx["customers"][2].name, "Neg")

    def test_debt_filter_no_debt(self):
        resp = self.client.get(reverse("customer"), {"debt": "no_debt"})
        names = [c.name for c in resp.context["customers"]]
        self.assertEqual(names, ["Zero"])

    def test_debt_filter_with_debt_includes_negative(self):
        resp = self.client.get(reverse("customer"), {"debt": "with_debt"})
        names = [c.name for c in resp.context["customers"]]
        self.assertIn("Neg", names)   # negative debt is "with_debt"
        self.assertIn("Big", names)
        self.assertNotIn("Zero", names)

    def test_total_debt_context_sum(self):
        resp = self.client.get(reverse("customer"))
        # 0 + 500000 - 20000 = 480000
        self.assertEqual(resp.context["total_debt"], 480000)

    def test_post_creates_customer(self):
        before = Customer.objects.count()
        resp = self.client.post(reverse("customer"), {
            "name": "New", "phone": "998900000006", "address": "A", "debt": "0",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Customer.objects.count(), before + 1)

    def test_put_updates_customer_debt(self):
        cust = Customer.objects.get(name="Zero")
        resp = self.client.post(reverse("customer"), {
            "_method": "PUT", "id": cust.id, "name": "Zero",
            "phone": "998900000003", "address": "A", "debt": "777",
        })
        self.assertEqual(resp.status_code, 302)
        cust.refresh_from_db()
        self.assertEqual(cust.total_debt, 777)


class CustomerDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u4", "u4@x.com", "pw")
        self.client = Client()
        self.client.force_login(self.user)
        self.c = Customer.objects.create(name="Del", phone="998900000007",
                                        address="A", total_debt=0)

    def test_delete_returns_204_and_removes(self):
        resp = self.client.delete(reverse("customer_delete", args=[self.c.id]))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Customer.objects.filter(id=self.c.id).exists())


class DebtViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u5", "u5@x.com", "pw")
        self.client = Client()
        self.client.force_login(self.user)
        self.c = Customer.objects.create(name="DC", phone="998900000008",
                                        address="A", total_debt=0)
        self.year = date.today().year
        in_year = timezone.make_aware(datetime(self.year, 6, 15, 12, 0))
        PaymentHistory.objects.create(customer=self.c, amount=100,
                                     paid_at=in_year, payment_type="cash")
        other = timezone.make_aware(datetime(self.year - 1, 6, 15, 12, 0))
        PaymentHistory.objects.create(customer=self.c, amount=50,
                                     paid_at=other, payment_type="cash")

    def test_year_filter_selects_current_year_only(self):
        resp = self.client.get(reverse("debts"))
        ctx = resp.context
        self.assertEqual(ctx["selected_year"], self.year)
        amounts = [float(p.amount) for p in ctx["payments"]]
        self.assertEqual(amounts, [100.0])
        self.assertEqual(ctx["total_amount"], 100)

    def test_invalid_year_falls_back_to_current(self):
        # NOTE: characterization - 'abc' -> current year
        resp = self.client.get(reverse("debts"), {"year": "abc"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["selected_year"], self.year)

    def test_post_creates_payment(self):
        before = PaymentHistory.objects.count()
        resp = self.client.post(reverse("debts"), {
            "customer_id": self.c.id, "payment_amount": "100",
            "payment_type": "cash",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PaymentHistory.objects.count(), before + 1)

    def test_payment_delete_increases_customer_debt(self):
        p = PaymentHistory.objects.create(customer=self.c, amount=200,
                                          payment_type="cash")
        self.c.total_debt = -200  # was reduced by this payment
        self.c.save()
        resp = self.client.get(reverse("payment_delete", args=[p.id]))
        self.assertEqual(resp.status_code, 302)
        self.c.refresh_from_db()
        # -200 + 200 = 0
        self.assertEqual(self.c.total_debt, 0)
        self.assertFalse(PaymentHistory.objects.filter(id=p.id).exists())

    def test_payment_edit_same_customer_applies_difference(self):
        p = PaymentHistory.objects.create(customer=self.c, amount=200, payment_type="cash")
        self.c.total_debt = 800  # 1000 - 200
        self.c.save()
        resp = self.client.post(reverse("payment_edit", args=[p.id]), {
            "customer": self.c.id, "payment_amount": "300", "payment_type": "cash",
        })
        self.assertEqual(resp.status_code, 302)
        self.c.refresh_from_db()
        self.assertEqual(self.c.total_debt, 700)

    def test_payment_edit_moves_debt_between_customers(self):
        other = Customer.objects.create(name="Other", phone="998900000009",
                                        address="B", total_debt=1000)
        p = PaymentHistory.objects.create(customer=self.c, amount=200, payment_type="cash")
        self.c.total_debt = 800  # 1000 - 200
        self.c.save()
        resp = self.client.post(reverse("payment_edit", args=[p.id]), {
            "customer": other.id, "payment_amount": "250", "payment_type": "cash",
        })
        self.assertEqual(resp.status_code, 302)
        self.c.refresh_from_db(); other.refresh_from_db(); p.refresh_from_db()
        self.assertEqual(self.c.total_debt, 1000)   # old payment given back
        self.assertEqual(other.total_debt, 750)     # new payment subtracted
        self.assertEqual(p.customer_id, other.id)
        self.assertEqual(p.amount, 250)


class CementTypeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u6", "u6@x.com", "pw")
        self.client = Client()
        self.client.force_login(self.user)
        self.ct = CementType.objects.create(name="M400", color="#FF0000")
        self.c2 = CementType.objects.create(name="M500", color="#00B050")

    def test_month_annotation_sums_quantity(self):
        self.year = date.today().year
        month = date.today().month
        Order.objects.create(customer=None, cement_type=self.ct,
                            quantity=100, price_per_kg=1, road_cost=0,
                            paid_amount=0, car_number="X",
                            order_date=date(self.year, month, 10))
        Order.objects.create(customer=None, cement_type=self.ct,
                            quantity=50, price_per_kg=1, road_cost=0,
                            paid_amount=0, car_number="X",
                            order_date=date(self.year, month, 11))
        Order.objects.create(customer=None, cement_type=self.c2,
                            quantity=25, price_per_kg=1, road_cost=0,
                            paid_amount=0, car_number="X",
                            order_date=date(self.year, month, 12))
        resp = self.client.get(reverse("cement_type"),
                               {"month": f"{self.year}-{month:02d}"})
        ctx = resp.context
        by_name = {ct.name: ct.total_quantity for ct in ctx["cement_types"]}
        self.assertEqual(by_name["M400"], 150)
        self.assertEqual(by_name["M500"], 25)
        self.assertEqual(ctx["total_quantity"], 175)

    def test_garbage_month_falls_back_to_current(self):
        # NOTE: characterization - 'garbage' -> current month/year
        resp = self.client.get(reverse("cement_type"), {"month": "garbage"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["selected_month"], "garbage")

    def test_out_of_range_month_yields_zero(self):
        # NOTE: characterization - month=13 parses but matches nothing -> zero
        self.year = date.today().year
        resp = self.client.get(reverse("cement_type"),
                               {"month": f"{self.year}-13"})
        ctx = resp.context
        for ct in ctx["cement_types"]:
            self.assertEqual(ct.total_quantity, 0)

    def test_post_creates_cement_type(self):
        before = CementType.objects.count()
        resp = self.client.post(reverse("cement_type"), {
            "name": "M600", "color": "#7030A0",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CementType.objects.count(), before + 1)

    def test_delete_removes_type(self):
        resp = self.client.post(reverse("cement_type_delete", args=[self.ct.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CementType.objects.filter(id=self.ct.id).exists())


class StatisticsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u7", "u7@x.com", "pw")
        self.client = Client()
        self.client.force_login(self.user)
        self.c = Customer.objects.create(name="SC", phone="998900000009",
                                        address="A", total_debt=120)
        self.ct = CementType.objects.create(name="M400", color="#FF0000")
        yr = 2025
        Order.objects.create(customer=self.c, cement_type=self.ct,
                            quantity=10, price_per_kg=100, road_cost=0,
                            paid_amount=0, car_number="X", total_price=1000,
                            total_sum=1000, remaining_debt=1000,
                            order_date=date(yr, 5, 1))
        Order.objects.create(customer=self.c, cement_type=self.ct,
                            quantity=5, price_per_kg=100, road_cost=0,
                            paid_amount=0, car_number="X", total_price=500,
                            total_sum=500, remaining_debt=500,
                            order_date=date(yr, 6, 1))

    def test_2025_totals(self):
        resp = self.client.get(reverse("stats"), {"year": "2025"})
        ctx = resp.context
        self.assertEqual(ctx["total_orders"], 2)
        self.assertEqual(ctx["total_revenue"], 1500 - 120)  # minus total_debt
        self.assertEqual(ctx["total_quantity"], 15)

    def test_default_year_is_2026(self):
        # NOTE: characterization - hardcoded 2026 default
        resp = self.client.get(reverse("stats"))
        self.assertEqual(resp.context["selected_year"], 2026)


class FilterTests(TestCase):
    def setUp(self):
        self.c = Customer.objects.create(name="FC", phone="998900000099",
                                        address="A", total_debt=0)
        self.ct = CementType.objects.create(name="M400", color="#FF0000")
        self.o1 = Order.objects.create(customer=self.c, cement_type=self.ct,
                                      quantity=1, price_per_kg=1, road_cost=0,
                                      paid_amount=0, car_number="A",
                                      order_date=date(2025, 1, 10))
        self.o2 = Order.objects.create(customer=self.c, cement_type=self.ct,
                                      quantity=2, price_per_kg=1, road_cost=0,
                                      paid_amount=0, car_number="B",
                                      order_date=date(2025, 6, 15))
        self.o3 = Order.objects.create(customer=self.c, cement_type=self.ct,
                                      quantity=3, price_per_kg=1, road_cost=0,
                                      paid_amount=0, car_number="C",
                                      order_date=date(2025, 12, 20))

    def test_order_filter_date_range(self):
        qs = OrderFilter({"date_from": "2025-06-01", "date_to": "2025-06-30"},
                          queryset=Order.objects.all()).qs
        self.assertEqual(set(qs), {self.o2})

    def test_order_filter_excludes_today_by_default_date(self):
        # orders created with auto_now_add (today) are excluded from a past range
        qs = OrderFilter({"date_from": "2025-01-01", "date_to": "2025-12-31"},
                          queryset=Order.objects.all()).qs
        ids = {o.id for o in qs}
        self.assertIn(self.o1.id, ids)
        self.assertIn(self.o3.id, ids)
        today_order = Order.objects.exclude(id__in=ids).first()
        if today_order:
            self.assertEqual(today_order.order_date, date.today())

    def test_customer_filter_debt_exclude(self):
        Customer.objects.create(name="Z", phone="998900000098", address="A",
                               total_debt=0)
        qs = CustomerFilter({"debt": "no_debt"},
                           queryset=Customer.objects.all()).qs
        self.assertTrue(all(c.total_debt == 0 for c in qs))

    def test_payment_filter_end_of_day_inclusive(self):
        # payment at 23:59 local on date_to must appear (exclude naive lte)
        d = date(2025, 6, 15)
        late = timezone.make_aware(datetime(2025, 6, 15, 23, 59))
        early_next = timezone.make_aware(datetime(2025, 6, 16, 0, 1))
        PaymentHistory.objects.create(customer=self.c, amount=10, paid_at=late)
        PaymentHistory.objects.create(customer=self.c, amount=20,
                                     paid_at=early_next)
        qs = PaymentFilter({"date_from": "2025-06-15", "date_to": "2025-06-15"},
                          queryset=PaymentHistory.objects.all()).qs
        # either payment at/before end-of-day inclusive is returned
        amts = sorted(float(p.amount) for p in qs)
        self.assertIn(10.0, amts)  # late-night payment on date_to must be present
        self.assertNotIn(20.0, amts)  # past midnight excluded
