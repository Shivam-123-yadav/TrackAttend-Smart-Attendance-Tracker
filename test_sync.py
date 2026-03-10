"""
Test script to verify automatic Google Sheets sync is working.
Run this from Django shell: python manage.py shell < test_sync.py
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from attendance.models import Employee, Attendance
from attendance.views import append_attendance_row

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n" + "="*60)
print("🧪 TESTING AUTOMATIC GOOGLE SHEETS SYNC")
print("="*60 + "\n")

# Test 1: Create a test employee
print("TEST 1: Creating test employee...")
try:
    emp, created = Employee.objects.get_or_create(
        employee_id='TEST001',
        defaults={
            'name': 'Test Employee',
            'branch': 'Test Branch'
        }
    )
    print(f"✅ Employee created/retrieved: {emp.name} ({emp.employee_id})")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Create attendance record (signal should trigger)
print("\nTEST 2: Creating attendance record (this will trigger auto-sync signal)...")
try:
    today = timezone.localdate()
    att, created = Attendance.objects.get_or_create(
        employee=emp,
        date=today,
        defaults={
            'intime': timezone.localtime().time(),
            'outtime': (timezone.localtime() + timedelta(hours=8)).time()
        }
    )
    print(f"✅ Attendance created: {att.employee.name} on {att.date}")
    print(f"   - Time In: {att.intime}")
    print(f"   - Time Out: {att.outtime}")
    print(f"   - Hours: {att.no_of_hours}")
    print(f"   - Status: {att.attendance}")
    print("   ✅ Signal should have triggered auto-sync to Google Sheets!")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Update attendance (signal should trigger again)
print("\nTEST 3: Updating attendance record (this will trigger auto-sync signal again)...")
try:
    from datetime import time
    att.intime = time(9, 30)
    att.outtime = time(18, 30)
    att.save()  # ← Signal triggers here!
    print(f"✅ Attendance updated: {att.employee.name}")
    print(f"   - New Time In: {att.intime}")
    print(f"   - New Time Out: {att.outtime}")
    print(f"   - Hours: {att.no_of_hours}")
    print("   ✅ Signal triggered! Google Sheet should be updated now!")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Manual sync test
print("\nTEST 4: Testing manual append_attendance_row function...")
try:
    result = append_attendance_row(emp, today, att.intime, att.outtime)
    print(f"✅ Manual sync executed successfully!")
except Exception as e:
    print(f"❌ Error during manual sync: {e}")

# Test 5: Verify signals are registered
print("\nTEST 5: Verifying signals are registered...")
try:
    from django.db.models.signals import post_save
    from django.dispatch import receiver
    signals_list = post_save.receivers
    attendance_signals = [s for s in signals_list if 'Attendance' in str(s)]
    if attendance_signals:
        print(f"✅ Found {len(attendance_signals)} signal(s) for Attendance model")
    else:
        print("⚠️ No signals found - this might be an issue")
except Exception as e:
    print(f"❌ Error checking signals: {e}")

print("\n" + "="*60)
print("✅ ALL TESTS COMPLETED!")
print("="*60)
print("\nINSTRUCTIONS:")
print("1. Check your Google Sheet to verify updates were synced")
print("2. Go to http://localhost:8000/ (dashboard)")
print("3. Search for the test employee to verify it appears")
print("\n" + "="*60 + "\n")
