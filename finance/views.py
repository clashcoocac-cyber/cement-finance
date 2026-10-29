import hashlib
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView as LView
from django.core.cache import cache
from django.db import models, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import make_naive
from django.views import View

from finance.filters import CustomerFilter, OrderFilter, PaymentFilter
from finance.forms import (
    CementTypeForm,
    CustomerForm,
    OrderForm,
    PaymentEditForm,
    PaymentForm,
)
from finance.models import CementType, Customer, Order, PaymentHistory, change_customer_debt
from finance.templatetags.custom_filters import format_currency


MAX_FAILED_LOGINS = 5          # per username from one address
MAX_FAILED_LOGINS_PER_IP = 30   # per address, across usernames
LOCKOUT_SECONDS = 15 * 60


def _client_ip(request):
    """nginx sets X-Real-IP; the socket peer is nginx itself."""
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")


def _count_failure(key):
    cache.add(key, 0, LOCKOUT_SECONDS)
    try:
        cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, LOCKOUT_SECONDS)


class UzbekAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Login yoki parol noto'g'ri. Ikkalasini ham tekshirib, qayta urinib ko'ring.",
        "inactive": "Bu hisob faol emas.",
    }


class LoginView(LView):
    """Sign-in with a brake on password guessing: 5 wrong tries per username (30 per address), then 15 minutes."""
    template_name = "login.html"
    authentication_form = UzbekAuthenticationForm
    redirect_authenticated_user = True

    def _throttle_keys(self):
        ip = _client_ip(self.request)
        username = (self.request.POST.get("username") or "").strip().lower()[:150]
        digest = hashlib.sha256(username.encode()).hexdigest()[:32]
        return f"login-fail:{ip}:{digest}", f"login-fail-ip:{ip}"

    def post(self, request, *args, **kwargs):
        user_key, ip_key = self._throttle_keys()
        if cache.get(user_key, 0) >= MAX_FAILED_LOGINS or cache.get(ip_key, 0) >= MAX_FAILED_LOGINS_PER_IP:
            form = self.get_form()
            form.add_error(None, "Juda ko'p noto'g'ri urinish. 15 daqiqadan keyin qayta urinib ko'ring.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        for key in self._throttle_keys():
            _count_failure(key)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._throttle_keys()[0])
        return super().form_valid(form)


class LogoutView(View):
    def get(self, request):
        from django.contrib.auth import logout

        logout(request)
        return redirect("login")


def money(value):
    """An amount for a message: 1 500 000 (non-breaking spaces)."""
    return format_currency(value)


def year_choices(selected_year, first_year=None):
    """Year tabs: from 2024 (or the first year with data) to the current year, so they grow with the calendar."""
    today = date.today()
    start = min(2024, first_year or today.year, selected_year)
    return list(range(start, max(today.year, selected_year) + 1))


def flash_errors(request, form):
    """Tell the person why a form was not saved (the pages used to drop invalid input without a word)."""
    for errors in form.errors.values():
        for error in errors:
            messages.error(request, error)


