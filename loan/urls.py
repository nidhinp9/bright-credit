from django.urls import path
from .views import GetStatementView, MakePaymentView, RegisterUserView, RecordTransactionView, CreditScoreView, ApplyLoanView

urlpatterns = [
    path('register-user/', RegisterUserView.as_view(), name='register-user'),
    path('record-transaction/', RecordTransactionView.as_view(), name='record-transaction'),
    path('credit-score/', CreditScoreView.as_view(), name='credit-score'),
    path('apply-loan/', ApplyLoanView.as_view(), name='apply-loan'), 
    path('make-payment/', MakePaymentView.as_view(), name='make-payment'),
    path('get-statement/', GetStatementView.as_view(), name='get-statement'),

]
