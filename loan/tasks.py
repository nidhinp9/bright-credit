from celery import shared_task
from loan.models import User, Transaction, LoanApplication, BillingDetail, DuePayment
import csv
from decimal import Decimal, getcontext, ROUND_HALF_UP
from django.conf import settings
from django.utils import timezone
from datetime import date, datetime, timedelta
from django.db import transaction
import os
import logging

# Set high precision for Decimal calculations
getcontext().prec = 10
logger = logging.getLogger(__name__)


@shared_task
def calculate_credit_score(aadhar_id):
    try:
        user = User.objects.get(aadhar_id=aadhar_id)
    except User.DoesNotExist:
        logger.warning(f"[!] User with Aadhar ID {aadhar_id} not found.")
        return

    csv_path = os.path.join(settings.BASE_DIR, 'user_transaction.csv')

    if not os.path.exists(csv_path):
        logger.error(f"[!] CSV file not found at {csv_path}")
        return

    total_income = Decimal('0.0')
    total_loans = Decimal('0.0')

    try:
        with open(csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    if row['aadhar_id'] == aadhar_id:
                        txn_type = row.get('transaction_type', '').strip().upper()
                        amount = Decimal(row.get('amount', '0'))
                        txn_date = datetime.strptime(row.get('date', ''), '%Y-%m-%d').date()

                        if txn_type == 'CREDIT':
                            total_income += amount
                        elif txn_type == 'DEBIT':
                            total_loans += amount

                        Transaction.objects.create(
                            user=user,
                            date=txn_date,
                            amount=amount,
                            transaction_type=txn_type
                        )
                except Exception as e:
                    logger.warning(f"[!] Skipping row due to error: {e}")
    except Exception as e:
        logger.error(f"[!] Failed to read CSV: {e}")
        return

    balance = total_income - total_loans

    if balance < Decimal('10000'):
        credit_score = 300
    else:
        effective_balance = min(balance, Decimal('1000000')) - Decimal('10000')
        increments = effective_balance // Decimal('15000')
        credit_score = min(300 + int(increments) * 10, 900)

    user.credit_score = credit_score
    user.save()

    logger.info(f"[✔] Final credit score for {aadhar_id}: {credit_score}")
    return True


@shared_task
def run_billing():
    today = date.today()
    loans = LoanApplication.objects.filter(approved=True)
    billed_loans = 0

    for loan in loans:
        last_billing = BillingDetail.objects.filter(loan=loan).order_by('-billing_date').first()
        if last_billing and (today - last_billing.billing_date).days < 30:
            continue

        principal_due = loan.loan_amount
        apr = loan.interest_rate / Decimal(100)
        daily_apr = apr / Decimal(365)
        interest_due = daily_apr * Decimal(30) * principal_due
        min_due = (principal_due * Decimal('0.03')) + interest_due
        min_due = min_due.quantize(Decimal('0.01'))

        billing_date = today
        due_date = today + timedelta(days=15)

        with transaction.atomic():
            BillingDetail.objects.create(
                loan=loan,
                billing_date=billing_date,
                due_date=due_date,
                min_due_amount=min_due
            )

            logger.info(f"📄 Billing Summary for Loan ID: {loan.id}")
            logger.info(f"   • User UUID: {loan.user.unique_user_id}")
            logger.info(f"   • Billing Date: {today}")
            logger.info(f"   • Due Date: {due_date}")
            logger.info(f"   • Min Due Amount: ₹{min_due}")
            logger.info(f"   • Remaining Unpaid EMIs: {loan.duepayment_set.filter(paid=False).count()}")
            logger.info(f"   • Status: ✅ New billing record created")
            logger.info("---------------------------------------------")
            billed_loans += 1

    logger.info(f"✅ Billing run completed for {billed_loans} loans on {today}")
    return f"Billing run completed for {billed_loans} loans on {today}"
