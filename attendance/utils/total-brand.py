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

# Rate limiting constants
MIN_API_DELAY = 5  # Minimum seconds between API calls
QUOTA_LIMIT = 60  # Read requests per minute
MIN_CYCLE_INTERVAL = 120  # Minimum seconds between full cycles (2 minutes)
last_api_call_time = 0  # Track last API call time globally

def get_csv_hash(csv_content):
    return hashlib.md5(csv_content.encode('utf-8')).hexdigest()

def enforce_api_rate_limit():
    """Enforce minimum delay between API calls to respect quota limits"""
    global last_api_call_time
    current_time = time.time()
    time_since_last_call = current_time - last_api_call_time
    
    if time_since_last_call < MIN_API_DELAY:
        sleep_time = MIN_API_DELAY - time_since_last_call
        logging.debug(f"⏳ Rate limit: sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)
    
    last_api_call_time = time.time()

def get_brand_column(df):
    """Find the brand column in the dataframe"""
    for col in df.columns:
        normalized = col.lower().replace(" ", "_")
        if normalized in ["brand", "brand_name", "brand_name_", "_brand", "brandname"]:
            return col
    return None

def update_brand_sheets(df, spreadsheet_id, brand_column):
    """Update individual brand sheets based on brand column"""
    try:
        sh = gc.open_by_key(spreadsheet_id)
    except Exception as e:
        logging.error(f"❌ Error opening spreadsheet: {e}")
        return

    for brand in BRANDS:
        brand_df = df[df[brand_column].str.lower() == brand.lower()]

        if brand_df.empty:
            logging.info(f"⏭ No data for brand: {brand}")
            continue

        ws = None
        time.sleep(1)  # Add delay before each brand sheet operation to avoid quota limits
        
        try:
            # First, try to get the existing worksheet
            ws = sh.worksheet(brand)
            logging.info(f"📝 Found existing sheet: {brand}")
        except gspread.exceptions.WorksheetNotFound:
            # Sheet doesn't exist, create it
            try:
                ws = sh.add_worksheet(title=brand, rows=2000, cols=30)
                logging.info(f"➕ Created new sheet: {brand}")
            except gspread.exceptions.APIError as e:
                if "already exists" in str(e).lower():
                    # Race condition: sheet was created between our check and creation attempt
                    # Try to get it one more time
                    try:
                        time.sleep(1)
                        ws = sh.worksheet(brand)
                        logging.info(f"📝 Retrieved sheet after race condition: {brand}")
                    except Exception as retry_error:
                        logging.error(f"❌ Could not retrieve {brand} sheet after creation conflict: {retry_error}")
                        continue
                else:
                    logging.error(f"❌ API Error creating brand sheet {brand}: {e}")
                    continue
        except Exception as e:
            logging.error(f"❌ Unexpected error accessing brand sheet {brand}: {e}")
            continue

        # Now update the sheet if we successfully got/created it
        if ws:
            try:
                ws.clear()
                ws.update([brand_df.columns.values.tolist()] + brand_df.values.tolist())
                logging.info(f"✔ Updated brand sheet: {brand} ({len(brand_df)} rows)")
                time.sleep(1)  # Increased delay to avoid rate limits
            except Exception as e:
                logging.error(f"❌ Error updating brand sheet {brand}: {e}")

def update_google_sheet(spreadsheet_id, worksheet_name, urls, last_csv_hash, max_retries=6, spreadsheet_cache=None):
    """Main function to update Google Sheets with CSV data"""
    attempt = 0
    sheet = None
    sh = None

    # Use cached spreadsheet if available
    if spreadsheet_cache and spreadsheet_id in spreadsheet_cache:
        sh = spreadsheet_cache[spreadsheet_id]
        logging.info(f"♻️ Using cached spreadsheet connection")
    
    # Open spreadsheet with retry logic if not cached
    if not sh:
        enforce_api_rate_limit()  # Enforce rate limiting before API call
        while attempt < max_retries:
            try:
                sh = gc.open_by_key(spreadsheet_id)
                if spreadsheet_cache is not None:
                    spreadsheet_cache[spreadsheet_id] = sh
                break
            except gspread.exceptions.APIError as e:
                attempt += 1
                # Handle quota exceeded errors with longer backoff
                if "429" in str(e) or "Quota exceeded" in str(e):
                    wait_time = 60 * (attempt + 1)  # 60s, 120s, 180s, etc.
                    logging.warning(f"⚠ Quota exceeded error (attempt {attempt}/{max_retries}), waiting {wait_time}s")
                else:
                    wait_time = 2 ** attempt
                    logging.warning(f"⚠ API Error opening spreadsheet (attempt {attempt}/{max_retries}), waiting {wait_time}s: {e}")
                time.sleep(wait_time)
        else:
            logging.error(f"❌ API Error: Could not open spreadsheet after {max_retries} attempts")
            return last_csv_hash
    
    # Add delay before fetching worksheet metadata to avoid quota limits
    time.sleep(1)
    
    # Now get the worksheet with quota-aware retry logic
    worksheet_attempt = 0
    while worksheet_attempt < max_retries:
        try:
            sheet = sh.worksheet(worksheet_name)
            logging.info(f"📖 Opened existing worksheet: {worksheet_name}")
            break
        except gspread.exceptions.WorksheetNotFound:
            try:
                sheet = sh.add_worksheet(title=worksheet_name, rows=2000, cols=30)
                logging.info(f"➕ Created new worksheet: {worksheet_name}")
                break
            except Exception as e:
                logging.error(f"❌ Error creating worksheet {worksheet_name}: {e}")
                return last_csv_hash
        except gspread.exceptions.APIError as e:
            worksheet_attempt += 1
            if "429" in str(e) or "Quota exceeded" in str(e):
                wait_time = 60 * (worksheet_attempt + 1)
                logging.warning(f"⚠ Quota exceeded when accessing worksheet (attempt {worksheet_attempt}/{max_retries}), waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                logging.error(f"❌ Unexpected API Error accessing worksheet: {e}")
                return last_csv_hash
        except Exception as e:
            logging.error(f"❌ Unexpected error accessing worksheet {worksheet_name}: {e}")
            return last_csv_hash

    combined_df = pd.DataFrame()
    new_hash = ""

    # Fetch and combine CSV data from all URLs
    for url in urls:
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            csv_content = response.text
            new_hash += get_csv_hash(csv_content)
            df = pd.read_csv(StringIO(csv_content))
            combined_df = pd.concat([combined_df, df], ignore_index=True)
            logging.info(f"✔ Fetched data from: {url.split('/')[2]} ({len(df)} rows)")

        except requests.exceptions.RequestException as e:
            logging.error(f"❌ CSV Fetch Error from {url}: {e}")
        except Exception as e:
            logging.error(f"❌ Error processing CSV from {url}: {e}")

    if combined_df.empty:
        logging.warning(f"⚠ Empty DataFrame for {worksheet_name} — skipping update!")
        return last_csv_hash

    # Check if data has changed
    if new_hash == last_csv_hash:
        logging.info(f"⏩ No changes detected in: {worksheet_name}")
        return last_csv_hash

    # Clean the dataframe
    combined_df.replace([np.nan, np.inf, -np.inf], "", inplace=True)

    try:
        # Update main sheet
        sheet.clear()
        sheet.update([combined_df.columns.values.tolist()] + combined_df.values.tolist())
        logging.info(f"✔ Main sheet updated: {worksheet_name} ({len(combined_df)} rows, {len(combined_df.columns)} cols)")

        # Try to update brand sheets if brand column exists
        brand_column = get_brand_column(combined_df)
        if brand_column:
            logging.info(f"📊 Found brand column: '{brand_column}'")
            logging.info(f"🏷 Brands in data: {combined_df[brand_column].unique().tolist()}")
            update_brand_sheets(combined_df, spreadsheet_id, brand_column)
        else:
            logging.info(f"ℹ No brand column found in {worksheet_name} - skipping brand sheet updates")
            logging.debug(f"Available columns: {combined_df.columns.tolist()}")

        return new_hash

    except Exception as e:
        logging.error(f"❌ Update Error for {worksheet_name}: {e}")
        return last_csv_hash

def main():
    """Main execution loop"""
    sheet_mapping = {
        "hp_offsite": ("1v_-f5q4M3-QHviU8-myIGMIeSwg48Q0i35QDK9BxOO4", "hp", [
            "https://hpservicecentre.co.in/export_offsite_reports.php",
            "https://hpauthorisedservicecenter.co.in/export_offsite_reports.php",
            "https://hpsparesindia.com/export_offsite_reports.php",
            "https://hpservicecenter.tech/export_offsite_reports.php"
        ]),
        "hp_onsite": ("1Wx8EHcx1Lg9mOGppuWPLbliZOJxYhZ3qkpy8xMkQzLw", "hp", [
            "https://hpservicecentre.co.in/export_customers.php",
            "https://hpauthorisedservicecenter.co.in/export_customers.php",
            "https://hpsparesindia.com/export_customers.php",
            "https://hpservicecenter.tech/export_customers.php"
        ]),
        "lenovo_offsite": ("1v_-f5q4M3-QHviU8-myIGMIeSwg48Q0i35QDK9BxOO4", "lenovo", [
            "https://lenovoservicecentre.co.in/export_offsite_reports.php",
            "https://lenovoservicecentre.com/export_offsite_reports.php"
        ]),
        "lenovo_onsite": ("1Wx8EHcx1Lg9mOGppuWPLbliZOJxYhZ3qkpy8xMkQzLw", "lenovo", [
            "https://lenovoservicecentre.co.in/export_customers.php",
            "https://lenovoservicecentre.com/export_customers.php"
        ]),
        "dell_offsite": ("1v_-f5q4M3-QHviU8-myIGMIeSwg48Q0i35QDK9BxOO4", "dell", [
            "https://mydellrepairs.in/export_offsite_reports.php",
            "https://dellsparesindia.com/export_offsite_reports.php",
            "https://dellservicecentre.com/export_offsite_reports.php",
            "https://dellservicecenter.info/export_offsite_reports.php",
            "https://dellservicescentre.co.in/export_offsite_reports.php"
        ]),
        "dell_onsite": ("1Wx8EHcx1Lg9mOGppuWPLbliZOJxYhZ3qkpy8xMkQzLw", "dell", [
            "https://mydellrepairs.in/export_customers.php",
            "https://dellsparesindia.com/export_customers.php",
            "https://dellservicecentre.com/export_customers.php",
            "https://dellservicecenter.info/export_customers.php",
            "https://dellservicescentre.co.in/export_customers.php"
        ]),
        "acer_offsite": ("1v_-f5q4M3-QHviU8-myIGMIeSwg48Q0i35QDK9BxOO4", "acer", [
            "https://laptopservicencenter.in/export_offsite_reports.php",
            "https://acerservicecenter.tech/export_offsite_reports.php",
            "https://acerservicecentre.com/export_offsite_reports.php",
            "https://laptopservicencenter.in/export_offsite_reports.php"
        ]),
        "acer_onsite": ("1Wx8EHcx1Lg9mOGppuWPLbliZOJxYhZ3qkpy8xMkQzLw", "acer", [
            "https://laptopservicencenter.in/export_customers.php",
            "https://acerservicecenter.tech/export_customers.php",
            "https://acerservicecentre.com/export_customers.php",
            "https://laptopservicencenter.in/export_customers.php"
        ]),
        "asus_offsite": ("1v_-f5q4M3-QHviU8-myIGMIeSwg48Q0i35QDK9BxOO4", "asus", [
            "https://asusservicecentre.in/export_offsite_reports.php"
        ]),
        "asus_onsite": ("1Wx8EHcx1Lg9mOGppuWPLbliZOJxYhZ3qkpy8xMkQzLw", "asus", [
            "https://asusservicecentre.in/export_customers.php"
        ]),
        "apple_offsite": ("1v_-f5q4M3-QHviU8-myIGMIeSwg48Q0i35QDK9BxOO4", "apple", [
            "https://appleservicescentre.co.in/export_offsite_reports.php"
        ]),
        "apple_onsite": ("1Wx8EHcx1Lg9mOGppuWPLbliZOJxYhZ3qkpy8xMkQzLw", "apple", [
            "https://appleservicescentre.co.in/export_customers.php"
        ]),
    }

    # Initialize hash tracking
    for key in sheet_mapping.keys():
        last_hashes.setdefault(key, "")

    logging.info("🚀 Starting Google Sheets sync service...")
    logging.info(f"📊 Monitoring {len(sheet_mapping)} sheet configurations")
    
    cycle_count = 0
    spreadsheet_cache = {}  # Cache spreadsheet connections to reduce API calls
    
    while True:
        cycle_count += 1
        cycle_start_time = time.time()  # Track cycle start time
        logging.info(f"\n{'='*60}")
        logging.info(f"🔄 Starting sync cycle #{cycle_count}")
        logging.info(f"{'='*60}")
        
        for idx, (key, (spreadsheet_id, worksheet_name, urls)) in enumerate(sheet_mapping.items(), 1):
            logging.info(f"\n📋 Processing: {key} ({idx}/{len(sheet_mapping)})")
            last_hashes[key] = update_google_sheet(
                spreadsheet_id, worksheet_name, urls, last_hashes[key], spreadsheet_cache=spreadsheet_cache
            )
            
            # Add delay between sheets to avoid rate limits (except after the last one)
            if idx < len(sheet_mapping):
                time.sleep(1)  # 1 second minimum, but rate limiter will enforce longer delays

        # Clear cache every cycle to force fresh metadata fetches and prevent quota buildup
        spreadsheet_cache.clear()
        logging.info("🔄 Cleared spreadsheet cache")

        # Calculate time spent in cycle
        cycle_elapsed = time.time() - cycle_start_time
        remaining_cycle_time = MIN_CYCLE_INTERVAL - cycle_elapsed
        
        if remaining_cycle_time > 0:
            logging.info(f"\n{'='*60}")
            logging.info(f"⏱ Waiting {remaining_cycle_time:.0f} seconds for next cycle (quota-aware)...")
            logging.info(f"{'='*60}\n")
            time.sleep(remaining_cycle_time)
        else:
            logging.warning(f"⚠ Cycle took longer than minimum interval ({cycle_elapsed:.0f}s > {MIN_CYCLE_INTERVAL}s)")
            time.sleep(5)  # Still wait a bit before next cycle

if __name__ == "__main__":
    main()