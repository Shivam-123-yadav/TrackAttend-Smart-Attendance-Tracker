from django.db import models
from datetime import date
import datetime
from decimal import Decimal

class Holiday(models.Model):
    """Store holiday dates with names"""
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)
    
    class Meta:
        ordering = ['date']
    
    def __str__(self):
        return f"{self.name} ({self.date})"

class Employee(models.Model):
    employee_id = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    branch = models.CharField(max_length=80, blank=True)
    photo = models.ImageField(upload_to='employees/', blank=True, null=True)
    def __str__(self):
        return f"{self.name} ({self.employee_id})"
class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField(default=date.today)
    intime = models.TimeField(null=True, blank=True)
    outtime = models.TimeField(null=True, blank=True)
    in_image = models.ImageField(upload_to='attendance/in/', null=True, blank=True)
    out_image = models.ImageField(upload_to='attendance/out/', null=True, blank=True)
    # Snapshot / computed fields to mirror spreadsheet columns
    day = models.CharField(max_length=20, blank=True)
    employee_name = models.CharField(max_length=120, blank=True)
    employee_identifier = models.CharField(max_length=30, blank=True)
    branch = models.CharField(max_length=80, blank=True)
    no_of_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    attendance = models.CharField(max_length=3, blank=True)
    remark = models.CharField(max_length=64, blank=True)
    class Meta:
        unique_together = ('employee', 'date')
    def __str__(self):
        return f"{self.employee.name} - {self.date}"

    def is_holiday(self):
        """Check if the date is a holiday"""
        return Holiday.objects.filter(date=self.date).exists()

    def save(self, *args, **kwargs):
        # Populate day
        try:
            if self.date:
                self.day = self.date.strftime('%A')
        except Exception:
            self.day = ''

        # Populate snapshot fields from employee
        try:
            if self.employee_id:
                emp = self.employee
                self.employee_name = emp.name or ''
                self.employee_identifier = emp.employee_id or ''
                self.branch = emp.branch or ''
        except Exception:
            pass

        # Compute no_of_hours if both times available
        try:
            if self.intime and self.outtime and self.date:
                dt_in = datetime.datetime.combine(self.date, self.intime)
                dt_out = datetime.datetime.combine(self.date, self.outtime)
                if dt_out < dt_in:
                    dt_out += datetime.timedelta(days=1)
                hours = (dt_out - dt_in).total_seconds() / 3600.0
                # store as Decimal with 2 decimal places
                self.no_of_hours = Decimal(str(round(hours, 2)))
            else:
                self.no_of_hours = None
        except Exception:
            self.no_of_hours = None

        # Attendance status: Holiday -> 'H', Sunday -> 'H', intime -> 'P', else 'A'
        try:
            if self.date:
                # Check if it's a holiday
                if self.is_holiday():
                    self.attendance = 'H'
                else:
                    weekday_num = self.date.weekday()  # 0=Mon,6=Sun
                    if weekday_num == 6:
                        self.attendance = 'H'
                    elif self.intime:
                        self.attendance = 'P'
                    else:
                        self.attendance = 'A'
        except Exception:
            self.attendance = ''

        # Remark: Half Day (>10:30), Half Day (>10:15)
        try:
            if self.intime:
                t_1015 = datetime.time(10, 15)
                t_1030 = datetime.time(10, 30)
                if self.intime > t_1030:
                    self.remark = 'Half Day'
                elif self.intime > t_1015:
                    self.remark = 'Half Day'
                else:
                    self.remark = ''
            else:
                self.remark = ''
        except Exception:
            self.remark = ''

        super().save(*args, **kwargs)

        # If Saturday is marked Present (P), auto-mark Sunday as 'S'
        try:
            if self.date and self.intime:
                weekday_num = self.date.weekday()  # 0=Mon, 5=Sat, 6=Sun
                if weekday_num == 5:  # Saturday
                    # Get next day (Sunday)
                    sunday_date = self.date + datetime.timedelta(days=1)
                    # Create or get Sunday's attendance record
                    sunday_attendance, created = Attendance.objects.get_or_create(
                        employee=self.employee,
                        date=sunday_date
                    )
                    # Mark Sunday with 'S'
                    sunday_attendance.attendance = 'S'
                    sunday_attendance.day = sunday_date.strftime('%A')
                    sunday_attendance.employee_name = self.employee_name
                    sunday_attendance.employee_identifier = self.employee_identifier
                    sunday_attendance.branch = self.branch
                    # Save without triggering this save method again (to avoid recursion)
                    Attendance.objects.filter(pk=sunday_attendance.pk).update(
                        attendance='S',
                        day='Sunday',
                        employee_name=self.employee_name,
                        employee_identifier=self.employee_identifier,
                        branch=self.branch
                    )
        except Exception as e:
            print(f"Error auto-marking Sunday attendance: {e}")
