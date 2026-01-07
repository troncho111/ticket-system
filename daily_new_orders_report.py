#!/usr/bin/env python3
"""
Daily new orders report script.
Runs at 20:00 Israel time every day.
Sends email report for all orders with status 'new'.
"""

import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz
import resend
import pandas as pd

SHEET_NAME = "מערכת הזמנות - קוד יהודה  "
WORKSHEET_INDEX = 0
DEFAULT_EMAIL = "info@tiktik.co.il"

def get_resend_credentials():
    """Get Resend API credentials from Replit connector"""
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

def get_new_orders():
    """Get all orders with status 'new'"""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if 'orderd' not in df.columns:
            print("No 'orderd' column found")
            return pd.DataFrame()
        
        new_orders = df[df['orderd'].fillna('').str.strip().str.lower() == 'new'].copy()
        
        if 'TOTAL' in new_orders.columns:
            new_orders['TOTAL_clean'] = pd.to_numeric(
                new_orders['TOTAL'].astype(str).str.replace('€', '').str.replace('£', '').str.replace('$', '').str.replace(',', '').str.strip(),
                errors='coerce'
            ).fillna(0)
        
        if 'Date of the event' in new_orders.columns:
            new_orders['parsed_date'] = pd.to_datetime(new_orders['Date of the event'], errors='coerce', dayfirst=True)
        
        return new_orders
    except Exception as e:
        print(f"Error getting new orders: {e}")
        return pd.DataFrame()

