"""Tests for finance/excel_views.py — the four .xlsx export views."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook

from finance.excel_views import OrderExportView
from finance.models import CementType, Customer, Order, PaymentHistory

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def make_customer(**kwargs):
    defaults = dict(name="Test Customer", phone="+998901234567", address="Tashkent")
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_cement_type(**kwargs):
    defaults = dict(name="M400", color="#FF0000")
    defaults.update(kwargs)
    return CementType.objects.create(**defaults)


def make_order(**kwargs):
    # Create related objects lazily so overriding them doesn't leave stray rows
    if "customer" not in kwargs:
        kwargs["customer"] = make_customer()
    if "cement_type" not in kwargs:
        kwargs["cement_type"] = make_cement_type()
    defaults = dict(
        quantity=1000,
        price_per_kg=5000,
        road_cost=100000,
        paid_amount=2000000,
        car_number="01A123BB",
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


def make_payment(**kwargs):
    if "customer" not in kwargs:
        kwargs["customer"] = make_customer()
    defaults = dict(
        payment_type="cash",
        amount=Decimal("100000"),
        comment="olindi",
    )
    defaults.update(kwargs)
    return PaymentHistory.objects.create(**defaults)


def set_order_date(order, new_date):
    """auto_now_add ignores assigned dates on insert; fix up afterwards."""
    Order.objects.filter(pk=order.pk).update(order_date=new_date)


def set_paid_at(payment, new_dt):
    PaymentHistory.objects.filter(pk=payment.pk).update(paid_at=new_dt)


def utc_dt(*args):
    """Aware UTC datetime so the stored value renders back unchanged."""
    return datetime(*args, tzinfo=timezone.utc)


def _fake_request(url):
    """Bare request for calling export views directly (bypasses the test
    client's debug-page rendering, which crashes on Python 3.14)."""
    from django.http import HttpRequest, QueryDict

    path, _, query = url.partition("?")
    request = HttpRequest()
    request.method = "GET"
    request.path = path
    request.META = {"QUERY_STRING": query, "REQUEST_METHOD": "GET"}
    request.GET = QueryDict(query)
    return request


class ExcelExportTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="tester", password="pass12345")

    def setUp(self):
        self.client.force_login(self.user)

    def load_wb(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], XLSX_CONTENT_TYPE)
        wb = load_workbook(BytesIO(resp.content))
        return resp, wb, wb.active

    @staticmethod
    def grid(ws, row_start, row_end, ncols):
        return [
            [ws.cell(row=r, column=c).value for c in range(1, ncols + 1)]
            for r in range(row_start, row_end + 1)
        ]

    @staticmethod
    def as_date(value):
        return value.date() if isinstance(value, datetime) else value


class LoginRequiredTests(ExcelExportTestCase):
    def test_anonymous_gets_redirect_for_all_export_views(self):
        self.client.logout()
        for url in (
            "/export/orders/",
            "/export/customers/",
            "/export/debts/",
            "/export/cement-types/",
        ):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/login/", resp.url)


