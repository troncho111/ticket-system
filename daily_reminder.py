#!/usr/bin/env python3
"""
Daily reminder script for unpaid orders.
Runs at 10:00 AM Israel time every day.
Sends email alert for all orders with status 'sent - not paid'.
"""

import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import resend
import hashlib

def generate_mark_paid_token(order_num, row_index):
    """Generate a verification token for mark-as-paid links - requires SESSION_SECRET"""
    secret = os.environ.get('SESSION_SECRET')
    if not secret or len(secret) < 10:
        return None
    data = f"{order_num}:{row_index}:{secret}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

SHEET_NAME = "מערכת הזמנות - קוד יהודה  "
WORKSHEET_INDEX = 0
OPERATIONS_EMAIL = "operations@tiktik.co.il"

def get_resend_credentials():
    """Get Resend API credentials from Replit connector (same logic as app.py)"""
    try:
        hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
        x_replit_token = None
        
        if os.environ.get('REPL_IDENTITY'):
            x_replit_token = 'repl ' + os.environ.get('REPL_IDENTITY')
        elif os.environ.get('WEB_REPL_RENEWAL'):
            x_replit_token = 'depl ' + os.environ.get('WEB_REPL_RENEWAL')
        
        if not x_replit_token or not hostname:
            print(f"Missing credentials: hostname={hostname}, token={'set' if x_replit_token else 'not set'}")
            return None, None
        
        response = requests.get(
            f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=resend',
            headers={
                'Accept': 'application/json',
                'X_REPLIT_TOKEN': x_replit_token
            }
        )
        data = response.json()
        connection = data.get('items', [{}])[0] if data.get('items') else {}
        settings = connection.get('settings', {})
        
        return settings.get('api_key'), settings.get('from_email')
    except Exception as e:
        print(f"Error getting Resend credentials: {e}")
        return None, None

def get_gspread_client():
    """Create and return authenticated gspread client"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS not found in environment")
    
    if isinstance(creds_json, str):
        creds_dict = json.loads(creds_json)
    else:
        creds_dict = dict(creds_json)
    
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client

def get_unpaid_orders():
    """Get all orders with status 'sent - not paid' or similar, including row index"""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        data = worksheet.get_all_records()
        
        unpaid_orders = []
        for idx, row in enumerate(data):
            status = str(row.get('orderd', '')).lower().strip()
            if 'sent_not_paid' in status or 'sent - not paid' in status or 'נשלח ולא שולם' in status:
                row['_row_index'] = idx + 2
                unpaid_orders.append(row)
        
        return unpaid_orders
    except Exception as e:
        print(f"Error getting unpaid orders: {e}")
        return []

def get_app_base_url():
    """Get the base URL of the published Replit app"""
    return "https://workspace-yehudatiktik.replit.app"

def send_daily_reminder_email(orders_data):
    """Send daily reminder email for unpaid orders - RED THEME with Mark as Paid buttons"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        print("No Resend credentials found")
        return False
    
    resend.api_key = api_key
    
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    app_url = get_app_base_url()
    
    email_body = f"<h2 style='color: #dc2626;'>תזכורת יומית - הזמנות לא שולמו</h2>"
    email_body += f"<p>תאריך: {now.strftime('%Y-%m-%d %H:%M')} (שעון ישראל)</p>"
    email_body += f"<p style='background: #dc2626; color: white; padding: 10px; border-radius: 5px; font-size: 18px;'><strong>{len(orders_data)} הזמנות ממתינות לתשלום</strong></p>"
    email_body += "<hr>"
    
    total_amount = 0
    for idx, order in enumerate(orders_data):
        order_num = order.get('Order number', '-')
        event_name = order.get('event name', '-')
        docket = order.get('docket number', order.get('docket', order.get('Docket', '-')))
        source = order.get('source', '-')
        supp_order = order.get('SUPP order number', '-')
        event_date = order.get('Date of the event', '-')
        qty = order.get('Qty', order.get('QTY', '-'))
        price_sold = order.get('Price sold', '-')
        total_sold = order.get('TOTAL', '-')
        row_index = order.get('_row_index', '')
        
        if total_sold and total_sold != '-':
            try:
                amount = float(str(total_sold).replace('€','').replace('£','').replace('$','').replace(',','').strip())
                total_amount += amount
                total_display = f"€{amount:,.2f}"
            except:
                total_display = str(total_sold)
        else:
            total_display = '-'
        
        token = generate_mark_paid_token(order_num, row_index)
        
        mark_paid_button = ""
        if token:
            mark_paid_url = f"{app_url}?mark_paid={order_num}&row={row_index}&token={token}"
            mark_paid_button = f"""
            <div style="margin-top: 15px; text-align: center;">
                <a href="{mark_paid_url}" style="display: inline-block; background: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px;">
                    סמן כשולם (Done!)
                </a>
            </div>
            """
        
        email_body += f"""
        <div style="background: #fee2e2; padding: 15px; margin: 10px 0; border-radius: 8px; border-right: 4px solid #dc2626;">
            <h3 style="color: #dc2626;">הזמנה #{idx+1} - לא שולם</h3>
            <table style="width: 100%;">
                <tr><td><strong>מספר הזמנה:</strong></td><td>{order_num}</td></tr>
                <tr><td><strong>שם אירוע:</strong></td><td>{event_name}</td></tr>
                <tr><td><strong>מספר דוקט:</strong></td><td>{docket}</td></tr>
                <tr><td><strong>מקור:</strong></td><td>{source}</td></tr>
                <tr><td><strong>מספר הזמנה ספק:</strong></td><td>{supp_order}</td></tr>
                <tr><td><strong>תאריך אירוע:</strong></td><td>{event_date}</td></tr>
                <tr><td><strong>כמות:</strong></td><td>{qty}</td></tr>
                <tr><td><strong>מחיר מקורי לכרטיס:</strong></td><td>{price_sold}</td></tr>
                <tr style="background: #dc2626; color: white;"><td><strong>סכום לגבייה:</strong></td><td><strong>{total_display}</strong></td></tr>
            </table>
            {mark_paid_button}
        </div>
        """
    
    if total_amount > 0:
        email_body += f"<div style='background: #dc2626; color: white; padding: 15px; border-radius: 8px; text-align: center; margin-top: 20px;'><h2>סה\"כ לגבייה: €{total_amount:,.2f}</h2></div>"
    
    email_body += "<hr><p style='color: #666;'>תזכורת יומית אוטומטית ממערכת ניהול הזמנות כרטיסים - נשלחת בשעה 10:00 בבוקר</p>"
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [OPERATIONS_EMAIL],
            "subject": f"🔴 תזכורת יומית - {len(orders_data)} הזמנות לא שולמו! (€{total_amount:,.2f})",
            "html": email_body
        })
        print(f"Email sent successfully! ID: {result.get('id', 'N/A')}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def main():
    """Main function - run daily reminder"""
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    print(f"🔔 Running daily reminder at {now.strftime('%Y-%m-%d %H:%M:%S')} Israel time")
    
    unpaid_orders = get_unpaid_orders()
    
    if not unpaid_orders:
        print("✅ No unpaid orders found - no email needed")
        return
    
    print(f"📋 Found {len(unpaid_orders)} unpaid orders")
    
    success = send_daily_reminder_email(unpaid_orders)
    
    if success:
        print("✅ Daily reminder email sent successfully!")
    else:
        print("❌ Failed to send daily reminder email")

if __name__ == "__main__":
    main()
