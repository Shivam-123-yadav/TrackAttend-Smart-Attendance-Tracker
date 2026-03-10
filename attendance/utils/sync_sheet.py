import gspread
from google.oauth2.service_account import Credentials
import json
import hashlib
import time
import random
import socket
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from requests.exceptions import ConnectionError as RequestsConnectionError


SOURCE_SPREADSHEET_ID = "1IK3Z_ggdm87sd95KFwlW15n_YqkENfhMthNSV2NrO8I"
TARGET_SPREADSHEET_ID = "1gEuoVQW-nXLlYCRqO8pIy_5SYdg7V8PyXoShixVRMYs"
# TARGET_SPREADSHEET_ID = "1xSAxn-AqfcPHzLXd7xWnDGSFniPxniSdhvjcccHIqxg"
CREDS_FILE = "/home/Attendance/public_html/django_attendance_project/automation-scripts.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

def safe_execute(request, delay=5):
    """Safely execute a Google API request with infinite retry on timeout."""
    attempt = 1
    while True:
        try:
            return request.execute()
        except (socket.timeout, TimeoutError) as e:
            print(f"[Timeout] Attempt {attempt}: Retrying in {delay} seconds...")
            time.sleep(delay)
            attempt += 1
        except HttpError as e:
            print(f"[HttpError] {e}")
            break  
    print("Execution failed permanently.")
    return None



def fetch_google_sheet_data(spreadsheet_id):
    sheet = client.open_by_key(spreadsheet_id)
    worksheet = sheet.sheet1
    print(f"Sheet opened: {sheet.title}")
    headers = worksheet.row_values(1)
    seen = {}
    unique_headers = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            unique_headers.append(f"{h}_{seen[h]}") 
        else:
            seen[h] = 0
            unique_headers.append(h)
    values = worksheet.get_all_values()[1:]
    sheet_data = [dict(zip(unique_headers, row)) for row in values]
    sheet_hash = hashlib.md5(json.dumps(sheet_data, sort_keys=True).encode()).hexdigest()
    return sheet_data, sheet_hash


