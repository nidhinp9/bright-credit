from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid

class User(models.Model):
    unique_user_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    aadhar_id = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    annual_income = models.DecimalField(max_digits=10, decimal_places=2)
    credit_score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.aadhar_id}"


class TransactionType(models.TextChoices):
    CREDIT = 'CREDIT', _('Credit')
    DEBIT = 'DEBIT', _('Debit')


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('LOAN', 'Loan'),
        ('REPAYMENT', 'Repayment'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)

    def __str__(self):
        return f"{self.user.name} - {self.transaction_type} - ₹{self.amount} on {self.date}"


class LoanApplication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    loan_amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tenure_months = models.IntegerField()
    monthly_emi = models.DecimalField(max_digits=10, decimal_places=2)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Loan for {self.user.aadhar_id} - Rs.{self.loan_amount}"


class BillingDetail(models.Model):
    loan = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, related_name='billings')
    billing_date = models.DateField()
    due_date = models.DateField()
    min_due_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Billing for Loan {self.loan.id} on {self.billing_date}"


class DuePayment(models.Model):
    loan = models.ForeignKey(LoanApplication, on_delete=models.CASCADE)
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)  # ✅ Make sure this exists

    def __str__(self):
        return f"Due on {self.due_date} - {'Paid' if self.paid else 'Pending'}"
