# Klickit Attendance System

Modern Django-based employee attendance tracking system designed for organizations to manage daily attendance with automated tracking, Google Sheets integration, and intelligent attendance rules.

The system supports camera-based check-ins, automated attendance calculations, and real-time Google Sheets synchronization for transparent employee tracking.

---



## Key Features

- Face / camera-based check-in & check-out (base64 image upload)
- One **Check-In** and **Check-Out** per day validation
- Automatic **Google Sheets synchronization** per employee
- Automatic **absent marking for missing days**
- **Sunday holiday detection** based on adjacent working days
- **Late / Half-Day remarks** based on check-in time
- Dashboard with **name, date, and month filters**
- **Excel export** of attendance records
- **Background thread processing** for faster UI response
- Full **Admin panel support** for attendance management

---

## Attendance Rules

| Rule | Logic |
|-----|------|
| Late Mark | Check-in after **10:15 AM** |
| Half Day | Check-in after **10:30 AM** |
| Check-Out | Allowed after minimum **5 minutes gap** |
| Sunday | Auto-marked based on adjacent working days |
| Missing Days | Automatically marked as **Absent** |

---

## System Features Overview

| Feature | Status | Description |
|-------|--------|-------------|
| Check-in / Check-out with photo | ✓ | Base64 image captured and stored |
| One IN + one OUT per day | ✓ | Prevents duplicate entries |
| Google Sheets sync | ✓ | Individual sheet per employee |
| Auto absent marking | ✓ | Detects gaps between attendance |
| Sunday holiday logic | ✓ | Based on attendance pattern |
| Late / Half-day remark | ✓ | Automatic calculation |
| Dashboard filters | ✓ | Search by name/date/month |
| Excel export | ✓ | From DB or Google Sheets |
| Admin panel | ✓ | Manual edits also sync to Sheets |
| Background processing | ✓ | Fast UI using threads |

---

## Tech Stack

Backend  
Python  
Django  

Database  
SQLite (Development)  
PostgreSQL (Recommended for Production)

Frontend  
Django Templates  
HTML  
CSS  
JavaScript  

External Integrations  
Google Sheets API  
gspread  
google-auth  

Libraries  
openpyxl  
pandas  

Storage  
Local media storage for captured images

---

## Project Structure


attendance_system/
│
├── attendance/
│ ├── models.py
│ ├── views.py
│ ├── signals.py
│ ├── utils.py
│
├── templates/
├── static/
├── media/
├── manage.py
└── requirements.txt


---

## Installation

Clone repository


git clone https://github.com/YOUR_USERNAME/klickit-attendance-system.git


Navigate to project


cd klickit-attendance-system


Install dependencies


pip install -r requirements.txt


Run migrations


python manage.py migrate


Run development server


python manage.py runserver


---

## Future Improvements

- Secure authentication with JWT
- Production deployment with Docker
- Logging & monitoring system
- Improved error handling
- Cloud storage for images

---

## Author

Shivam Yadav  
Full Stack Developer  

LinkedIn  
https://www.linkedin.com/in/shivam-yadav-23b4a1317/

Portfolio  
https://my-portfolio-eta-eight-21.vercel.app/