def print_updated_values(sheet_data):
    target_sheet = client.open_by_key(TARGET_SPREADSHEET_ID).sheet1
    source_sheet = client.open_by_key(SOURCE_SPREADSHEET_ID).sheet1

    target_data = target_sheet.get_all_records()
    headers = target_sheet.row_values(1)

    status_color_mapping = {
        'CLOSED': '#F8D7DA',
        'IN PROCESS': '#D1ECF1',
        'WAITING': '#FFF3CD',
        'OPEN': '#D4EDDA'
    }

    update_requests = []
    new_rows_to_append = []
    rows_to_delete = []
    format_requests = []

    for row_index, source_row in enumerate(sheet_data, start=2):
        token_number = source_row.get('Token #')
        status = source_row.get('Status', '').upper()
        row_index_to_modify = None
        for idx, target_row in enumerate(target_data):
            if str(target_row.get('Token #')) == str(token_number):
                row_index_to_modify = idx + 2
                break
        filtered_data = {
            'Token #': source_row.get('Token #'),
            'Customer Name': source_row.get('Customer Name'),
            'Status': source_row.get('Status'),
            'Counters': source_row.get('Counters')
        }
        
        row_values = [filtered_data.get(header, "") for header in headers]

        # if status in ['OPEN', 'WAITING', 'IN PROCESS']:
            # if row_index_to_modify:
                # cell_range = f"A{row_index_to_modify}:{chr(64 + len(headers))}{row_index_to_modify}"
                # update_requests.append({
                    # 'range': cell_range,
                    # 'values': [row_values]
                # })
                # print(f"Queued update for Token {token_number}")
            # else:
                # new_rows_to_append.append(row_values)
                # print(f"Queued new row for Token {token_number}")
        # elif status == "CLOSED" and row_index_to_modify:
            # rows_to_delete.append(row_index_to_modify - 1) 
            # print(f"Status CLOSED. Marked row {row_index_to_modify} for deletion for Token {token_number}.")
        if status in ['OPEN', 'WAITING', 'IN PROCESS']:
            if row_index_to_modify:
                cell_range = f"A{row_index_to_modify}:{chr(64 + len(headers))}{row_index_to_modify}"
                update_requests.append({
                    'range': cell_range,
                    'values': [row_values]
                })
                print(f"Queued update for Token {token_number}")
            else:
                new_rows_to_append.append(row_values)
                print(f"Queued new row for Token {token_number}")

        elif status == "CLOSED" and row_index_to_modify:
            # Safe delete (double verification)
            try:
                matching_token = target_data[row_index_to_modify - 2].get('Token #')
            except IndexError:
                matching_token = None

            if str(matching_token) == str(token_number):
                rows_to_delete.append(row_index_to_modify - 1)
                print(f"Status CLOSED → deleting row for Token {token_number}")
            else:
                print(f"Token mismatch. Skipping delete for Token {token_number}.")

        else:
            print(f"Status is CLOSED but no matching row found for Token {token_number}.")
        color_hex = status_color_mapping.get(status, '#FFFFFF')
        r = int(color_hex[1:3], 16) / 255
        g = int(color_hex[3:5], 16) / 255
        b = int(color_hex[5:7], 16) / 255
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": source_sheet._properties['sheetId'],
                    "startRowIndex": row_index - 1,
                    "endRowIndex": row_index,
                    "startColumnIndex": 11,
                    "endColumnIndex": 12
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": r, "green": g, "blue": b}
                    }
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    service = build('sheets', 'v4', credentials=creds)
    if update_requests:
        body = {'valueInputOption': 'USER_ENTERED', 'data': update_requests}
        safe_execute(service.spreadsheets().values().batchUpdate(
            spreadsheetId=TARGET_SPREADSHEET_ID,
            body=body
        ))
        print(f"{len(update_requests)} rows updated in batch.")

    if new_rows_to_append:
        try:
            target_sheet.append_rows(new_rows_to_append, value_input_option='USER_ENTERED')
            print(f"{len(new_rows_to_append)} rows appended.")
        except Exception as e:
            print(f"Error appending rows: {e}")

    if rows_to_delete:
        delete_requests = []
        for row_index in sorted(rows_to_delete, reverse=True): 
            delete_requests.append({
                "deleteDimension": {
                    "range": {
                        "sheetId": target_sheet._properties['sheetId'],
                        "dimension": "ROWS",
                        "startIndex": row_index,
                        "endIndex": row_index + 1
                    }
                }
            })

        try:
            safe_execute(service.spreadsheets().batchUpdate(
                spreadsheetId=TARGET_SPREADSHEET_ID,
                body={"requests": delete_requests}
            ))
            print(f"{len(delete_requests)} rows deleted for CLOSED status.")
        except Exception as e:
            print(f"Error deleting rows: {e}")

    if format_requests:
        safe_execute(service.spreadsheets().batchUpdate(
            spreadsheetId=SOURCE_SPREADSHEET_ID,
            body={"requests": format_requests}
        ))
        print(f"{len(format_requests)} format requests applied.")


def exponential_backoff(retries):
    wait_time = min(2 ** retries + random.uniform(0, 1), 60)
    print(f"Waiting for {wait_time:.2f} seconds before retrying.")
    time.sleep(wait_time)


if __name__ == "__main__":
    retries = 0
    while True:
        try:
            sheet_data, sheet_hash = fetch_google_sheet_data(SOURCE_SPREADSHEET_ID)
            print_updated_values(sheet_data)
            retries = 0 
            time.sleep(10)
        except gspread.exceptions.APIError as e:
            print(f"Quota or API error encountered: {e}")
            retries += 1
            exponential_backoff(retries)
        except RequestsConnectionError as e:
            print(f"Connection aborted: {e}")
            retries += 1
            exponential_backoff(retries)
        except Exception as e:
            print(f"Unhandled exception occurred: {e}")
            retries += 1
            exponential_backoff(retries)