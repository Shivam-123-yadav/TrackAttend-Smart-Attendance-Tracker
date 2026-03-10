#!/usr/bin/env python
import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

from attendance.models import Holiday

# Add Ganesh Chaturthi
holiday1, created1 = Holiday.objects.get_or_create(
    date=date(2026, 3, 5),
    defaults={'name': 'Ganesh Chaturthi'}
)
print(f"Ganesh Chaturthi: {'Created' if created1 else 'Already exists'}")

# Add Ramzan ID
holiday2, created2 = Holiday.objects.get_or_create(
    date=date(2026, 3, 21),
    defaults={'name': 'Ramzan ID'}
)
print(f"Ramzan ID: {'Created' if created2 else 'Already exists'}")

# List all holidays
print("\nAll Holidays:")
for holiday in Holiday.objects.all().order_by('date'):
    print(f"  {holiday.date}: {holiday.name}")
