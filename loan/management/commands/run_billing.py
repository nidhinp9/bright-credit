from django.core.management.base import BaseCommand
from loan.cron import run_billing_cycle

class Command(BaseCommand):
    help = 'Run the 30-day billing cycle'

    def handle(self, *args, **kwargs):
        run_billing_cycle()
        self.stdout.write(self.style.SUCCESS('Billing cycle executed successfully.'))