class OrderView(LoginRequiredMixin, View):
    template_name = "order.html"

    def _get_payment_data(self, customer_id, date_from=None, date_to=None):
        """Get payment data for a specific customer with optional date filtering"""
        payments = PaymentHistory.objects.filter(customer_id=customer_id)

        # Apply date filtering if provided
        if date_from:
            payments = payments.filter(paid_at__date__gte=date_from)
        if date_to:
            payments = payments.filter(paid_at__date__lte=date_to)

        return payments.order_by("-paid_at")

    def _prepare_combined_data(self, orders, payments, customer):
        """Combine order and payment data into a single list"""
        combined_data = []

        # Add orders
        for order in orders:
            combined_data.append(
                {
                    "type": "order",
                    "id": order.id,
                    "customer": order.customer if order.customer else "",
                    "cement_type": order.cement_type if order.cement_type else "",
                    "quantity": order.quantity,
                    "price_per_kg": order.price_per_kg,
                    "paid_amount": order.paid_amount,
                    "order_date": order.order_date,
                    "total_price": order.total_price,
                    "total_sum": order.total_sum,
                    "road_cost": order.road_cost,
                    "car_number": order.car_number,
                    "remaining_debt": order.remaining_debt,
                }
            )

        # Add payments
        for payment in payments:
            combined_data.append(
                {
                    "type": "payment",
                    "id": payment.id,
                    "customer": payment.customer,
                    "cement_type": "",  # Payments don't have cement type
                    "quantity": 0,  # Payments don't have quantity
                    "price_per_kg": 0,  # Payments don't have price
                    "paid_amount": payment.amount,  # Negative because it reduces received amount
                    "order_date": payment.paid_at.date(),
                    "total_price": 0,  # Payments don't have total price
                    "total_sum": 0,  # Payments don't contribute to total sum
                    "road_cost": 0,  # Payments don't have road cost
                    "car_number": "",  # Payments don't have car number
                    "remaining_debt": -payment.amount,  # Negative because it reduces debt
                    "payment_type": payment.payment_type,
                    "comment": payment.comment,  # Add comment from payment
                }
            )

        combined_data.sort(key=lambda x: x["order_date"])
        return combined_data

    def _opening_balance(self, customer, date_from):
        """What the customer owed just before `date_from` (or at the very start when there is no date)."""
        balance = customer.default_debt   # the opening debt; manual corrections of the debt are folded into it
        if date_from:
            orders = Order.objects.filter(customer=customer, order_date__lt=date_from).aggregate(
                total=models.Sum("remaining_debt"))["total"] or 0
            paid = PaymentHistory.objects.filter(customer=customer, paid_at__date__lt=date_from).aggregate(
                total=models.Sum("amount"))["total"] or 0
            balance += orders - int(paid)
        return balance

    def _calculate_cumulative_debt(self, combined_data, customer, date_from=None):
        """Running balance after each line. It starts from the real balance before the period, so it is
        right for any period (it used to count back from today's debt, which is only right when the period
        ends today)."""
        cumulative_debt = self._opening_balance(customer, date_from)

        for item in combined_data:
            if item["type"] == "order":
                cumulative_debt += item["remaining_debt"]
            elif item["type"] == "payment":
                cumulative_debt -= item["paid_amount"]

            # Update remaining_debt to show cumulative value
            item["remaining_debt"] = cumulative_debt

        return combined_data

    def get(self, request):
        query_params = request.GET.copy()
        if not query_params.get("customer_id"):
            query_params["date_from"] = query_params.get("date_from") or date.today()
            query_params["date_to"] = query_params.get("date_to") or date.today()

        # Get filtered orders
        filtered_orders = OrderFilter(
            query_params,
            queryset=Order.objects.order_by("order_date").select_related(
                "customer", "cement_type"
            ),
        ).qs

        customer = None
        if request.GET.get("customer_id"):
            try:
                customer = Customer.objects.get(id=request.GET.get("customer_id"))
            except Customer.DoesNotExist:
                pass

        if customer:
            date_from = query_params.get("date_from")
            date_to = query_params.get("date_to")
            payments = self._get_payment_data(customer.id, date_from, date_to)

            # Combine orders and payments
            combined_data = self._prepare_combined_data(
                filtered_orders, payments, customer
            )

            # Calculate cumulative debt for each transaction
            combined_data = self._calculate_cumulative_debt(combined_data, customer, date_from)

            total_quantity = sum(
                item["quantity"] for item in combined_data if item["type"] == "order"
            )
            total_price = sum(
                item["total_sum"] for item in combined_data if item["type"] == "order"
            )  # Only orders contribute to total price
            total_paid_amount = sum(
                item["paid_amount"] for item in combined_data if item["type"] == "order"
            ) + sum(
                item["paid_amount"]
                for item in combined_data
                if item["type"] == "payment"
            )  # Orders + negative payments = net received
            total_debt = customer.total_debt  # Use customer's actual total debt

            order_data = combined_data
        else:
            # Calculate order totals only
            order_aggs = filtered_orders.aggregate(
                total_quantity=models.Sum("quantity"),
                total_price=models.Sum("total_sum"),
                total_paid_amount=models.Sum("paid_amount"),
                total_debt=models.Sum("remaining_debt"),
            )

            totals = {
                "total_quantity": order_aggs["total_quantity"] or 0,
                "total_price": order_aggs["total_price"] or 0,
                "total_paid_amount": order_aggs["total_paid_amount"] or 0,
                "total_debt": order_aggs["total_debt"] or 0,
            }

            # Prepare order data
            order_data = [
                {
                    "type": "order",
                    "id": order.id,
                    "customer": order.customer,
                    "cement_type": order.cement_type,
                    "quantity": order.quantity,
                    "price_per_kg": order.price_per_kg,
                    "paid_amount": order.paid_amount,
                    "order_date": order.order_date,
                    "total_price": order.total_price,
                    "total_sum": order.total_sum,
                    "road_cost": order.road_cost,
                    "car_number": order.car_number,
                    "remaining_debt": order.remaining_debt,
                }
                for order in filtered_orders
            ]

            total_quantity = totals["total_quantity"]
            total_price = totals["total_price"]
            total_paid_amount = totals["total_paid_amount"]
            total_debt = totals["total_debt"]

        context = {
            "orders": order_data,
            "customers": Customer.objects.all(),
            "cement_types": CementType.objects.all(),
            "today": date.today().strftime("%Y-%m-%d"),
            "total_quantity": total_quantity,
            "total_price": total_price,
            "total_paid_amount": total_paid_amount,
            "total_debt": total_debt,
            "page": "dashboard",
            "customer": customer,
        }

        return render(request, self.template_name, context=context)

    def post(self, request):
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save()
            messages.success(
                request,
                f"Buyurtma saqlandi: {order.customer.name}, jami {money(order.total_sum)} so'm, "
                f"qolgan qarz {money(order.remaining_debt)} so'm.",
            )
        else:
            flash_errors(request, form)
        return redirect("dashboard")


