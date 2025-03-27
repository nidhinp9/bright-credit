#!/bin/bash

echo "🔄 Running migrations..."
./brightenv/bin/python manage.py migrate

echo "🚀 Starting Django server..."
./brightenv/bin/python manage.py runserver 8001 &

echo "⚙️ Starting Celery Worker..."
./brightenv/bin/celery -A bright_credit worker --loglevel=info &

echo "⏰ Starting Celery Beat Scheduler..."
./brightenv/bin/celery -A bright_credit beat --loglevel=info &

echo "✅ All services running. Visit: http://127.0.0.1:8001"
