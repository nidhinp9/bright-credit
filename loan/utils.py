import csv
from decimal import Decimal, getcontext
from django.conf import settings
import os
from loan.models import User, Transaction
from datetime import datetime

getcontext().prec = 10

def calculate_credit_score_from_csv(aadhar_id):
    csv_path = os.path.join(settings.BASE_DIR, 'user_transaction.csv')

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}")

    total_income = Decimal('0.0')
    total_loans = Decimal('0.0')

    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        found = False
        for row in reader:
            if row['aadhar_id'] == aadhar_id:
                found = True
                txn_type = row.get('transaction_type', '').strip().upper()
                amount = Decimal(row.get('amount', '0'))
                txn_date = datetime.strptime(row.get('date', ''), '%Y-%m-%d').date()

                if txn_type == 'CREDIT':
                    total_income += amount
                elif txn_type == 'DEBIT':
                    total_loans += amount

                # Save transaction to DB
                Transaction.objects.create(
                    user=User.objects.get(aadhar_id=aadhar_id),
                    date=txn_date,
                    amount=amount,
                    transaction_type=txn_type
                )

        if not found:
            raise ValueError("No matching transaction for this Aadhar ID")

    balance = total_income - total_loans

    if balance < Decimal('10000'):
        return 300
    else:
        effective_balance = min(balance, Decimal('1000000')) - Decimal('10000')
        increments = effective_balance // Decimal('15000')
        return min(300 + int(increments) * 10, 900)

def aadhar_exists_in_csv(aadhar_id):
    csv_path = os.path.join(settings.BASE_DIR, 'user_transaction.csv')
    if not os.path.exists(csv_path):
        return False

    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row.get('aadhar_id') == aadhar_id:
                return True
    return False