class OrderEditView(LoginRequiredMixin, View):
    template_name = "order_edit.html"

    def get_context(self, form, order):
        return {
            "form": form,
            "order": order,
            "customers": Customer.objects.all(),
            "cement_types": CementType.objects.all(),
            "page": "dashboard",
        }

    def get(self, request, pk):
        order = get_object_or_404(Order, id=pk)
        form = OrderForm(instance=order)
        return render(request, self.template_name, self.get_context(form, order))

    def post(self, request, pk):
        order = get_object_or_404(Order, id=pk)
        form = OrderForm(request.POST, instance=order)

        if form.is_valid():
            saved = form.save()
            messages.success(request, f"Buyurtma yangilandi: {saved.customer.name}.")
            return redirect("dashboard")

        flash_errors(request, form)
        return render(request, self.template_name, self.get_context(form, order))


class OrderDeleteView(LoginRequiredMixin, View):
    """POST only: a link that deletes on GET can be triggered by any page the signed-in person visits."""

    def post(self, request, pk):
        with transaction.atomic():
            order = get_object_or_404(Order, id=pk)
            change_customer_debt(order.customer_id, -order.remaining_debt)   # no-op when the customer is gone
            order.delete()
        messages.success(request, "Buyurtma o'chirildi.")
        return redirect("dashboard")


class CustomerView(LoginRequiredMixin, View):
    template_name = "customer.html"

    def get(self, request):
        customers = CustomerFilter(
            request.GET, Customer.objects.order_by("-total_debt")
        ).qs
        all_customers = Customer.objects.order_by("-total_debt").values(
            "id", "name", "phone", "total_debt"
        )
        total_debt = customers.aggregate(total=models.Sum("total_debt"))["total"] or 0

        context = {
            "customers": customers,
            "all_customers": all_customers,
            "today": date.today().strftime("%Y-%m-%d"),
            "total_debt": total_debt,
            "page": "customer",
        }
        return render(request, self.template_name, context=context)

    def post(self, request):
        if request.POST.get("_method") == "PUT":
            return self.put(request)

        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f"Mijoz qo'shildi: {customer.name}.")
        else:
            flash_errors(request, form)
        return redirect("customer")

    def put(self, request):
        customer_id = request.POST.get("id")
        customer = get_object_or_404(Customer, id=customer_id)
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save(update=True)
            messages.success(request, f"Mijoz ma'lumotlari yangilandi: {customer.name}.")
        else:
            flash_errors(request, form)
        return redirect("customer")


class CustomerDeleteView(LoginRequiredMixin, View):
    def delete(self, request, pk):
        customer = get_object_or_404(Customer, id=pk)
        # Deleting a customer wipes their payment history and leaves their orders without an owner,
        # and the money they still owe disappears from the totals. Only a customer with no trace can go.
        if customer.orders.exists() or customer.payment_histories.exists() or customer.total_debt:
            return JsonResponse(
                {"error": "Bu mijozda buyurtma, to'lov yoki qarz bor, shuning uchun o'chirib bo'lmaydi."},
                status=409,
            )
        name = customer.name
        customer.delete()
        messages.success(request, f"Mijoz o'chirildi: {name}.")
        return HttpResponse(status=204)


class DebtView(LoginRequiredMixin, View):
    template_name = "debt.html"

    def get(self, request):
        # Get year from query parameter, default to current year
        selected_year = request.GET.get("year", str(date.today().year))

        try:
            selected_year = int(selected_year)
        except (ValueError, TypeError):
            selected_year = date.today().year

        customers = Customer.objects.order_by("-total_debt")

        # Get date filters, default to today
        date_from = request.GET.get("date_from", date.today().strftime("%Y-%m-%d"))
        date_to = request.GET.get("date_to", date.today().strftime("%Y-%m-%d"))

        query_params = request.GET.copy()
        query_params["date_from"] = date_from
        query_params["date_to"] = date_to

        # Filter payments by year
        payments = PaymentFilter(
            query_params,
            PaymentHistory.objects.filter(paid_at__year=selected_year).order_by(
                "-paid_at"
            ),
        ).qs

        context = {
            "customers": customers,
            "payments": payments,
            "total_amount": sum(payment.amount for payment in payments),
            "today": date.today().strftime("%Y-%m-%d"),
            "date_from": date_from,
            "date_to": date_to,
            "payment_type_choices": PaymentHistory.PaymentTypeChoices.choices,
            "selected_year": selected_year,
            "years": year_choices(
                selected_year,
                PaymentHistory.objects.order_by("paid_at").values_list("paid_at__year", flat=True).first(),
            ),
            "page": "debt",
        }
        return render(request, self.template_name, context=context)

    def post(self, request):
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save()
            debt = Customer.objects.get(pk=payment.customer_id).total_debt
            if payment.amount < 0:
                what = f"Mijozga berilgan pul saqlandi: {payment.customer.name}, {money(-payment.amount)} so'm."
            else:
                what = f"To'lov saqlandi: {payment.customer.name}, {money(payment.amount)} so'm."
            messages.success(request, f"{what} Mijozning joriy qarzi: {money(debt)} so'm.")
        else:
            flash_errors(request, form)
        return redirect("debts")