class OrderExportViewTests(ExcelExportTestCase):
    def test_no_customer_rows_totals_and_hozirgi_qarz(self):
        big = make_order(
            quantity=1_500_000,
            price_per_kg=12345,
            road_cost=250_000,
            paid_amount=18_000_000_000,
            car_number="01A111AA",
        )  # total_sum=18_517_500_000-250_000=18_517_250_000, remaining=517_250_000
        small = make_order(
            quantity=50,
            price_per_kg=2000,
            road_cost=0,
            paid_amount=50_000,
            car_number="02B222BB",
        )  # total_sum=100_000, remaining=50_000

        resp, wb, ws = self.load_wb("/export/orders/")

        self.assertTrue(
            resp["Content-Disposition"].startswith(
                'attachment; filename="buyurtmalar_hisoboti_'
            )
        )
        self.assertTrue(resp["Content-Disposition"].endswith('.xlsx"'))
        self.assertEqual(ws.title, "Buyurtmalar")
        self.assertEqual(
            ws.cell(row=1, column=1).value,
            "BUYURTMALAR HISOBOTI — Barcha mijozlar",
        )

        data_rows = self.grid(ws, 5, 6, 10)
        by_car = {row[3]: row for row in data_rows}
        self.assertEqual(by_car["01A111AA"][1], big.customer.name)
        self.assertEqual(by_car["01A111AA"][2], big.cement_type.name)
        self.assertEqual(by_car["01A111AA"][4], 1_500_000)
        self.assertEqual(by_car["01A111AA"][5], 12345)
        self.assertEqual(by_car["01A111AA"][6], 250_000)
        self.assertEqual(by_car["01A111AA"][7], 18_517_250_000)
        self.assertEqual(by_car["01A111AA"][8], 18_000_000_000)
        self.assertEqual(by_car["01A111AA"][9], 517_250_000)
        self.assertEqual(self.as_date(by_car["02B222BB"][0]), date.today())
        self.assertEqual(by_car["02B222BB"][7], 100_000)
        self.assertEqual(by_car["02B222BB"][9], 50_000)

        totals = self.grid(ws, 7, 7, 10)[0]
        self.assertEqual(totals[0], "JAMI:")
        self.assertEqual(totals[4], 1_500_050)  # quantity sum
        self.assertEqual(totals[8], 18_000_050_000)  # paid sum
        self.assertEqual(totals[9], 517_300_000)  # sum of remaining_debt

        self.assertEqual(ws.cell(row=9, column=1).value, "Hozirgi qarz:")
        self.assertEqual(ws.cell(row=9, column=2).value, 517_300_000)

    def test_payment_rows_in_combined_customer_export(self):
        customer = make_customer(name="Qarzdor Ali", total_debt=60_000)
        order = make_order(
            customer=customer,
            cement_type=make_cement_type(name="M500"),
            quantity=100,
            price_per_kg=1000,
            road_cost=0,
            paid_amount=40_000,
            car_number="99C999CC",
        )  # total_sum=100_000, remaining=60_000
        payment = make_payment(
            customer=customer,
            amount=Decimal("30000"),
            payment_type="click",
            comment="birinchi to'lov",
        )
        set_order_date(order, date(2026, 8, 1))
        set_paid_at(payment, utc_dt(2026, 8, 5, 10, 0))

        resp, wb, ws = self.load_wb("/export/orders/?customer_id=%d" % customer.pk)

        self.assertEqual(
            ws.cell(row=1, column=1).value,
            "BUYURTMALAR HISOBOTI — Qarzdor Ali",
        )
        self.assertEqual(
            ws.cell(row=2, column=1).value,
            "Mijoz: Qarzdor Ali   Eski qarz: 60,000 so'm",
        )

        rows = self.grid(ws, 5, 6, 10)
        order_row, payment_row = rows

        self.assertEqual(order_row[1], "Qarzdor Ali")
        self.assertEqual(order_row[2], "M500")
        self.assertEqual(order_row[3], "99C999CC")
        self.assertEqual(self.as_date(order_row[0]), date(2026, 8, 1))
        self.assertEqual(order_row[9], 90_000)  # cumulative after the order

        self.assertEqual(payment_row[2], "To'lov")
        self.assertEqual(payment_row[3], "birinchi to'lov")
        # Money columns for payments are left empty (None) up to Olingan/Qarz
        self.assertIsNone(payment_row[4])
        self.assertIsNone(payment_row[5])
        self.assertIsNone(payment_row[6])
        self.assertIsNone(payment_row[7])
        self.assertEqual(int(payment_row[8]), 30000)  # Olingan
        self.assertEqual(int(payment_row[9]), 60_000)  # cumulative ends at total_debt

        totals = self.grid(ws, 7, 7, 10)[0]
        self.assertEqual(totals[0], "JAMI:")
        self.assertEqual(totals[4], 100)  # only order quantity counts
        self.assertEqual(int(totals[8]), 70_000)  # order paid + payment amount
        self.assertEqual(totals[9], 60_000)  # customer.total_debt

        self.assertEqual(ws.cell(row=9, column=1).value, "Hozirgi qarz:")
        self.assertEqual(ws.cell(row=9, column=2).value, 60_000)

    def test_multiple_orders_and_interleaved_payments_cumulative_debt(self):
        # Two orders with a payment dated BETWEEN them: rows still come out
        # orders-then-payments (orders by +order_date, payments by -paid_at),
        # and each Qarz cell carries the running total ending at total_debt.
        customer = make_customer(name="Yigindi", total_debt=150_000)
        cement = make_cement_type(name="M400")
        order1 = make_order(
            customer=customer, cement_type=cement, quantity=10,
            price_per_kg=1000, road_cost=0, paid_amount=0, car_number="AA1",
        )  # remaining 10_000
        order2 = make_order(
            customer=customer, cement_type=cement, quantity=20,
            price_per_kg=1000, road_cost=0, paid_amount=0, car_number="AA2",
        )  # remaining 20_000
        between = make_payment(
            customer=customer, amount=Decimal("30000"), comment=None
        )
        after = make_payment(customer=customer, amount=Decimal("25000"), comment=None)
        set_order_date(order1, date(2026, 8, 1))
        set_order_date(order2, date(2026, 8, 10))
        set_paid_at(between, utc_dt(2026, 8, 5, 12, 0))
        set_paid_at(after, utc_dt(2026, 8, 20, 12, 0))

        # Window includes both orders and only the between-payment.
        resp, wb, ws = self.load_wb(
            "/export/orders/?customer_id=%d&date_from=2026-08-01&date_to=2026-08-10"
            % customer.pk
        )

        rows = self.grid(ws, 5, 7, 10)
        # Orders come first (by +order_date), then the payment (by -paid_at)
        # even though the payment is dated between the two orders.
        # Note: blank styled cells (payment car_number "") round-trip as None
        # through openpyxl save/load.
        self.assertEqual([row[3] for row in rows], ["AA1", None, "AA2"])
        self.assertEqual([row[2] for row in rows], ["M400", "To'lov", "M400"])
        # Cumulative: 150k start, +10k, -30k, +20k -> ends at total_debt.
        self.assertEqual([row[9] for row in rows], [160_000, 130_000, 150_000])

        totals = self.grid(ws, 8, 8, 10)[0]
        self.assertEqual(totals[4], 30)  # only order quantities
        self.assertEqual(int(totals[8]), 30_000)  # order paid (0) + payment
        self.assertEqual(totals[9], 150_000)  # customer.total_debt

    def test_overpaid_order_negative_remaining_debt_included_in_totals(self):
        make_order(quantity=100, price_per_kg=1000, road_cost=0, paid_amount=500_000)
        make_order(quantity=10, price_per_kg=1000, road_cost=0, paid_amount=0)

        resp, wb, ws = self.load_wb("/export/orders/")
        data_rows = self.grid(ws, 5, 6, 10)
        debts = sorted(row[9] for row in data_rows)
        self.assertEqual(debts, [-400_000, 10_000])

        totals = self.grid(ws, 7, 7, 10)[0]
        self.assertEqual(totals[9], -390_000)
        self.assertEqual(ws.cell(row=9, column=2).value, -390_000)

    def test_nonnumeric_customer_id_raises_value_error(self):
        # NOTE: characterization - Customer.objects.get(id="abc") raises
        # ValueError (not DoesNotExist), which the view's except clause does
        # not catch, so ?customer_id=abc bubbles out of the view (500 in
        # production). Pin it until the view also catches ValueError.
        view = OrderExportView()
        with self.assertRaises(ValueError):
            view.get(_fake_request("/export/orders/?customer_id=abc"))

    def test_order_dated_yesterday_excluded_from_default_export(self):
        # Default no-params export injects date_from=date_to=today; an order
        # dated yesterday must not appear even though it exists.
        old = make_order(car_number="OLD1", quantity=10, price_per_kg=1000)
        set_order_date(old, date.today() - timedelta(days=1))
        today = make_order(car_number="TOD1", quantity=20, price_per_kg=1000)

        resp, wb, ws = self.load_wb("/export/orders/")
        rows = self.grid(ws, 5, 5, 10)[0]
        self.assertEqual(rows[3], "TOD1")

        resp, wb, ws = self.load_wb(
            "/export/orders/?date_from=%s&date_to=%s"
            % (date.today().isoformat(), date.today().isoformat())
        )
        rows = self.grid(ws, 5, 5, 10)[0]
        self.assertEqual(rows[3], "TOD1")

        # Explicit window covering yesterday brings the old order back.
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp, wb, ws = self.load_wb(
            "/export/orders/?date_from=%s&date_to=%s" % (yesterday, yesterday)
        )
        rows = self.grid(ws, 5, 5, 10)[0]
        self.assertEqual(rows[3], "OLD1")

    def test_nonexistent_customer_id_gives_empty_report_with_zero_totals(self):
        resp, wb, ws = self.load_wb("/export/orders/?customer_id=999999")

        # NOTE: characterization - bogus customer_id silently falls back to the
        # "all customers" report instead of erroring, and the customer filter
        # leaves zero rows; JAMI/Hozirgi qarz show 0.
        self.assertEqual(
            ws.cell(row=1, column=1).value,
            "BUYURTMALAR HISOBOTI — Barcha mijozlar",
        )
        totals = self.grid(ws, 5, 5, 10)[0]
        self.assertEqual(totals[0], "JAMI:")
        self.assertEqual(totals[4], 0)
        self.assertEqual(totals[8], 0)
        self.assertEqual(totals[9], 0)
        self.assertEqual(ws.cell(row=7, column=2).value, 0)