def send_daily_report_email(orders_df, to_email):
    """Send daily report email with professional CRM-style format"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        print("No Resend credentials found")
        return False
    
    if orders_df.empty:
        print("No new orders to report")
        return True
    
    resend.api_key = api_key
    
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    total_tickets = int(pd.to_numeric(orders_df.get('Qty', 0), errors='coerce').sum())
    total_amount = orders_df['TOTAL_clean'].sum() if 'TOTAL_clean' in orders_df.columns else 0
    num_orders = len(orders_df)
    
    unique_events = orders_df['event name'].nunique() if 'event name' in orders_df.columns else 0
    unique_sources = orders_df['source'].nunique() if 'source' in orders_df.columns else 0
    
    urgent_orders = 0
    if 'parsed_date' in orders_df.columns:
        today = datetime.now()
        week_ahead = today + timedelta(days=7)
        upcoming_mask = (orders_df['parsed_date'].notna()) & (orders_df['parsed_date'] <= week_ahead) & (orders_df['parsed_date'] >= today)
        urgent_orders = upcoming_mask.sum()
    
    source_breakdown = ""
    if 'source' in orders_df.columns:
        source_counts = orders_df.groupby('source').agg({
            'Order number': 'count',
            'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum()
        }).reset_index()
        source_counts.columns = ['source', 'orders', 'tickets']
        source_counts = source_counts.sort_values('tickets', ascending=False)
        
        source_breakdown = "<table style='width: 100%; margin: 10px 0;'>"
        for _, row in source_counts.head(5).iterrows():
            source_breakdown += f"<tr><td style='padding: 5px;'>{row['source']}</td><td style='padding: 5px; text-align: left;'>{int(row['orders'])} הזמנות | {int(row['tickets'])} כרטיסים</td></tr>"
        source_breakdown += "</table>"
    
    top_events = ""
    if 'event name' in orders_df.columns:
        event_counts = orders_df.groupby('event name').agg({
            'Order number': 'count',
            'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum(),
            'TOTAL_clean': 'sum'
        }).reset_index()
        event_counts.columns = ['event', 'orders', 'tickets', 'value']
        event_counts = event_counts.sort_values('value', ascending=False)
        
        for i, row in event_counts.head(3).iterrows():
            event_display = str(row['event'])[:50]
            top_events += f"<div style='background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px; border-right: 3px solid #667eea;'>"
            top_events += f"<strong>{event_display}...</strong><br>"
            top_events += f"<span style='color: #666;'>{int(row['orders'])} הזמנות | {int(row['tickets'])} כרטיסים | €{row['value']:,.0f}</span>"
            top_events += "</div>"
    
    avg_ticket_value = total_amount / total_tickets if total_tickets > 0 else 0
    
    email_body = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @media only screen and (max-width: 600px) {{
                .main-container {{ padding: 10px !important; }}
                .metric-box {{ width: 48% !important; margin-bottom: 10px !important; }}
                .metric-value {{ font-size: 28px !important; }}
                .insight-card {{ width: 100% !important; margin-bottom: 15px !important; }}
                .stats-row td {{ display: block !important; width: 100% !important; margin-bottom: 10px !important; }}
                .order-table {{ font-size: 11px !important; }}
                .order-table th, .order-table td {{ padding: 5px 3px !important; }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background: #f0f2f5;">
    <div dir="rtl" class="main-container" style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 0 auto; background: white;">
        
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">📊 דוח יומי - כרטיסים לרכישה</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 14px;">קוד יהודה | {now.strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        
        <div style="background: #1a1a2e; color: white; padding: 20px;">
            <h2 style="margin: 0 0 15px 0; color: #ffd700; font-size: 18px;">⚡ סיכום מנהלים</h2>
            
            <table style="width: 100%; border-spacing: 8px;">
                <tr>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 36px; font-weight: bold; color: #667eea;">{num_orders}</div>
                        <div style="color: #aaa; font-size: 12px;">הזמנות פתוחות</div>
                    </td>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 36px; font-weight: bold; color: #28a745;">{total_tickets}</div>
                        <div style="color: #aaa; font-size: 12px;">כרטיסים לרכישה</div>
                    </td>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 36px; font-weight: bold; color: #17a2b8;">€{total_amount:,.0f}</div>
                        <div style="color: #aaa; font-size: 12px;">שווי כולל</div>
                    </td>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 36px; font-weight: bold; color: #ffc107;">{unique_events}</div>
                        <div style="color: #aaa; font-size: 12px;">אירועים שונים</div>
                    </td>
                </tr>
            </table>
        </div>
        
        {"" if urgent_orders == 0 else f'''
        <div style="background: linear-gradient(90deg, #dc3545, #c82333); color: white; padding: 15px 20px;">
            <strong>🚨 התראה דחופה:</strong> {urgent_orders} הזמנות עם אירועים ב-7 ימים הקרובים!
        </div>
        '''}
        
        <div style="background: #f8f9fa; padding: 20px;">
            <h2 style="margin: 0 0 15px 0; color: #333; font-size: 16px;">📈 תובנות מפתח</h2>
            
            <table style="width: 100%;">
                <tr>
                    <td style="width: 50%; vertical-align: top; padding: 8px;">
                        <div style="background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                            <h3 style="margin: 0 0 10px 0; color: #667eea; font-size: 14px;">🏆 אירועים מובילים</h3>
                            {top_events if top_events else "<p>אין נתונים</p>"}
                        </div>
                    </td>
                    <td style="width: 50%; vertical-align: top; padding: 8px;">
                        <div style="background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                            <h3 style="margin: 0 0 10px 0; color: #667eea; font-size: 14px;">📊 פילוח לפי מקור</h3>
                            {source_breakdown if source_breakdown else "<p>אין נתונים</p>"}
                        </div>
                    </td>
                </tr>
            </table>
            
            <div style="background: white; padding: 15px; border-radius: 10px; margin-top: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                <h3 style="margin: 0 0 10px 0; color: #667eea; font-size: 14px;">📊 מדדים נוספים</h3>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px; background: #e8f5e9; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #28a745;">€{avg_ticket_value:,.0f}</div>
                            <div style="color: #666; font-size: 11px;">ממוצע לכרטיס</div>
                        </td>
                        <td style="padding: 8px; background: #e3f2fd; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #1976d2;">{unique_sources}</div>
                            <div style="color: #666; font-size: 11px;">מקורות מכירה</div>
                        </td>
                        <td style="padding: 8px; background: #fff3e0; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #f57c00;">{total_tickets / num_orders:.1f}</div>
                            <div style="color: #666; font-size: 11px;">כרטיסים/הזמנה</div>
                        </td>
                        <td style="padding: 8px; background: #fce4ec; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #c2185b;">€{total_amount / num_orders:,.0f}</div>
                            <div style="color: #666; font-size: 11px;">ממוצע להזמנה</div>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        
        <div style="padding: 20px;">
            <h2 style="margin: 0 0 15px 0; color: #333; font-size: 16px;">📋 פירוט הזמנות ({num_orders})</h2>
            
            <table class="order-table" style="width: 100%; border-collapse: collapse; font-size: 12px;">
                <thead>
                    <tr style="background: #667eea; color: white;">
                        <th style="padding: 10px 6px; border: 1px solid #ddd;">#</th>
                        <th style="padding: 10px 6px; border: 1px solid #ddd;">אירוע</th>
                        <th style="padding: 10px 6px; border: 1px solid #ddd;">תאריך</th>
                        <th style="padding: 10px 6px; border: 1px solid #ddd;">כמות</th>
                        <th style="padding: 10px 6px; border: 1px solid #ddd;">מקור</th>
                        <th style="padding: 10px 6px; border: 1px solid #ddd;">סכום</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for idx, (_, order) in enumerate(orders_df.iterrows()):
        event_name = str(order.get('event name', '-'))[:35]
        event_date = order.get('Date of the event', '-')
        qty = order.get('Qty', '-')
        source = order.get('source', '-')
        total = order.get('TOTAL_clean', 0)
        
        row_bg = '#ffffff' if idx % 2 == 0 else '#f8f9fa'
        
        email_body += f"""
                <tr style="background: {row_bg};">
                    <td style="padding: 6px; border: 1px solid #eee; text-align: center;">{idx + 1}</td>
                    <td style="padding: 6px; border: 1px solid #eee;">{event_name}</td>
                    <td style="padding: 6px; border: 1px solid #eee;">{event_date}</td>
                    <td style="padding: 6px; border: 1px solid #eee; text-align: center; font-weight: bold;">{qty}</td>
                    <td style="padding: 6px; border: 1px solid #eee;">{source}</td>
                    <td style="padding: 6px; border: 1px solid #eee; text-align: left; font-weight: bold;">€{total:,.0f}</td>
                </tr>
        """
    
    email_body += f"""
                </tbody>
                <tfoot>
                    <tr style="background: #333; color: white; font-weight: bold;">
                        <td colspan="3" style="padding: 10px; border: 1px solid #333;">סה"כ</td>
                        <td style="padding: 10px; border: 1px solid #333; text-align: center;">{total_tickets}</td>
                        <td style="padding: 10px; border: 1px solid #333;"></td>
                        <td style="padding: 10px; border: 1px solid #333; text-align: left;">€{total_amount:,.0f}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        
        <div style="background: #1a1a2e; color: #aaa; padding: 20px; text-align: center;">
            <p style="margin: 0; font-size: 14px;">מערכת ניהול הזמנות כרטיסים - קוד יהודה</p>
            <p style="margin: 8px 0 0 0; font-size: 11px;">דוח יומי אוטומטי - {now.strftime('%d/%m/%Y %H:%M')}</p>
            <p style="margin: 8px 0 0 0; font-size: 11px; color: #667eea;">📱 מותאם לצפייה במובייל</p>
        </div>
        
    </div>
    </body>
    </html>
    """
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": f"📊 דוח יומי | {num_orders} הזמנות | {total_tickets} כרטיסים | €{total_amount:,.0f}",
            "html": email_body
        })
        print(f"Email sent successfully! ID: {result.get('id', 'N/A')}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def main():
    """Main function - run daily at 20:00 Israel time"""
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    print(f"Daily New Orders Report - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    orders_df = get_new_orders()
    
    if orders_df.empty:
        print("No new orders found. Skipping email.")
        return
    
    print(f"Found {len(orders_df)} new orders")
    
    success = send_daily_report_email(orders_df, DEFAULT_EMAIL)
    
    if success:
        print("Daily report sent successfully!")
    else:
        print("Failed to send daily report")

if __name__ == "__main__":
    main()
