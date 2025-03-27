# 💳 Bright Credit Loan Management System

A Django + Celery-based backend service to manage users, credit scores, loan applications, payments, and statements.

---

## 🚀 Setup Instructions

### 1. CD into Directory

```bash
cd bright_credit
```

### 2. Create and Activate Virtual Environment

```bash
python3 -m venv brightenv
source brightenv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Migrate and Seed Database

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Run Server

```bash
./brightenv/bin/python manage.py runserver 8001
```

### 6. Start Redis (if not running)

```bash
brew services start redis
```

### 7. Start Celery Worker

```bash
celery -A bright_credit worker --loglevel=info
```

---

## ⚙️ Cron Job - Billing with Celery

To trigger daily billing manually:

```python
from loan.tasks import run_billing
run_billing.delay()
```

---

## 📂 Required File: `user_transaction.csv`

Place it in the root directory. Format:

```csv
aadhar_id,date,amount,transaction_type
111122223333,2025-03-01,600000,CREDIT
111122223333,2025-03-02,50000,DEBIT
```

---

## 📮 API Endpoints

### 1. **Register User**

**POST** `/api/register-user/`

#### Request:

```json
{
  "aadhar_id": "999900001111",
  "name": "Test User",
  "email": "test@example.com",
  "annual_income": "2000000"
}
```

#### Success Response:

```json
{
  "unique_user_id": "uuid-abc-123..."
}
```

---

### 2. **Get Credit Score**

**GET** `/api/credit-score/?unique_user_id=<uuid>`

#### Success Response:

```json
{
  "unique_user_id": "uuid...",
  "credit_score": 480
}
```

---

### 3. **Apply for Loan**

**POST** `/api/apply-loan/`

#### Request:

```json
{
  "unique_user_id": "uuid...",
  "loan_type": "CREDIT_CARD",
  "loan_amount": 4000,
  "interest_rate": 14,
  "term_period": 4,
  "disbursement_date": "2025-03-27"
}
```

#### Success Response:

```json
{
  "loan_id": 3,
  "due_dates": [
    { "date": "2025-04-26", "amount_due": "1560.00" },
    { "date": "2025-05-26", "amount_due": "1560.00" },
    ...
  ]
}
```

---

### 4. **Make Payment**

**POST** `/api/make-payment/`

#### Request:

```json
{
  "loan_id": 3,
  "amount": 1560,
  "payment_date": "2025-04-26"
}
```

#### Success Response:

```json
{
  "message": "EMI of ₹1560 paid successfully for due date 2025-04-26.",
  "transaction_id": "uuid..."
}
```

---

### 5. **Get Loan Statement**

**GET** `/api/get-statement/?loan_id=3`

#### Success Response:

```json
{
  "past_transactions": [
    {
      "date": "2025-04-26",
      "principal": 1000,
      "interest": 560,
      "amount_paid": 1560
    }
  ],
  "upcoming_transactions": [
    { "date": "2025-05-26", "amount_due": "1560.00" },
    ...
  ]
}
```
