from datetime import date, timedelta
from django.db import transaction
from .models import User, BillingDetail, DuePayment
from decimal import Decimal
def run_billing_cycle():
    today = date.today()
    due_date = today + timedelta(days=15)

    users = User.objects.exclude(credit_score__isnull=True)

    for user in users:
        # Assume min due is 3% of annual income / 12 + ₹50 interest
        min_due = round((user.annual_income / 12) * Decimal('0.03') + Decimal('50.00'), 2)

        with transaction.atomic():
            billing = BillingDetail.objects.create(
                loan=loan,
                billing_date=today,
                due_date=due_date,
                min_due_amount=min_due
            )

            DuePayment.objects.create(
                billing=billing,
                amount_paid=Decimal('0.00'),
                is_paid=False
            )

            print(f"[✔] Billing generated for {user.aadhar_id}")
