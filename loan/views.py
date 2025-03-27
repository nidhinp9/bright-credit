from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Transaction, User, LoanApplication, DuePayment
from django.db import transaction as db_transaction
from .serializers import TransactionSerializer, UserSerializer
from .utils import calculate_credit_score_from_csv
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
import uuid
import csv
import os
from django.conf import settings
from uuid import UUID, uuid4
import traceback
from datetime import datetime, timedelta


class RegisterUserView(APIView):
    def post(self, request):
        aadhar_id = request.data.get('aadhar_id')

        # ✅ Validate Aadhar ID length
        if not aadhar_id or not aadhar_id.isdigit() or len(aadhar_id) != 12:
            return Response({
                'error': 'Invalid Aadhar ID. It must be a 12-digit number.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Check if Aadhar ID has transactions in CSV
        csv_path = os.path.join(settings.BASE_DIR, 'user_transaction.csv')
        found = False
        try:
            with open(csv_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get('aadhar_id') == aadhar_id:
                        found = True
                        break
        except Exception as e:
            return Response({
                'error': f'Error reading transaction file: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not found:
            return Response({
                'error': 'No transactions found for the given Aadhar ID. User cannot be registered.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Generate unique UUID and merge with request data
        user_uuid = str(uuid.uuid4())
        data = request.data.copy()
        data['unique_user_id'] = user_uuid

        # ✅ Validate and save user
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()

            # ✅ Calculate credit score
            try:
                score = calculate_credit_score_from_csv(user.aadhar_id)
                user.credit_score = score
                user.save()
            except Exception:
                user.delete()
                return Response({
                    'error': 'User registration failed. Could not calculate credit score.'
                }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'unique_user_id': user.unique_user_id
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class RecordTransactionView(APIView):
    def post(self, request):
        serializer = TransactionSerializer(data=request.data)
        if serializer.is_valid():
            transaction = serializer.save()

            user = transaction.user
            transactions = Transaction.objects.filter(user=user)

            total_credits = sum(t.amount for t in transactions if t.transaction_type == 'CREDIT')
            total_debits = sum(t.amount for t in transactions if t.transaction_type == 'DEBIT')

            if user.annual_income > 0:
                user.credit_score = ((total_credits - total_debits) / user.annual_income) * 100
                user.save()

            return Response({
                'message': 'Transaction recorded and credit score updated.',
                'credit_score': user.credit_score
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreditScoreView(APIView):
    def get(self, request):
        unique_user_id = request.query_params.get('unique_user_id')
        if not unique_user_id:
            return Response({'error': 'unique_user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(unique_user_id=unique_user_id)
            return Response({
                'unique_user_id': user.unique_user_id,
                'credit_score': user.credit_score
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class ApplyLoanView(APIView):
    def post(self, request):
        from datetime import timedelta

        data = request.data
        unique_user_id = data.get("unique_user_id")
        loan_type = data.get("loan_type")
        loan_amount = data.get("loan_amount")
        interest_rate = data.get("interest_rate")
        term_period = data.get("term_period")
        disbursement_date = data.get("disbursement_date")

        if not all([unique_user_id, loan_type, loan_amount, interest_rate, term_period, disbursement_date]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uuid_obj = UUID(unique_user_id, version=4)
            user = User.objects.get(unique_user_id=uuid_obj)
        except (ValueError, User.DoesNotExist):
            return Response({"error": "Invalid or non-existent UUID."}, status=status.HTTP_404_NOT_FOUND)

        if user.credit_score is None or user.credit_score < 450:
            return Response({
                "error": f"User not eligible. Credit score: {user.credit_score or 'Not available'}"
            }, status=status.HTTP_400_BAD_REQUEST)

        if user.annual_income < Decimal('150000'):
            return Response({"error": "Annual income below minimum threshold."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            disbursement_date = datetime.strptime(disbursement_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        loan_amount = Decimal(loan_amount)
        interest_rate = Decimal(interest_rate)
        term_period = int(term_period)
        monthly_income = user.annual_income / 12

        if loan_amount > 5000:
            return Response({"error": "Loan amount exceeds ₹5000 limit."}, status=status.HTTP_400_BAD_REQUEST)
        if interest_rate < 12:
            return Response({"error": "Interest rate must be ≥ 12%."}, status=status.HTTP_400_BAD_REQUEST)

        # 💡 Flat interest logic
        annual_interest = loan_amount * interest_rate / Decimal('100')
        total_interest = (annual_interest / Decimal('12')) * Decimal(term_period)
        total_payable = loan_amount + total_interest

        base_emi = (total_payable / term_period).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if base_emi > monthly_income * Decimal('0.2'):
            return Response({"error": "EMI exceeds 20% of monthly income."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Create Loan
        loan = LoanApplication.objects.create(
            user=user,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            tenure_months=term_period,
            monthly_emi=base_emi,
            approved=True
        )

        due_dates = []
        try:
            total_scheduled = Decimal('0.00')

            for i in range(term_period):
                due_date = disbursement_date + timedelta(days=30 * (i + 1))

                if i == term_period - 1:
                    last_emi = (total_payable - total_scheduled).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    emi_amount = last_emi
                else:
                    emi_amount = base_emi

                DuePayment.objects.create(
                    loan=loan,
                    due_date=due_date,
                    amount_due=emi_amount
                )

                due_dates.append({
                    "date": due_date.strftime("%Y-%m-%d"),
                    "amount_due": str(emi_amount)
                })

                total_scheduled += emi_amount

        except Exception as e:
            loan.delete()
            return Response({
                "error": "Failed to generate EMI schedule.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "loan_id": loan.id,
            "due_dates": due_dates
        }, status=status.HTTP_200_OK)


class MakePaymentView(APIView):
    def post(self, request):
        data = request.data
        loan_id = data.get("loan_id")
        amount = data.get("amount")
        payment_date = data.get("payment_date")  # Optional; defaults to today

        if not loan_id or not amount:
            return Response({"error": "Both loan_id and amount are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(amount)
        except:
            return Response({"error": "Invalid amount format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            loan = LoanApplication.objects.get(id=loan_id)
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found."}, status=status.HTTP_404_NOT_FOUND)

        # Resolve date
        try:
            payment_date_obj = (
                datetime.strptime(payment_date, "%Y-%m-%d").date()
                if payment_date else timezone.now().date()
            )
        except ValueError:
            return Response({"error": "Invalid payment_date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        emis = DuePayment.objects.filter(loan=loan).order_by("due_date")

        with db_transaction.atomic():
            emi = emis.filter(due_date=payment_date_obj).first()
            if not emi:
                # Get next unpaid EMI info for clarity
                next_emi = emis.filter(paid=False).order_by("due_date").first()
                return Response({
                    "error": f"No EMI found with due date {payment_date_obj}.",
                    "next_due": {
                        "date": next_emi.due_date.strftime("%Y-%m-%d"),
                        "amount_due": str(next_emi.amount_due)
                    } if next_emi else "All EMIs are paid."
                }, status=status.HTTP_400_BAD_REQUEST)

            if emi.paid:
                next_unpaid = emis.filter(paid=False, due_date__gt=emi.due_date).order_by("due_date").first()
                return Response({
                    "error": f"Payment already made on {emi.due_date}.",
                    "next_due": {
                        "date": next_unpaid.due_date.strftime("%Y-%m-%d"),
                        "amount_due": str(next_unpaid.amount_due)
                    } if next_unpaid else "Loan is fully paid."
                }, status=status.HTTP_400_BAD_REQUEST)

            # ✅ Enhanced: Show previous unpaid EMI if any
            unpaid_prev = emis.filter(due_date__lt=emi.due_date, paid=False).order_by("-due_date").first()
            if unpaid_prev:
                return Response({
                    "error": f"Previous EMI before {emi.due_date} is unpaid. Please clear it first.",
                    "unpaid_due_date": unpaid_prev.due_date.strftime("%Y-%m-%d"),
                    "unpaid_amount": str(unpaid_prev.amount_due)
                }, status=status.HTTP_400_BAD_REQUEST)

            # If amount is not exact, accept and recalculate remaining EMIs
            if amount != emi.amount_due:
                remaining_emis = emis.filter(paid=False, due_date__gt=emi.due_date).order_by("due_date")
                remaining_due = sum(e.amount_due for e in remaining_emis)

                paid_till_now = emi.amount_due
                actual_remaining = (remaining_due + paid_till_now) - amount

                emi.amount_due = amount
                emi.paid = True
                emi.payment_date = payment_date_obj
                emi.save()

                if remaining_emis.exists():
                    new_emi = (actual_remaining / remaining_emis.count()).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    for i, e in enumerate(remaining_emis):
                        if i == remaining_emis.count() - 1:
                            # Last EMI takes all remaining amount
                            e.amount_due = actual_remaining
                        else:
                            e.amount_due = new_emi
                            actual_remaining -= new_emi
                        e.amount_due = e.amount_due.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        e.save()

                transaction_id = str(uuid4())
                return Response({
                    "message": f"Partial payment of ₹{amount} accepted for EMI on {emi.due_date}. EMIs recalculated.",
                    "transaction_id": transaction_id
                }, status=status.HTTP_200_OK)

            # ✅ Exact payment
            emi.paid = True
            emi.payment_date = payment_date_obj
            emi.save()

            transaction_id = str(uuid4())
            return Response({
                "message": f"EMI of ₹{amount} paid successfully for due date {emi.due_date}.",
                "transaction_id": transaction_id
            }, status=status.HTTP_200_OK)
        
class GetStatementView(APIView):
    def get(self, request):
        print("🔍 GetStatementView triggered with query params:", request.query_params)

        loan_id = request.query_params.get("loan_id")
        if not loan_id:
            print("❌ loan_id missing in request")
            return Response({"error": "loan_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            loan = LoanApplication.objects.get(id=loan_id)
            print(f"✅ Loan found: ID {loan.id}, User: {loan.user.name}")
        except LoanApplication.DoesNotExist:
            print(f"❌ Loan with ID {loan_id} does not exist.")
            return Response({"error": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)

        emis = DuePayment.objects.filter(loan=loan).order_by("due_date")
        print(f"📊 Total EMIs found: {emis.count()}")

        if not emis.exists():
            print("❌ No EMIs linked to this loan.")
            return Response({"error": "No EMIs found for this loan."}, status=status.HTTP_400_BAD_REQUEST)

        if emis.filter(paid=False).count() == 0:
            print("✅ All EMIs are paid. Loan is closed.")
            return Response({"error": "Loan is closed. All EMIs are paid."}, status=status.HTTP_400_BAD_REQUEST)

        monthly_interest_rate = loan.interest_rate / Decimal('12') / Decimal('100')
        past_transactions = []
        upcoming_transactions = []

        for emi in emis:
            if emi.paid:
                # Assume payment on 1st of the EMI month
                date_str = emi.due_date.replace(day=1).strftime("%Y-%m-%d")
                amount = emi.amount_due
                interest = (amount * monthly_interest_rate).quantize(Decimal('0.01'))
                principal = amount - interest

                print(f"📌 Paid EMI | Date: {date_str}, Principal: {principal}, Interest: {interest}, Total: {amount}")
                past_transactions.append({
                    "date": date_str,
                    "principal": str(principal),
                    "interest": str(interest),
                    "amount_paid": str(amount)
                })
            else:
                print(f"📅 Upcoming EMI | Date: {emi.due_date}, Amount: {emi.amount_due}")
                upcoming_transactions.append({
                    "date": emi.due_date.strftime("%Y-%m-%d"),
                    "amount_due": str(emi.amount_due)
                })

        return Response({
            "past_transactions": past_transactions,
            "upcoming_transactions": upcoming_transactions
        }, status=status.HTTP_200_OK)
