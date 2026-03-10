from django.contrib import admin
from .models import Employee, Attendance, Holiday

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'name', 'branch')
    search_fields = ('employee_id', 'name', 'branch')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'intime', 'outtime')
    list_filter = ('date', 'employee__branch')

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name')
    list_filter = ('date',)
    search_fields = ('name',)
    ordering = ('date',)
