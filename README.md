# Klickit Attendance System

Modern Django-based employee attendance tracking system with:

- Face/camera-based check-in/check-out (base64 image upload)
- Google Sheets per-employee auto-sync (real-time + conditional formatting)
- Automatic absent marking for gap days
- Sunday/holiday logic (based on adjacent working days)
- Late / Half-day remarks (10:15 & 10:30 cutoff)
- Dashboard with filters (name, date, month)
- Excel export (from DB or directly from Google Sheets)
- Background thread processing for fast UI response

Current status: **Production-ready with polish needed** (security, logging, error handling, deployment config)

## Features

| Feature                              | Status     | Notes |
|--------------------------------------|------------|-------|
| Check-in / Check-out with photo      | ✓          | Base64 → saved in media/ |
| One IN + one OUT per day             | ✓          | 5-minute gap enforced for OUT |
| Google Sheets sync (per employee)    | ✓          | Individual worksheet + colors + formulas |
| Auto-create absent days in gaps      | ✓          | Via post_save signal |
| Sunday holiday logic                 | ✓          | Depends on Sat & Mon presence |
| Late / Half-day auto-remark          | ✓          | >10:15 = Late, >10:30 = Half Day |
| Dashboard + filters                  | ✓          | Name search + date/month |
| Excel export (per employee sheets)   | ✓          | From DB or from Google Sheets |
| Admin panel support                  | ✓          | Edits also sync to Sheets |
| Background thread for Sheets write   | ✓          | Fast frontend response |

## Tech Stack

- **Backend**     Django 4.x / 5.x
- **Database**    SQLite (dev) → PostgreSQL recommended (prod)
- **Frontend**    Django templates + simple JS (for camera)
- **External**    gspread, google-auth, openpyxl, pandas
- **Storage**     Local media/ for images

## Project Structure