class CustomerExportViewTests(ExcelExportTestCase):
    def test_rows_ordered_by_total_debt_desc_and_jami_row(self):
        make_customer(name="Katta", total_debt=500_000)
        make_customer(name="Nol", total_debt=0)
        make_customer(name="Manfil", total_debt=-20_000)

        resp, wb, ws = self.load_wb("/export/customers/")

        self.assertTrue(
            resp["Content-Disposition"].startswith(
                'attachment; filename="mijozlar_royxati_'
            )
        )
        self.assertEqual(ws.cell(row=1, column=1).value, "MIJOZLAR RO'YXATI")

        rows = self.grid(ws, 4, 6, 5)
        self.assertEqual([r[0] for r in rows], [1, 2, 3])
        self.assertEqual([r[1] for r in rows], ["Katta", "Nol", "Manfil"])
        self.assertEqual([r[4] for r in rows], [500_000, 0, -20_000])

        jami = self.grid(ws, 7, 7, 5)[0]
        self.assertEqual(jami[0], "JAMI:")
        self.assertEqual(jami[4], 480_000)

    def test_negative_debt_customer_counts_as_with_debt(self):
        # CustomerFilter uses exclude(total_debt=0), so overpaid customers
        # (negative debt) land in with_debt, not no_debt.
        make_customer(name="Manfil", total_debt=-20_000)
        make_customer(name="Nol", total_debt=0)

        resp, wb, ws = self.load_wb("/export/customers/?debt=with_debt")
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[1], "Manfil")

        resp, wb, ws = self.load_wb("/export/customers/?debt=no_debt")
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[1], "Nol")

    def test_debt_filter_with_debt_and_no_debt(self):
        make_customer(name="Katta", total_debt=500_000)
        make_customer(name="Nol", total_debt=0)

        resp, wb, ws = self.load_wb("/export/customers/?debt=with_debt")
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[1], "Katta")
        self.assertEqual(self.grid(ws, 5, 5, 5)[0][4], 500_000)  # JAMI

        resp, wb, ws = self.load_wb("/export/customers/?debt=no_debt")
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[1], "Nol")
        self.assertEqual(self.grid(ws, 5, 5, 5)[0][4], 0)

    def test_empty_customer_table_shows_zero_jami(self):
        resp, wb, ws = self.load_wb("/export/customers/")
        jami = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(jami[0], "JAMI:")
        self.assertEqual(jami[4], 0)


