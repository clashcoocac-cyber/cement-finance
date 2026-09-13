from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from finance.models import CementType, Customer, Order, PaymentHistory


def make_customer(**kwargs):
    defaults = dict(name="Test Customer", phone="+998901234567", address="Tashkent")
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_cement_type(**kwargs):
    defaults = dict(name="M400", color="#FF0000")
    defaults.update(kwargs)
    return CementType.objects.create(**defaults)


def make_order(**kwargs):
    defaults = dict(
        customer=make_customer(),
        cement_type=make_cement_type(),
        quantity=1000,
        price_per_kg=5000,
        road_cost=100000,
        paid_amount=2000000,
        car_number="01A123BB",
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


class OrderSaveDerivedFieldsTests(TestCase):
    def test_basic_derived_fields(self):
        order = make_order(quantity=1000, price_per_kg=5000, road_cost=100000, paid_amount=2000000)
        self.assertEqual(order.total_price, 5_000_000)
        self.assertEqual(order.total_sum, 4_900_000)
        self.assertEqual(order.remaining_debt, 2_900_000)

    def test_road_cost_zero(self):
        order = make_order(quantity=100, price_per_kg=2000, road_cost=0, paid_amount=0)
        self.assertEqual(order.total_price, 200_000)
        self.assertEqual(order.total_sum, 200_000)
        self.assertEqual(order.remaining_debt, 200_000)

    def test_paid_amount_zero(self):
        order = make_order(quantity=500, price_per_kg=4000, road_cost=50_000, paid_amount=0)
        self.assertEqual(order.total_sum, 1_950_000)
        self.assertEqual(order.remaining_debt, 1_950_000)

    def test_full_payment_leaves_zero_remaining_debt(self):
        order = make_order(quantity=1000, price_per_kg=5000, road_cost=0, paid_amount=5_000_000)
        self.assertEqual(order.remaining_debt, 0)

    def test_overpayment_produces_negative_remaining_debt(self):
        order = make_order(quantity=100, price_per_kg=1000, road_cost=0, paid_amount=500_000)
        self.assertEqual(order.total_sum, 100_000)
        self.assertEqual(order.remaining_debt, -400_000)

    def test_zero_quantity(self):
        order = make_order(quantity=0, price_per_kg=5000, road_cost=10_000, paid_amount=0)
        self.assertEqual(order.total_price, 0)
        self.assertEqual(order.total_sum, -10_000)
        self.assertEqual(order.remaining_debt, -10_000)

    def test_negative_road_cost_increases_total_sum(self):
        order = make_order(quantity=100, price_per_kg=1000, road_cost=-5_000, paid_amount=0)
        self.assertEqual(order.total_price, 100_000)
        self.assertEqual(order.total_sum, 105_000)
        self.assertEqual(order.remaining_debt, 105_000)

    def test_negative_price_per_kg(self):
        order = make_order(quantity=10, price_per_kg=-100, road_cost=0, paid_amount=0)
        self.assertEqual(order.total_price, -1_000)
        self.assertEqual(order.total_sum, -1_000)
        self.assertEqual(order.remaining_debt, -1_000)

    def test_very_large_values(self):
        # 10**6 * 10**12 = 10**18, fits in a signed 64-bit integer.
        order = make_order(quantity=1_000_000, price_per_kg=10**12, road_cost=1, paid_amount=2)
        self.assertEqual(order.total_price, 10**18)
        self.assertEqual(order.total_sum, 10**18 - 1)
        self.assertEqual(order.remaining_debt, 10**18 - 3)

    def test_resave_recomputes_derived_fields(self):
        order = make_order(quantity=1000, price_per_kg=5000, road_cost=100_000, paid_amount=2_000_000)
        order.quantity = 2000
        order.road_cost = 0
        order.paid_amount = 9_000_000
        order.save()
        self.assertEqual(order.total_price, 10_000_000)
        self.assertEqual(order.total_sum, 10_000_000)
        self.assertEqual(order.remaining_debt, 1_000_000)

        refreshed = Order.objects.get(pk=order.pk)
        self.assertEqual(refreshed.total_price, 10_000_000)
        self.assertEqual(refreshed.total_sum, 10_000_000)
        self.assertEqual(refreshed.remaining_debt, 1_000_000)

    def test_derived_fields_survive_reload(self):
        order = make_order(quantity=7, price_per_kg=13, road_cost=5, paid_amount=3)
        refreshed = Order.objects.get(pk=order.pk)
        self.assertEqual(refreshed.total_price, 91)
        self.assertEqual(refreshed.total_sum, 86)
        self.assertEqual(refreshed.remaining_debt, 83)

    def test_save_with_update_fields_persists_listed_fields_only(self):
        # NOTE: characterization - save(update_fields=[...]) recomputes the
        # derived fields in memory but persists only the listed ones, so the
        # DB's derived columns go stale. Documents the current behavior;
        # callers must list the derived fields themselves.
        order = make_order(quantity=1000, price_per_kg=5000, road_cost=0, paid_amount=0)
        order.quantity = 2000
        order.save(update_fields=["quantity"])

        refreshed = Order.objects.get(pk=order.pk)
        self.assertEqual(refreshed.quantity, 2000)  # listed field persisted
        self.assertEqual(refreshed.total_price, 5_000_000)  # stale, not recomputed
        self.assertEqual(refreshed.total_sum, 5_000_000)
        self.assertEqual(refreshed.remaining_debt, 5_000_000)

        # The in-memory instance did get the recomputed values.
        self.assertEqual(order.total_price, 10_000_000)

    def test_order_date_set_automatically(self):
        # Bounds mirror test_paid_at_auto_now_add: auto_now_add must write
        # today's date, not just any non-null value.
        before = timezone.localdate()
        order = make_order()
        after = timezone.localdate()
        self.assertLessEqual(before, order.order_date)
        self.assertLessEqual(order.order_date, after)


class OrderForeignKeyNullabilityTests(TestCase):
    def test_save_with_null_customer(self):
        order = make_order(customer=None)
        self.assertIsNone(order.customer_id)
        refreshed = Order.objects.get(pk=order.pk)
        self.assertIsNone(refreshed.customer_id)
        self.assertEqual(refreshed.total_price, 5_000_000)

    def test_save_with_null_cement_type(self):
        order = make_order(cement_type=None)
        self.assertIsNone(order.cement_type_id)
        refreshed = Order.objects.get(pk=order.pk)
        self.assertIsNone(refreshed.cement_type_id)
        self.assertEqual(refreshed.total_sum, 4_900_000)

    def test_save_with_both_fks_null(self):
        order = make_order(customer=None, cement_type=None)
        refreshed = Order.objects.get(pk=order.pk)
        self.assertIsNone(refreshed.customer_id)
        self.assertIsNone(refreshed.cement_type_id)

    def test_customer_delete_nulls_order_fk(self):
        order = make_order()
        customer = order.customer
        customer.delete()
        order.refresh_from_db()
        self.assertIsNone(order.customer_id)

    def test_cement_type_delete_nulls_order_fk(self):
        order = make_order()
        cement_type = order.cement_type
        cement_type.delete()
        order.refresh_from_db()
        self.assertIsNone(order.cement_type_id)

    def test_str_with_null_foreign_keys(self):
        # NOTE: characterization - __str__ dereferences customer.name and
        # cement_type.name without guards, so null-FK orders (allowed by
        # SET_NULL) raise AttributeError when rendered.
        order = make_order(customer=None, cement_type=None)
        with self.assertRaises(AttributeError):
            str(order)

    def test_str_with_fully_populated_order(self):
        customer = make_customer(name="Ali Voki")
        cement_type = make_cement_type(name="M400 D20")
        order = make_order(customer=customer, cement_type=cement_type)
        # Substring assertions: don't re-encode the exact __str__ format so
        # legitimate formatting refactors don't break the test.
        self.assertIn(customer.name, str(order))
        self.assertIn(cement_type.name, str(order))


class PaymentHistoryTests(TestCase):
    # Single smoke check that the three payment types exist and resolve for
    # forms/validation; the enum in models.py is the source of truth, so no
    # duplicated value/label data tables here.
    def test_payment_type_values_available(self):
        values = dict(PaymentHistory.PaymentTypeChoices.choices)
        for value in ("bank", "cash", "click"):
            self.assertIn(value, values)
            self.assertEqual(
                value, getattr(PaymentHistory.PaymentTypeChoices, value.upper()).value
            )

    def test_amount_accepts_two_decimal_places(self):
        payment = PaymentHistory.objects.create(
            customer=make_customer(),
            payment_type=PaymentHistory.PaymentTypeChoices.CASH,
            amount=Decimal("123.45"),
        )
        refreshed = PaymentHistory.objects.get(pk=payment.pk)
        self.assertEqual(refreshed.amount, Decimal("123.45"))

    def test_amount_with_third_decimal_on_sqlite(self):
        # NOTE: characterization - SQLite does not round 10.005 to 10.01 like
        # PostgreSQL would; it stores the truncated value 10.00. Do not rely
        # on DB-level rounding for amounts with extra precision.
        payment = PaymentHistory.objects.create(
            customer=make_customer(),
            amount=Decimal("10.005"),
        )
        refreshed = PaymentHistory.objects.get(pk=payment.pk)
        self.assertEqual(refreshed.amount, Decimal("10.00"))

    def test_paid_at_auto_now_add(self):
        before = timezone.now()
        payment = PaymentHistory.objects.create(customer=make_customer(), amount=Decimal("1.00"))
        after = timezone.now()
        self.assertIsNotNone(payment.paid_at)
        self.assertLessEqual(before, payment.paid_at)
        self.assertLessEqual(payment.paid_at, after)

    def test_paid_at_only_frozen_on_insert(self):
        # NOTE: characterization - auto_now_add only applies when the row is
        # first inserted; a later save() persists whatever value the field
        # currently holds, so paid_at is not protected against updates.
        payment = PaymentHistory.objects.create(customer=make_customer(), amount=Decimal("1.00"))
        fixed = payment.paid_at
        payment.paid_at = fixed.replace(year=2000)
        payment.save()
        refreshed = PaymentHistory.objects.get(pk=payment.pk)
        self.assertEqual(refreshed.paid_at.year, 2000)

    def test_str_format(self):
        payment = PaymentHistory.objects.create(
            customer=make_customer(name="Ali"),
            amount=Decimal("1500.50"),
        )
        # Substring assertions only: the exact separator/timestamp layout is an
        # implementation detail, but name, amount and date must appear.
        self.assertIn("Ali", str(payment))
        self.assertIn("1500.50", str(payment))
        self.assertIn(payment.paid_at.strftime("%Y-%m-%d"), str(payment))

    def test_payment_type_can_be_null(self):
        payment = PaymentHistory.objects.create(customer=make_customer(), amount=Decimal("1.00"))
        self.assertIsNone(payment.payment_type)
        refreshed = PaymentHistory.objects.get(pk=payment.pk)
        self.assertIsNone(refreshed.payment_type)

    def test_deleting_customer_cascades_to_payments(self):
        customer = make_customer()
        PaymentHistory.objects.create(customer=customer, amount=Decimal("1.00"))
        PaymentHistory.objects.create(customer=customer, amount=Decimal("2.00"))
        customer.delete()
        self.assertEqual(PaymentHistory.objects.count(), 0)


class CustomerTests(TestCase):
    def test_default_debts_default_to_zero(self):
        customer = Customer.objects.create(name="A", phone="1", address="Tashkent")
        self.assertEqual(customer.default_debt, 0)
        self.assertEqual(customer.total_debt, 0)

    def test_debts_can_be_negative_and_large(self):
        customer = make_customer(default_debt=-500, total_debt=10**12)
        refreshed = Customer.objects.get(pk=customer.pk)
        self.assertEqual(refreshed.default_debt, -500)
        self.assertEqual(refreshed.total_debt, 10**12)

    def test_str_returns_name(self):
        customer = make_customer(name="Vali")
        self.assertEqual(str(customer), "Vali")

    def test_related_orders_and_payments(self):
        customer = make_customer()
        make_order(customer=customer)
        make_order(customer=customer)
        PaymentHistory.objects.create(customer=customer, amount=Decimal("1.00"))
        self.assertEqual(customer.orders.count(), 2)
        self.assertEqual(customer.payment_histories.count(), 1)


class CementTypeTests(TestCase):
    def test_valid_color_choice_saves(self):
        cement_type = make_cement_type(name="M500", color="#00B050")
        refreshed = CementType.objects.get(pk=cement_type.pk)
        self.assertEqual(refreshed.color, "#00B050")

    def test_invalid_color_rejected_by_full_clean(self):
        cement_type = CementType(name="M500", color="#FFFFFF")
        with self.assertRaises(ValidationError) as ctx:
            cement_type.full_clean()
        self.assertIn("color", ctx.exception.message_dict)

    def test_invalid_color_still_saves_at_db_level(self):
        # NOTE: characterization - Django choices are not DB-enforced, so an
        # invalid color persists via .save() without full_clean(); apps must
        # rely on forms/full_clean for validation.
        cement_type = CementType.objects.create(name="Off-brand", color="#FFFFFF")
        refreshed = CementType.objects.get(pk=cement_type.pk)
        self.assertEqual(refreshed.color, "#FFFFFF")

    def test_str_returns_name(self):
        cement_type = make_cement_type(name="M400 D20")
        self.assertEqual(str(cement_type), "M400 D20")

    def test_every_declared_choice_saves_and_full_clean_passes(self):
        for value, _label in CementType.COLOR_CHOICES:
            cement_type = CementType(name=f"T-{value}", color=value)
            cement_type.full_clean()
            cement_type.save()
        self.assertEqual(CementType.objects.count(), len(CementType.COLOR_CHOICES))
