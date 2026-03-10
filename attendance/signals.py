"""
Django signals for automatic Google Sheets sync.
Whenever an Attendance record is saved (including admin panel edits),
it automatically syncs to Google Sheets and refreshes the dashboard.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import logging
from datetime import timedelta

from .models import Attendance

# Setup logging
logger = logging.getLogger(__name__)


def create_absent_entries_for_gap(instance, created):
    """
    When an attendance record is created/updated, check if there's a gap from previous attendance.
    If gap > 1 day, automatically create ABSENT entries for the gap days.
    
    Example:
    - Last attendance: 2026-02-11 (with time-in/out)
    - Current attendance: 2026-02-15 (with time-in/out)
    - Gap: 2026-02-12, 2026-02-13, 2026-02-14 (3 absent days)
    → Auto-create absent entries for these 3 days
    
    Note: The post_save signal will automatically sync each created entry to Google Sheets,
    so we don't need to manually sync here.
    """
    if not created:
        # Only do this for new entries, not updates
        return
    
    try:
        employee = instance.employee
        current_date = instance.date
        
        # Find previous attendance record for same employee (before current date)
        previous_attendance = Attendance.objects.filter(
            employee=employee,
            date__lt=current_date
        ).order_by('-date').first()
        
        if not previous_attendance:
            # No previous record, so no gap to fill
            return
        
        previous_date = previous_attendance.date
        gap_days = (current_date - previous_date).days
        
        # Only create absent entries if gap > 1 day
        if gap_days <= 1:
            return
        
        logger.info(
            f"⏩ Gap detected for {employee.name}: "
            f"{previous_date} to {current_date} ({gap_days} days). "
            f"Creating absent entries for {gap_days - 1} day(s)..."
        )
        
        # Create absent entries for each gap day
        for i in range(1, gap_days):
            gap_date = previous_date + timedelta(days=i)
            
            # Create absent attendance record for this gap date
            # The post_save signal will automatically sync this to Google Sheets
            absent_attendance, was_created = Attendance.objects.get_or_create(
                employee=employee,
                date=gap_date,
                defaults={
                    'intime': None,
                    'outtime': None,
                    'attendance': 'A'  # Absent
                }
            )
            
            if was_created:
                logger.info(
                    f"✔ Auto-created absent entry for {employee.name} on {gap_date} "
                    f"(will be synced to Google Sheets by signal)"
                )
    
    except Exception as e:
        logger.error(
            f"❌ Error creating absent entries for gap: {e}",
            exc_info=True
        )


@receiver(post_save, sender=Attendance)
def sync_attendance_to_google_sheet(sender, instance, created, **kwargs):
    """
    Signal handler: When an Attendance record is saved (created or updated),
    automatically sync to Google Sheets and refresh the dashboard.
    
    Also handles creating absent entries for gap dates if applicable.
    
    This ensures:
    - Manual edits in admin panel → Google Sheet updated
    - Manual edits in database → Google Sheet updated
    - Gap dates auto-filled with absent entries
    - Dashboard always shows latest data from DB
    """
    try:
        # First, check if we need to create absent entries for gap days
        if created:
            create_absent_entries_for_gap(instance, created)
        
        # Import here to avoid circular imports
        from .views import append_attendance_row
        
        # Call the function with the updated attendance data
        append_attendance_row(
            employee=instance.employee,
            date_obj=instance.date,
            intime=instance.intime,
            outtime=instance.outtime
        )
        
        action = "created" if created else "updated"
        logger.info(
            f"✔ {action.capitalize()} attendance for {instance.employee.name} "
            f"on {instance.date} and synced to Google Sheets"
        )
        
    except Exception as e:
        logger.error(
            f"❌ Error syncing attendance to Google Sheets: {e}",
            exc_info=True
        )
        # Don't raise - we want the save to succeed even if sync fails
        print(f"Warning: Google Sheets sync failed - {e}")