class DebtExportViewTests(ExcelExportTestCase):
    def test_year_rows_payment_type_display_and_jami(self):
        customer = make_customer(name="To'lovchi")
        p1 = make_payment(
            customer=customer, amount=Decimal("15000.50"), payment_type="cash"
        )
        p2 = make_payment(
            customer=customer, amount=25000, payment_type="bank", comment="bank orqali"
        )
        make_payment(
            customer=customer, amount=999_999, payment_type="click", comment=None
        )  # 2026 payment, must not appear for 2025
        set_paid_at(p1, utc_dt(2025, 3, 10, 14, 30))
        set_paid_at(p2, utc_dt(2025, 7, 1, 9, 15))

        resp, wb, ws = self.load_wb(
            "/export/debts/?year=2025&date_from=2025-01-01&date_to=2025-12-31"
        )

        self.assertTrue(
            resp["Content-Disposition"].startswith(
                'attachment; filename="qarz_tovlovlari_'
            )
        )
        self.assertEqual(ws.cell(row=1, column=1).value, "QARZ TO'LOVLARI — 2025-yil")

        rows = self.grid(ws, 4, 5, 5)
        # ordered by -paid_at: July first
        self.assertEqual(rows[0][0], "2025-07-01 09:15")
        self.assertEqual(rows[0][1], "To'lovchi")
        self.assertEqual(int(rows[0][2]), 25000)
        self.assertEqual(rows[0][3], "Pul ko'chirish")
        self.assertEqual(rows[0][4], "bank orqali")
        self.assertEqual(rows[1][0], "2025-03-10 14:30")
        self.assertEqual(rows[1][3], "Naqd")

        jami = self.grid(ws, 6, 6, 5)[0]
        self.assertEqual(jami[0], "JAMI:")
        self.assertEqual(jami[2], Decimal("40000.50"))

    def test_invalid_year_falls_back_to_current_year(self):
        customer = make_customer(name="Hozirgi")
        current = make_payment(customer=customer, amount=12345)
        old = make_payment(customer=customer, amount=777_777)
        set_paid_at(old, utc_dt(2020, 1, 1, 8, 0))

        resp, wb, ws = self.load_wb(
            "/export/debts/?year=notanumber&date_from=2000-01-01&date_to=2099-12-31"
        )
        self.assertEqual(
            ws.cell(row=1, column=1).value,
            "QARZ TO'LOVLARI — %d-yil" % date.today().year,
        )
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[1], "Hozirgi")
        self.assertEqual(int(rows[2]), 12345)

        jami = self.grid(ws, 5, 5, 5)[0]
        self.assertEqual(jami[2], 12345)

    def test_no_query_params_defaults_to_today(self):
        # UI link path: /export/debts/ with no query string defaults year,
        # date_from and date_to to today — only today's payment may appear.
        customer = make_customer(name="Bugun")
        todays = make_payment(customer=customer, amount=Decimal("5000"))
        earlier = make_payment(customer=customer, amount=Decimal("654321"))
        set_paid_at(earlier, utc_dt(2020, 1, 1, 8, 0))

        resp, wb, ws = self.load_wb("/export/debts/")
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[1], "Bugun")
        self.assertEqual(int(rows[2]), 5000)

        jami = self.grid(ws, 5, 5, 5)[0]
        self.assertEqual(jami[2], Decimal("5000"))

    def test_year_with_no_payments_shows_zero_jami(self):
        make_payment(amount=Decimal("50000"))
        resp, wb, ws = self.load_wb(
            "/export/debts/?year=1999&date_from=1999-01-01&date_to=1999-12-31"
        )
        jami = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(jami[0], "JAMI:")
        self.assertEqual(jami[2], 0)

    def test_null_payment_type_shows_dash(self):
        p = make_payment(payment_type=None)
        set_paid_at(p, utc_dt(2024, 5, 5, 12, 0))
        resp, wb, ws = self.load_wb(
            "/export/debts/?year=2024&date_from=2024-01-01&date_to=2024-12-31"
        )
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[3], "-")

    def test_date_to_includes_last_minute_and_excludes_next_day(self):
        # filter_date_to is exclusive next-day local midnight (paid_at <
        # date_to+1 00:00 local), so the last minute of date_to appears and
        # one minute past local midnight does not.
        # NOTE: paid_at is stored as UTC and PaymentHistory.__str__/export
        # cells render the stored instant verbatim (UTC), while the local
        # zone is Asia/Tashkent (UTC+5). Local 23:59 on date_to == 18:59 UTC;
        # local 00:01 next day == 19:01 UTC the same calendar day.
        customer = make_customer(name="Chegara")
        inside = make_payment(customer=customer, amount=Decimal("111"))
        outside = make_payment(customer=customer, amount=Decimal("222"))
        set_paid_at(inside, utc_dt(2025, 12, 31, 18, 59))
        set_paid_at(outside, utc_dt(2025, 12, 31, 19, 1))

        resp, wb, ws = self.load_wb(
            "/export/debts/?year=2025&date_from=2025-12-31&date_to=2025-12-31"
        )
        rows = self.grid(ws, 4, 4, 5)[0]
        self.assertEqual(rows[0], "2025-12-31 18:59")
        self.assertEqual(int(rows[2]), 111)
        jami = self.grid(ws, 5, 5, 5)[0]
        self.assertEqual(jami[2], Decimal("111"))

        # A naive paid_at__lte=date cutoff (midnight UTC) would drop the
        # 18:59 payment and show JAMI: 0.
        self.assertEqual(jami[2], Decimal("111"))