class PaymentEditView(LoginRequiredMixin, View):
    template_name = "payment_edit.html"

    def get_context(self, form, payment):
        return {
            "form": form,
            "payment": payment,
            "payment_type_choices": PaymentHistory.PaymentTypeChoices.choices,
            "page": "debt",
        }

    def get(self, request, pk):
        payment = get_object_or_404(PaymentHistory, id=pk)
        form = PaymentEditForm(instance=payment)
        return render(request, self.template_name, self.get_context(form, payment))

    def post(self, request, pk):
        payment = get_object_or_404(PaymentHistory, id=pk)
        form = PaymentEditForm(request.POST, instance=payment)

        if form.is_valid():
            saved = form.save()
            messages.success(request, f"To'lov yangilandi: {saved.customer.name}.")
            return redirect("debts")

        flash_errors(request, form)
        return render(request, self.template_name, self.get_context(form, payment))


class PaymentDeleteView(LoginRequiredMixin, View):
    """POST only (see OrderDeleteView)."""

    def post(self, request, pk):
        with transaction.atomic():
            payment = get_object_or_404(PaymentHistory, id=pk)
            change_customer_debt(payment.customer_id, payment.amount)
            payment.delete()
        messages.success(request, "To'lov o'chirildi.")
        return redirect("debts")


class CementTypeView(LoginRequiredMixin, View):
    template_name = "cement_type.html"

    def parse_month(self, month_str):
        try:
            year, month_num = month_str.split("-")
            return int(year), int(month_num)
        except ValueError:
            today = date.today()
            return today.year, today.month

    def get_month_annotation(self, year, month):
        return models.Sum(
            models.Case(
                models.When(
                    orders__order_date__year=year,
                    orders__order_date__month=month,
                    then="orders__quantity",
                ),
                default=0,
            )
        )

    def get(self, request):
        current_month = date.today().strftime("%Y-%m")
        selected_month = request.GET.get("month") or current_month

        year, month = self.parse_month(selected_month)

        cement_types = CementType.objects.annotate(
            total_quantity=self.get_month_annotation(year, month)
        )

        context = {
            "cement_types": cement_types,
            "colors": CementType.COLOR_CHOICES,
            "total_quantity": sum(
                cement_type.total_quantity or 0 for cement_type in cement_types
            ),
            "page": "cement_type",
            "selected_month": selected_month,
        }
        return render(request, self.template_name, context=context)

    def post(self, request):
        form = CementTypeForm(request.POST)
        if form.is_valid():
            cement = form.save()
            messages.success(request, f"Sement turi qo'shildi: {cement.name}.")
        else:
            flash_errors(request, form)
        return redirect("cement_type")


class CementTypeDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        CementType.objects.filter(pk=pk).delete()
        messages.success(request, "Sement turi o'chirildi.")
        return redirect("cement_type")


class StatisticsView(LoginRequiredMixin, View):
    template_name = "stats.html"

    def get(self, request):
        today = date.today()
        try:
            selected_year = int(request.GET.get("year", today.year))
        except (ValueError, TypeError):
            selected_year = today.year

        first_year = Order.objects.order_by("order_date").values_list("order_date__year", flat=True).first()
        years = year_choices(selected_year, first_year)

        orders = Order.objects.filter(order_date__year=selected_year)

        most_cement_types = CementType.objects.annotate(
            total_quantity=models.Sum(
                "orders__quantity",
                filter=models.Q(orders__order_date__year=selected_year),
            )
        ).order_by("-total_quantity")[:3]

        context = {
            "total_orders": orders.count(),
            "total_debt": Customer.objects.aggregate(total=models.Sum("total_debt"))["total"] or 0,
            "total_quantity": orders.aggregate(total=models.Sum("quantity"))["total"] or 0,
            "most_cement_types": most_cement_types,
            "selected_year": selected_year,
            "years": years,
            "page": "stats",
        }

        return render(request, self.template_name, context=context)
