import os
import sys
import json
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
API_URL = "https://api.monday.com/v2"

HEADERS = {
    "Authorization": MONDAY_API_TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2024-01"
}

def execute_query(query: str, variables: dict = None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    for attempt in range(5):
        try:
            response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
            if response.status_code == 429:
                wait_sec = int(response.headers.get("Retry-After", 5))
                print(f"Rate limited (429). Waiting {wait_sec}s...")
                time.sleep(wait_sec)
                continue
            if response.status_code != 200:
                print(f"HTTP {response.status_code}: {response.text}")
                time.sleep(2)
                continue
            res_data = response.json()
            if "errors" in res_data:
                err_msg = res_data["errors"][0].get("message", "")
                if "complexity" in err_msg.lower() or "limit" in err_msg.lower():
                    time.sleep(3)
                    continue
                raise Exception(f"GraphQL Error: {res_data['errors']}")
            return res_data.get("data", {})
        except requests.exceptions.RequestException as e:
            print(f"Network error on attempt {attempt+1}: {e}")
            time.sleep(2)
    raise Exception("Max retries exceeded for query.")

def create_board(board_name: str):
    mutation = """
    mutation ($boardName: String!, $kind: BoardKind!) {
        create_board (board_name: $boardName, board_kind: $kind) {
            id
            name
        }
    }
    """
    data = execute_query(mutation, {"boardName": board_name, "kind": "public"})
    board_id = data["create_board"]["id"]
    print(f"Created board: '{board_name}' (ID: {board_id})")
    return board_id

def create_column(board_id: str, title: str, column_type: str):
    mutation = """
    mutation ($boardId: ID!, $title: String!, $columnType: ColumnType!) {
        create_column (board_id: $boardId, title: $title, column_type: $columnType) {
            id
            title
        }
    }
    """
    try:
        data = execute_query(mutation, {"boardId": board_id, "title": title, "columnType": column_type})
        col_id = data["create_column"]["id"]
        return col_id
    except Exception as e:
        print(f"  [Warning] Column '{title}' creation note: {e}")
        return None

def get_board_columns(board_id: str):
    query = """
    query ($boardId: [ID!]) {
        boards (ids: $boardId) {
            columns {
                id
                title
                type
            }
        }
    }
    """
    data = execute_query(query, {"boardId": [str(board_id)]})
    return {col["title"].strip().lower(): col["id"] for col in data["boards"][0]["columns"]}

def format_date_for_monday(val):
    if pd.isna(val) or val is None or str(val).strip().lower() in ["nan", "nat", "none", ""]:
        return None
    try:
        dt = pd.to_datetime(val)
        return {"date": dt.strftime("%Y-%m-%d")}
    except Exception:
        return None

def format_number_for_monday(val):
    if pd.isna(val) or val is None:
        return None
    try:
        clean_val = str(val).replace(",", "").replace("₹", "").replace("%", "").strip()
        num = float(clean_val)
        return str(round(num, 2))
    except Exception:
        return None

def format_status_for_monday(val):
    if pd.isna(val) or val is None:
        return None
    text = str(val).strip()
    if not text or text.lower() in ["nan", "none"]:
        return None
    return {"label": text[:30]}

def populate_deals_board(excel_path: str):
    print("\n--- Populating Deals Board ---")
    df = pd.read_excel(excel_path)
    board_id = create_board("Skylark - Deal Funnel (Sales Pipeline)")
    
    # Define columns
    col_defs = [
        ("Owner Code", "text"),
        ("Client Code", "text"),
        ("Deal Status", "status"),
        ("Close Date Actual", "date"),
        ("Closure Probability", "numbers"),
        ("Masked Deal Value", "numbers"),
        ("Tentative Close Date", "date"),
        ("Deal Stage", "status"),
        ("Product Deal", "text"),
        ("Sector", "status"),
        ("Created Date", "date"),
    ]
    
    for title, ctype in col_defs:
        create_column(board_id, title, ctype)
        time.sleep(0.3)
    
    col_map = get_board_columns(board_id)
    print(f"Mapped Deals Columns: {col_map}")
    
    total = len(df)
    print(f"Uploading {total} Deal records...")
    
    for idx, row in df.iterrows():
        deal_name = str(row.get("Deal Name", "")).strip()
        if not deal_name or deal_name.lower() == "nan":
            deal_name = f"Deal #{idx+1}"
            
        values = {}
        
        # Owner Code
        if pd.notna(row.get("Owner code")) and "owner code" in col_map:
            values[col_map["owner code"]] = str(row["Owner code"]).strip()
            
        # Client Code
        if pd.notna(row.get("Client Code")) and "client code" in col_map:
            values[col_map["client code"]] = str(row["Client Code"]).strip()
            
        # Deal Status
        if pd.notna(row.get("Deal Status")) and "deal status" in col_map:
            status_val = format_status_for_monday(row["Deal Status"])
            if status_val:
                values[col_map["deal status"]] = status_val
                
        # Close Date (A)
        if "close date actual" in col_map:
            d_val = format_date_for_monday(row.get("Close Date (A)"))
            if d_val:
                values[col_map["close date actual"]] = d_val
                
        # Closure Probability
        if "closure probability" in col_map:
            prob_raw = str(row.get("Closure Probability", ""))
            prob_num = format_number_for_monday(prob_raw)
            if prob_num:
                values[col_map["closure probability"]] = prob_num
                
        # Masked Deal value
        if "masked deal value" in col_map:
            val_num = format_number_for_monday(row.get("Masked Deal value"))
            if val_num:
                values[col_map["masked deal value"]] = val_num
                
        # Tentative Close Date
        if "tentative close date" in col_map:
            d_val = format_date_for_monday(row.get("Tentative Close Date"))
            if d_val:
                values[col_map["tentative close date"]] = d_val
                
        # Deal Stage
        if pd.notna(row.get("Deal Stage")) and "deal stage" in col_map:
            stage_val = format_status_for_monday(row["Deal Stage"])
            if stage_val:
                values[col_map["deal stage"]] = stage_val
                
        # Product deal
        if pd.notna(row.get("Product deal")) and "product deal" in col_map:
            values[col_map["product deal"]] = str(row["Product deal"]).strip()
            
        # Sector/service
        if pd.notna(row.get("Sector/service")) and "sector" in col_map:
            sec_val = format_status_for_monday(row["Sector/service"])
            if sec_val:
                values[col_map["sector"]] = sec_val
                
        # Created Date
        if "created date" in col_map:
            d_val = format_date_for_monday(row.get("Created Date"))
            if d_val:
                values[col_map["created date"]] = d_val
                
        mutation = """
        mutation ($boardId: ID!, $itemName: String!, $colVals: JSON!) {
            create_item (board_id: $boardId, item_name: $itemName, column_values: $colVals) {
                id
            }
        }
        """
        try:
            execute_query(mutation, {
                "boardId": board_id,
                "itemName": deal_name[:255],
                "colVals": json.dumps(values)
            })
        except Exception as e:
            # Fallback without complex column values if any status failed
            try:
                execute_query(mutation, {
                    "boardId": board_id,
                    "itemName": deal_name[:255],
                    "colVals": "{}"
                })
            except Exception:
                pass
        
        if (idx + 1) % 25 == 0 or (idx + 1) == total:
            print(f"  Uploaded {idx+1}/{total} deals...")
        time.sleep(0.15)
        
    return board_id

def populate_work_orders_board(excel_path: str):
    print("\n--- Populating Work Orders Board ---")
    df_raw = pd.read_excel(excel_path, header=0)
    # The first row contains actual column names
    headers = list(df_raw.iloc[0].values)
    df = df_raw.iloc[1:].copy()
    df.columns = headers
    df.reset_index(drop=True, inplace=True)
    
    board_id = create_board("Skylark - Work Order Tracker (Operations)")
    
    # Define primary columns
    col_defs = [
        ("Customer Code", "text"),
        ("Serial Number", "text"),
        ("Nature of Work", "text"),
        ("Execution Status", "status"),
        ("Data Delivery Date", "date"),
        ("Date of PO LOI", "date"),
        ("Sector", "status"),
        ("Type of Work", "text"),
        ("Last Invoice Date", "date"),
        ("Latest Invoice No", "text"),
        ("Amount Excl GST", "numbers"),
        ("Amount Incl GST", "numbers"),
        ("Billed Value Excl GST", "numbers"),
        ("Billed Value Incl GST", "numbers"),
        ("Collected Amount Incl GST", "numbers"),
        ("Amount To Be Billed Excl GST", "numbers"),
        ("Amount Receivable", "numbers"),
        ("AR Priority", "status"),
        ("Quantities as per PO", "text"),
        ("Balance Quantity", "numbers"),
        ("WO Status Billed", "status"),
        ("Billing Status", "status")
    ]
    
    for title, ctype in col_defs:
        create_column(board_id, title, ctype)
        time.sleep(0.3)
        
    col_map = get_board_columns(board_id)
    print(f"Mapped Work Order Columns: {col_map}")
    
    total = len(df)
    print(f"Uploading {total} Work Order records...")
    
    for idx, row in df.iterrows():
        deal_name = str(row.get("Deal name masked", "")).strip()
        serial = str(row.get("Serial #", "")).strip()
        item_title = f"{serial} - {deal_name}" if serial and deal_name else (deal_name or serial or f"WO #{idx+1}")
        
        values = {}
        
        if pd.notna(row.get("Customer Name Code")) and "customer code" in col_map:
            values[col_map["customer code"]] = str(row["Customer Name Code"]).strip()
            
        if pd.notna(row.get("Serial #")) and "serial number" in col_map:
            values[col_map["serial number"]] = str(row["Serial #"]).strip()
            
        if pd.notna(row.get("Nature of Work")) and "nature of work" in col_map:
            values[col_map["nature of work"]] = str(row["Nature of Work"]).strip()
            
        if pd.notna(row.get("Execution Status")) and "execution status" in col_map:
            stat_val = format_status_for_monday(row["Execution Status"])
            if stat_val:
                values[col_map["execution status"]] = stat_val
                
        if "data delivery date" in col_map:
            d_val = format_date_for_monday(row.get("Data Delivery Date"))
            if d_val:
                values[col_map["data delivery date"]] = d_val
                
        if "date of po loi" in col_map:
            d_val = format_date_for_monday(row.get("Date of PO/LOI"))
            if d_val:
                values[col_map["date of po loi"]] = d_val
                
        if pd.notna(row.get("Sector")) and "sector" in col_map:
            sec_val = format_status_for_monday(row["Sector"])
            if sec_val:
                values[col_map["sector"]] = sec_val
                
        if pd.notna(row.get("Type of Work")) and "type of work" in col_map:
            values[col_map["type of work"]] = str(row["Type of Work"]).strip()
            
        if "last invoice date" in col_map:
            d_val = format_date_for_monday(row.get("Last invoice date"))
            if d_val:
                values[col_map["last invoice date"]] = d_val
                
        if pd.notna(row.get("latest invoice no.")) and "latest invoice no" in col_map:
            values[col_map["latest invoice no"]] = str(row["latest invoice no."]).strip()
            
        # Financial numbers
        num_fields = [
            ("Amount in Rupees (Excl of GST) (Masked)", "amount excl gst"),
            ("Amount in Rupees (Incl of GST) (Masked)", "amount incl gst"),
            ("Billed Value in Rupees (Excl of GST.) (Masked)", "billed value excl gst"),
            ("Billed Value in Rupees (Incl of GST.) (Masked)", "billed value incl gst"),
            ("Collected Amount in Rupees (Incl of GST.) (Masked)", "collected amount incl gst"),
            ("Amount to be billed in Rs. (Exl. of GST) (Masked)", "amount to be billed excl gst"),
            ("Amount Receivable (Masked)", "amount receivable"),
            ("Balance in quantity", "balance quantity")
        ]
        
        for excel_col, monday_key in num_fields:
            if monday_key in col_map:
                val = format_number_for_monday(row.get(excel_col))
                if val:
                    values[col_map[monday_key]] = val
                    
        if pd.notna(row.get("AR Priority account")) and "ar priority" in col_map:
            ar_val = format_status_for_monday(row["AR Priority account"])
            if ar_val:
                values[col_map["ar priority"]] = ar_val
                
        if pd.notna(row.get("Quantities as per PO")) and "quantities as per po" in col_map:
            values[col_map["quantities as per po"]] = str(row["Quantities as per PO"]).strip()
            
        if pd.notna(row.get("WO Status (billed)")) and "wo status billed" in col_map:
            st = format_status_for_monday(row["WO Status (billed)"])
            if st:
                values[col_map["wo status billed"]] = st
                
        if pd.notna(row.get("Billing Status")) and "billing status" in col_map:
            st = format_status_for_monday(row["Billing Status"])
            if st:
                values[col_map["billing status"]] = st
                
        mutation = """
        mutation ($boardId: ID!, $itemName: String!, $colVals: JSON!) {
            create_item (board_id: $boardId, item_name: $itemName, column_values: $colVals) {
                id
            }
        }
        """
        try:
            execute_query(mutation, {
                "boardId": board_id,
                "itemName": item_title[:255],
                "colVals": json.dumps(values)
            })
        except Exception:
            try:
                execute_query(mutation, {
                    "boardId": board_id,
                    "itemName": item_title[:255],
                    "colVals": "{}"
                })
            except Exception:
                pass
                
        if (idx + 1) % 25 == 0 or (idx + 1) == total:
            print(f"  Uploaded {idx+1}/{total} work orders...")
        time.sleep(0.15)
        
    return board_id

if __name__ == "__main__":
    deals_file = "Deal funnel Data.xlsx"
    wo_file = "Work_Order_Tracker Data.xlsx"
    
    print("==================================================")
    print("  Populating Live Monday.com Boards for Skylark   ")
    print("==================================================")
    
    deals_board_id = populate_deals_board(deals_file)
    wo_board_id = populate_work_orders_board(wo_file)
    
    print("\n==================================================")
    print("  BOARD SETUP COMPLETED SUCCESSFULLY!             ")
    print(f"  Deals Board ID:       {deals_board_id}")
    print(f"  Work Orders Board ID: {wo_board_id}")
    print("==================================================")
    
    # Append to .env
    with open(".env", "a") as f:
        f.write(f"\nMONDAY_DEALS_BOARD_ID={deals_board_id}")
        f.write(f"\nMONDAY_WORK_ORDERS_BOARD_ID={wo_board_id}\n")
    print("Updated .env with live Board IDs.")