class CementTypeExportViewTests(ExcelExportTestCase):
    def test_month_quantity_sums_jami_and_color_display(self):
        qizil = make_cement_type(name="M400", color="#FF0000")
        yashil = make_cement_type(name="M500", color="#00B050")
        bosh = make_cement_type(name="M600", color="#808080")  # no orders at all

        o1 = make_order(cement_type=qizil, quantity=1200, price_per_kg=1000)
        o2 = make_order(cement_type=qizil, quantity=800, price_per_kg=1000)
        o3 = make_order(cement_type=yashil, quantity=500, price_per_kg=1000)
        o4 = make_order(cement_type=yashil, quantity=9999, price_per_kg=1000)
        set_order_date(o1, date(2026, 8, 10))
        set_order_date(o2, date(2026, 8, 20))
        set_order_date(o3, date(2026, 8, 15))
        set_order_date(o4, date(2026, 7, 15))  # other month, excluded

        resp, wb, ws = self.load_wb("/export/cement-types/?month=2026-08")

        self.assertTrue(
            resp["Content-Disposition"].startswith(
                'attachment; filename="sement_turlari_'
            )
        )
        self.assertEqual(ws.cell(row=1, column=1).value, "SEMENT TURLARI — 2026-08")

        by_name = {
            row[0]: row for row in self.grid(ws, 4, 6, 3)
        }
        self.assertEqual(by_name["M400"][1], "Qizil")
        self.assertEqual(by_name["M400"][2], 2000)  # 1200 + 800
        self.assertEqual(by_name["M500"][1], "Yashil")
        self.assertEqual(by_name["M500"][2], 500)
        self.assertEqual(by_name["M600"][1], "Kulrang")
        self.assertEqual(by_name["M600"][2], 0)  # no orders -> 0 via _money

        jami = self.grid(ws, 7, 7, 3)[0]
        self.assertEqual(jami[0], "Jami:")
        self.assertEqual(jami[2], 2500)

    def test_out_of_range_month_silently_yields_zero_report(self):
        # NOTE: characterization - "2026-13"/"2026-00" pass int() parsing and
        # the month filter matches nothing, so every quantity is 0 (no
        # fallback to the current month like non-numeric input).
        ct = make_cement_type(name="M800", color="#000000")
        order = make_order(cement_type=ct, quantity=333, price_per_kg=1000)
        set_order_date(order, date.today())

        for month in ("2026-13", "2026-00"):
            with self.subTest(month=month):
                resp, wb, ws = self.load_wb(f"/export/cement-types/?month={month}")
                self.assertEqual(ws.cell(row=1, column=1).value, f"SEMENT TURLARI — {month}")
                rows = self.grid(ws, 4, 4, 3)[0]
                self.assertEqual(rows[0], "M800")
                self.assertEqual(rows[2], 0)
                self.assertEqual(self.grid(ws, 5, 5, 3)[0][2], 0)

    def test_partial_month_string_uses_that_month(self):
        # ?month=2026-1 parses to January 2026 (no ValueError, so no
        # fallback) — a January order appears, today's does not.
        ct = make_cement_type(name="M900", color="#FFA500")
        jan = make_order(cement_type=ct, quantity=444, price_per_kg=1000)
        set_order_date(jan, date(2026, 1, 15))

        resp, wb, ws = self.load_wb("/export/cement-types/?month=2026-1")
        rows = {row[0]: row for row in self.grid(ws, 4, 4, 3)}
        self.assertEqual(rows["M900"][2], 444)

    def test_invalid_month_uses_current_month(self):
        ct = make_cement_type(name="M700", color="#0070C0")
        order = make_order(cement_type=ct, quantity=777, price_per_kg=1000)
        set_order_date(order, date.today())

        resp, wb, ws = self.load_wb("/export/cement-types/?month=garbage")
        # NOTE: characterization - title keeps the raw invalid input while the
        # data silently falls back to the current month.
        self.assertEqual(
            ws.cell(row=1, column=1).value, "SEMENT TURLARI — garbage"
        )
        rows = self.grid(ws, 4, 4, 3)[0]
        self.assertEqual(rows[0], "M700")
        self.assertEqual(rows[2], 777)
        self.assertEqual(self.grid(ws, 5, 5, 3)[0][2], 777)
