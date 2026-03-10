from django.urls import path
from . import views

urlpatterns = [
    path('', views.mark_attendance, name='home'),   
    path('employee/add/', views.employee_create, name='employee_add'),
    path('mark/', views.mark_attendance, name='mark_attendance'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('export_excel/', views.export_excel, name='export_excel'),
    path('export_excel_from_google_sheets/', views.export_excel_from_google_sheets, name='export_excel_from_google_sheets'),
]
