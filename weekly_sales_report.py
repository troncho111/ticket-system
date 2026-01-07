#!/usr/bin/env python3
"""
Weekly sales report script.
Runs every Friday at 14:00 Israel time.
Sends email report for orders sold THIS WEEK (Sunday to Saturday, filtered by order date in column A).
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
        raise ValueError("GOOGLE_CREDENTIALS not found")
    
    if isinstance(creds_json, str):
        creds_dict = json.loads(creds_json)
    else:
        creds_dict = dict(creds_json)
    
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client

def get_weekly_orders():
    """Get orders from this week (Sunday to Saturday, by order date column A)"""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return pd.DataFrame(), None, None
        
        israel_tz = pytz.timezone('Israel')
        today = datetime.now(israel_tz).date()
        
        start_of_week = today - timedelta(days=today.weekday() + 1)
        if today.weekday() == 6:
            start_of_week = today
        end_of_week = start_of_week + timedelta(days=6)
        
        if 'order date' in df.columns:
            df['order_date_parsed'] = pd.to_datetime(
                df['order date'], 
                format='%m/%d/%Y %H:%M:%S',
                errors='coerce'
            )
            df.loc[df['order_date_parsed'].isna(), 'order_date_parsed'] = pd.to_datetime(
                df.loc[df['order_date_parsed'].isna(), 'order date'],
                dayfirst=True,
                errors='coerce'
            )
            
            weekly_orders = df[
                (df['order_date_parsed'].dt.date >= start_of_week) &
                (df['order_date_parsed'].dt.date <= end_of_week)
            ].copy()
        else:
            print("Warning: 'order date' column not found")
            return pd.DataFrame(), None, None
        
        if 'TOTAL' in weekly_orders.columns:
            weekly_orders['TOTAL_clean'] = pd.to_numeric(
                weekly_orders['TOTAL'].astype(str).str.replace('€', '').str.replace('£', '').str.replace('$', '').str.replace(',', '').str.strip(),
                errors='coerce'
            ).fillna(0)
        
        if 'SUPP PRICE' in weekly_orders.columns:
            weekly_orders['SUPP_PRICE_clean'] = pd.to_numeric(
                weekly_orders['SUPP PRICE'].astype(str).str.replace('€', '').str.replace('£', '').str.replace('$', '').str.replace(',', '').str.strip(),
                errors='coerce'
            ).fillna(0)
        
        return weekly_orders, start_of_week, end_of_week
    except Exception as e:
        print(f"Error getting weekly orders: {e}")
        return pd.DataFrame(), None, None

def send_weekly_sales_email(orders_df, start_of_week, end_of_week, to_email):
    """Send weekly sales report email"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        print("No Resend credentials found")
        return False
    
    if orders_df.empty:
        print("No orders to report for this week")
        return True
    
    resend.api_key = api_key
    
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    week_start_str = start_of_week.strftime('%d/%m/%Y')
    week_end_str = end_of_week.strftime('%d/%m/%Y')
    
    total_tickets = int(pd.to_numeric(orders_df.get('Qty', 0), errors='coerce').sum())
    total_revenue = orders_df['TOTAL_clean'].sum() if 'TOTAL_clean' in orders_df.columns else 0
    total_cost = orders_df['SUPP_PRICE_clean'].sum() if 'SUPP_PRICE_clean' in orders_df.columns else 0
    total_profit = total_revenue - total_cost
    num_orders = len(orders_df)
    unique_events = orders_df['event name'].nunique() if 'event name' in orders_df.columns else 0
    unique_sources = orders_df['source'].nunique() if 'source' in orders_df.columns else 0
    
    days_in_week = (end_of_week - start_of_week).days + 1
    avg_daily_orders = num_orders / days_in_week if days_in_week > 0 else 0
    avg_daily_revenue = total_revenue / days_in_week if days_in_week > 0 else 0
    avg_daily_profit = total_profit / days_in_week if days_in_week > 0 else 0
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    avg_ticket_price = total_revenue / total_tickets if total_tickets > 0 else 0
    
    source_breakdown = ""
    if 'source' in orders_df.columns and 'TOTAL_clean' in orders_df.columns:
        source_stats = orders_df.groupby('source').agg({
            'Order number': 'count',
            'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum(),
            'TOTAL_clean': 'sum'
        }).reset_index()
        source_stats.columns = ['source', 'orders', 'tickets', 'revenue']
        source_stats = source_stats.sort_values('revenue', ascending=False)
        
        for _, row in source_stats.head(5).iterrows():
            pct = (row['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
            source_breakdown += f"<div style='background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px;'>"
            source_breakdown += f"<strong>{row['source']}</strong><br>"
            source_breakdown += f"<span style='color: #666;'>{int(row['orders'])} הזמנות | {int(row['tickets'])} כרטיסים | €{row['revenue']:,.0f} ({pct:.1f}%)</span>"
            source_breakdown += "</div>"
    
    top_events = ""
    if 'event name' in orders_df.columns and 'TOTAL_clean' in orders_df.columns:
        event_stats = orders_df.groupby('event name').agg({
            'Order number': 'count',
            'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum(),
            'TOTAL_clean': 'sum'
        }).reset_index()
        event_stats.columns = ['event', 'orders', 'tickets', 'revenue']
        event_stats = event_stats.sort_values('revenue', ascending=False)
        
        for _, row in event_stats.head(5).iterrows():
            event_display = str(row['event'])[:40]
            top_events += f"<div style='background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px; border-right: 3px solid #6f42c1;'>"
            top_events += f"<strong>{event_display}...</strong><br>"
            top_events += f"<span style='color: #666;'>{int(row['orders'])} הזמנות | {int(row['tickets'])} כרטיסים | €{row['revenue']:,.0f}</span>"
            top_events += "</div>"
    
    email_body = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background: #f0f2f5;">
    <div dir="rtl" style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 0 auto; background: white;">
        
        <div style="background: linear-gradient(135deg, #6f42c1 0%, #9b59b6 100%); color: white; padding: 30px 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">📊 דוח מכירות שבועי</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 14px;">קוד יהודה | {week_start_str} - {week_end_str}</p>
        </div>
        
        <div style="background: #1a1a2e; color: white; padding: 20px;">
            <h2 style="margin: 0 0 15px 0; color: #ffd700; font-size: 18px;">⚡ סיכום שבועי</h2>
            
            <table style="width: 100%; border-spacing: 8px;">
                <tr>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 32px; font-weight: bold; color: #6f42c1;">{num_orders}</div>
                        <div style="color: #aaa; font-size: 12px;">הזמנות</div>
                    </td>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 32px; font-weight: bold; color: #17a2b8;">{total_tickets}</div>
                        <div style="color: #aaa; font-size: 12px;">כרטיסים</div>
                    </td>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 32px; font-weight: bold; color: #28a745;">€{total_revenue:,.0f}</div>
                        <div style="color: #aaa; font-size: 12px;">הכנסות</div>
                    </td>
                    <td style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div style="font-size: 32px; font-weight: bold; color: #ffc107;">€{total_profit:,.0f}</div>
                        <div style="color: #aaa; font-size: 12px;">רווח</div>
                    </td>
                </tr>
            </table>
        </div>
        
        <div style="background: #f8f9fa; padding: 20px;">
            <div style="background: white; padding: 15px; border-radius: 10px; margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; color: #6f42c1; font-size: 14px;">📈 ממוצעים יומיים</h3>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px; background: #f3e5f5; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #6f42c1;">{avg_daily_orders:.1f}</div>
                            <div style="color: #666; font-size: 11px;">הזמנות/יום</div>
                        </td>
                        <td style="padding: 8px; background: #e8f5e9; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #28a745;">€{avg_daily_revenue:,.0f}</div>
                            <div style="color: #666; font-size: 11px;">הכנסות/יום</div>
                        </td>
                        <td style="padding: 8px; background: #fff3e0; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #f57c00;">€{avg_daily_profit:,.0f}</div>
                            <div style="color: #666; font-size: 11px;">רווח/יום</div>
                        </td>
                        <td style="padding: 8px; background: #e3f2fd; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #1976d2;">{profit_margin:.1f}%</div>
                            <div style="color: #666; font-size: 11px;">מרווח רווח</div>
                        </td>
                    </tr>
                </table>
            </div>
            
            <table style="width: 100%;">
                <tr>
                    <td style="width: 50%; vertical-align: top; padding: 8px;">
                        <div style="background: white; padding: 15px; border-radius: 10px;">
                            <h3 style="margin: 0 0 10px 0; color: #6f42c1; font-size: 14px;">🏆 אירועים מובילים (Top 5)</h3>
                            {top_events if top_events else "<p>אין נתונים</p>"}
                        </div>
                    </td>
                    <td style="width: 50%; vertical-align: top; padding: 8px;">
                        <div style="background: white; padding: 15px; border-radius: 10px;">
                            <h3 style="margin: 0 0 10px 0; color: #6f42c1; font-size: 14px;">📊 ביצועים לפי מקור</h3>
                            {source_breakdown if source_breakdown else "<p>אין נתונים</p>"}
                        </div>
                    </td>
                </tr>
            </table>
            
            <div style="background: white; padding: 15px; border-radius: 10px; margin-top: 10px;">
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px; background: #f3e5f5; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #6f42c1;">{unique_events}</div>
                            <div style="color: #666; font-size: 11px;">אירועים</div>
                        </td>
                        <td style="padding: 8px; background: #e8f5e9; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #28a745;">{unique_sources}</div>
                            <div style="color: #666; font-size: 11px;">מקורות</div>
                        </td>
                        <td style="padding: 8px; background: #e3f2fd; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #1976d2;">€{avg_ticket_price:,.0f}</div>
                            <div style="color: #666; font-size: 11px;">ממוצע לכרטיס</div>
                        </td>
                        <td style="padding: 8px; background: #fff3e0; border-radius: 5px; text-align: center;">
                            <div style="font-size: 20px; font-weight: bold; color: #f57c00;">{total_tickets / num_orders:.1f}</div>
                            <div style="color: #666; font-size: 11px;">כרטיסים/הזמנה</div>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        
        <div style="background: #1a1a2e; color: #aaa; padding: 20px; text-align: center;">
            <p style="margin: 0; font-size: 14px;">מערכת ניהול הזמנות כרטיסים - קוד יהודה</p>
            <p style="margin: 8px 0 0 0; font-size: 11px;">דוח שבועי אוטומטי - {now.strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        
    </div>
    </body>
    </html>
    """
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": f"📊 סיכום שבועי {week_start_str}-{week_end_str} | {num_orders} הזמנות | €{total_revenue:,.0f} הכנסות | €{total_profit:,.0f} רווח",
            "html": email_body
        })
        print(f"Email sent successfully! ID: {result.get('id', 'N/A')}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def main():
    """Main function - run every Friday at 14:00 Israel time"""
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    print(f"Weekly Sales Report - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    orders_df, start_of_week, end_of_week = get_weekly_orders()
    
    if orders_df.empty:
        print("No orders found for this week.")
        return
    
    print(f"Found {len(orders_df)} orders for the week {start_of_week} to {end_of_week}")
    
    success = send_weekly_sales_email(orders_df, start_of_week, end_of_week, DEFAULT_EMAIL)
    
    if success:
        print("Weekly sales report sent successfully!")
    else:
        print("Failed to send weekly sales report")

if __name__ == "__main__":
    main()
