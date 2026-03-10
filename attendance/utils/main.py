import requests
import pandas as pd
import gspread
import time
import hashlib
import numpy as np
import logging
from io import StringIO
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "/home/Attendance/public_html/django_attendance_project/automation-scripts.json"

credentials = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
gc = gspread.authorize(credentials)
last_hashes = {}

BRANDS = ["Acer", "Apple", "Asus", "Dell", "HP", "Lenovo"]

def get_csv_hash(csv_content):
    return hashlib.md5(csv_content.encode('utf-8')).hexdigest()

def get_brand_column(df):
    for col in df.columns:
        normalized = col.lower().replace(" ", "_")
        if normalized in ["brand", "brand_name"]:
            return col
    return None

def update_brand_sheets(df, spreadsheet_id, brand_column):
    sh = gc.open_by_key(spreadsheet_id)

    for brand in BRANDS:
        brand_df = df[df[brand_column].str.lower() == brand.lower()]

        if brand_df.empty:
            continue

        try:
            try:
                ws = sh.worksheet(brand)
            except gspread.exceptions.WorksheetNotFound:
                ws = sh.add_worksheet(title=brand, rows=2000, cols=30)

            ws.clear()
            ws.update([brand_df.columns.values.tolist()] + brand_df.values.tolist())
            logging.info(f"✔ Updated brand sheet: {brand}")
        except Exception as e:
            logging.error(f"❌ Error updating brand sheet {brand}: {e}")

def update_google_sheet(spreadsheet_id, worksheet_name, urls, last_csv_hash, max_retries=6):
    attempt = 0
    sheet = None

    while attempt < max_retries:
        try:
            sh = gc.open_by_key(spreadsheet_id)
            try:
                sheet = sh.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                sheet = sh.add_worksheet(title=worksheet_name, rows=2000, cols=30)
            break
        except gspread.exceptions.APIError as e:
            attempt += 1
            time.sleep(2 ** attempt)
    else:
        logging.error(f"API Error: Could not access {worksheet_name}")
        return last_csv_hash

    combined_df = pd.DataFrame()
    new_hash = ""

    for url in urls:
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            csv_content = response.text
            new_hash += get_csv_hash(csv_content)
            df = pd.read_csv(StringIO(csv_content))
            combined_df = pd.concat([combined_df, df], ignore_index=True)

        except Exception as e:
            logging.error(f"CSV Fetch Error: {e}")

    if combined_df.empty:
        logging.warning("⚠ Empty DataFrame — skipping!")
        return last_csv_hash

    if new_hash == last_csv_hash:
        logging.info(f"⏩ No changes in: {worksheet_name}")
        return last_csv_hash

    combined_df.replace([np.nan, np.inf, -np.inf], "", inplace=True)

    try:
        sheet.clear()
        sheet.update([combined_df.columns.values.tolist()] + combined_df.values.tolist())
        logging.info(f"✔ Main sheet updated: {worksheet_name}")

        brand_column = get_brand_column(combined_df)
        if brand_column:
            update_brand_sheets(combined_df, spreadsheet_id, brand_column)
        else:
            logging.warning("⚠ Brand column not found!")

        return new_hash

    except Exception as e:
        logging.error(f"Update Error: {e}")
        return last_csv_hash

def main():
    sheet_mapping = {
        "klickit_offsite": (
            "1IK3Z_ggdm87sd95KFwlW15n_YqkENfhMthNSV2NrO8I",
            "klickit_offsite",
            ["https://klickit.co.in/export_offsite_reports.php"]
        ),
        "klickit_onsite": (
            "1gEuoVQW-nXLlYCRqO8pIy_5SYdg7V8PyXoShixVRMYs",
            "klickit_onsite",
            ["https://klickit.co.in/export_customers.php"]
        ),
    }

    for key in sheet_mapping.keys():
        last_hashes.setdefault(key, "")

    while True:
        for key, (spreadsheet_id, worksheet_name, urls) in sheet_mapping.items():
            last_hashes[key] = update_google_sheet(
                spreadsheet_id, worksheet_name, urls, last_hashes[key]
            )

        logging.info("⏱ Waiting 5 sec for next update...\n")
        time.sleep(5)

if __name__ == "__main__":
    main()
