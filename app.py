import streamlit as st
import pandas as pd
import gspread
import gspread.exceptions
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import json
import re
import os
import time
import pytz
from streamlit_autorefresh import st_autorefresh
import resend
import requests

ACCOUNTING_EMAIL = "operations@tiktik.co.il"
OPERATIONS_EMAIL = "operations@tiktik.co.il"

def get_resend_credentials():
    """Get Resend API credentials from Streamlit Secrets, environment variables, or Replit connector"""
    # Method 1: Try Streamlit Secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets'):
            # Try different ways to access secrets
            api_key = None
            from_email = None
            
            # Method 1a: Direct access with []
            try:
                if 'RESEND_API_KEY' in st.secrets:
                    api_key = st.secrets['RESEND_API_KEY']
                if 'RESEND_FROM_EMAIL' in st.secrets:
                    from_email = st.secrets['RESEND_FROM_EMAIL']
            except:
                pass
            
            # Method 1b: Try getattr (safer)
            if not api_key:
                try:
                    api_key = getattr(st.secrets, 'RESEND_API_KEY', None)
                except:
                    pass
            
            if not from_email:
                try:
                    from_email = getattr(st.secrets, 'RESEND_FROM_EMAIL', None)
                except:
                    pass
            
            # Method 1c: Try .get() method if available
            if not api_key and hasattr(st.secrets, 'get'):
                try:
                    api_key = st.secrets.get('RESEND_API_KEY')
                    from_email = st.secrets.get('RESEND_FROM_EMAIL')
                except:
                    pass
            
            if api_key and from_email:
                return api_key, from_email
    except Exception as e:
        pass  # Fall through to other methods
    
    # Method 2: Try environment variables (fallback)
    try:
        api_key = os.environ.get('RESEND_API_KEY')
        from_email = os.environ.get('RESEND_FROM_EMAIL')
        if api_key and from_email:
            return api_key, from_email
    except Exception as e:
        pass  # Fall through to Replit connector method
    
    # Method 3: Fallback to Replit connector (for Replit deployments)
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
        # Don't show error if it's just missing Replit credentials (expected on Streamlit Cloud)
        return None, None

def send_payment_collection_email(orders_data):
    """Send payment collection email to accounting"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        error_msg = (
            "לא נמצאו הגדרות Resend.\n\n"
            "💡 **פתרון:** הוסף את הפרטים ב-Streamlit Cloud Secrets:\n"
            "RESEND_API_KEY = \"re_xxxxxxxxxxxxxxxxxxxxxxxxxx\"\n"
            "RESEND_FROM_EMAIL = \"info@tiktik.co.il\""
        )
        return False, error_msg
    
    resend.api_key = api_key
    
    email_body = "<h2>הודעת גבייה - הזמנות נשלחו ולא שולמו</h2>"
    email_body += f"<p>תאריך: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>"
    email_body += "<hr>"
    
    for idx, order in enumerate(orders_data):
        order_num = order.get('Order number', '-')
        event_name = order.get('event name', '-')
        docket = order.get('docket number', order.get('docket', order.get('Docket', '-')))
        source = order.get('source', '-')
        supp_order = order.get('SUPP order number', '-')
        event_date = order.get('Date of the event', '-')
        qty = order.get('Qty', order.get('QTY', '-'))
        price_sold = order.get('Price sold', '-')
        total_sold = order.get('total sold', order.get('TOTAL', order.get('TOTAL_clean', '-')))
        supp_price = order.get('SUPP PRICE', '-')
        
        if total_sold and total_sold != '-':
            try:
                total_display = f"€{float(str(total_sold).replace('€','').replace(',','').strip()):,.2f}"
            except:
                total_display = str(total_sold)
        else:
            total_display = '-'
        
        email_body += f"""
        <div style="background: #fff3cd; padding: 15px; margin: 10px 0; border-radius: 8px; border-right: 4px solid #ffc107;">
            <h3>הזמנה #{idx+1}</h3>
            <table style="width: 100%;">
                <tr><td><strong>מספר הזמנה:</strong></td><td>{order_num}</td></tr>
                <tr><td><strong>שם אירוע:</strong></td><td>{event_name}</td></tr>
                <tr><td><strong>מספר דוקט:</strong></td><td>{docket}</td></tr>
                <tr><td><strong>מקור:</strong></td><td>{source}</td></tr>
                <tr><td><strong>מספר הזמנה ספק:</strong></td><td>{supp_order}</td></tr>
                <tr><td><strong>תאריך אירוע:</strong></td><td>{event_date}</td></tr>
                <tr><td><strong>כמות:</strong></td><td>{qty}</td></tr>
                <tr><td><strong>מחיר מקורי לכרטיס:</strong></td><td>{price_sold}</td></tr>
                <tr style="background: #ffc107;"><td><strong>סכום לגבייה:</strong></td><td><strong>{total_display}</strong></td></tr>
                <tr><td><strong>מחיר ספק:</strong></td><td>{supp_price}</td></tr>
            </table>
        </div>
        """
    
    email_body += "<hr><p style='color: #666;'>הודעה זו נשלחה אוטומטית ממערכת ניהול הזמנות כרטיסים</p>"
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [ACCOUNTING_EMAIL],
            "subject": f"🔔 גבייה נדרשת - {len(orders_data)} הזמנות נשלחו ולא שולמו",
            "html": email_body
        })
        return True, f"המייל נשלח בהצלחה! ID: {result.get('id', 'N/A')}"
    except Exception as e:
        return False, f"שגיאה בשליחת מייל: {str(e)}"

def send_not_paid_email(orders_data):
    """Send NOT PAID alert email to operations - RED THEME"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        error_msg = (
            "לא נמצאו הגדרות Resend.\n\n"
            "💡 **פתרון:** הוסף את הפרטים ב-Streamlit Cloud Secrets:\n"
            "RESEND_API_KEY = \"re_xxxxxxxxxxxxxxxxxxxxxxxxxx\"\n"
            "RESEND_FROM_EMAIL = \"info@tiktik.co.il\""
        )
        return False, error_msg
    
    resend.api_key = api_key
    
    email_body = "<h2 style='color: #dc2626;'>🔴 התראת תשלום - הזמנות נשלחו ולא שולמו!</h2>"
    email_body += f"<p>תאריך: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>"
    email_body += "<p style='background: #dc2626; color: white; padding: 10px; border-radius: 5px; font-size: 18px;'><strong>⚠️ נדרשת פעולה - גביית תשלום</strong></p>"
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
        total_sold = order.get('total sold', order.get('TOTAL', order.get('TOTAL_clean', '-')))
        supp_price = order.get('SUPP PRICE', '-')
        
        if total_sold and total_sold != '-':
            try:
                amount = float(str(total_sold).replace('€','').replace('£','').replace('$','').replace(',','').strip())
                total_amount += amount
                total_display = f"€{amount:,.2f}"
            except:
                total_display = str(total_sold)
        else:
            total_display = '-'
        
        email_body += f"""
        <div style="background: #fee2e2; padding: 15px; margin: 10px 0; border-radius: 8px; border-right: 4px solid #dc2626;">
            <h3 style="color: #dc2626;">🔴 הזמנה #{idx+1} - לא שולם!</h3>
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
                <tr><td><strong>מחיר ספק:</strong></td><td>{supp_price}</td></tr>
            </table>
        </div>
        """
    
    if total_amount > 0:
        email_body += f"<div style='background: #dc2626; color: white; padding: 15px; border-radius: 8px; text-align: center; margin-top: 20px;'><h2>סה\"כ לגבייה: €{total_amount:,.2f}</h2></div>"
    
    email_body += "<hr><p style='color: #666;'>הודעה זו נשלחה אוטומטית ממערכת ניהול הזמנות כרטיסים</p>"
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [OPERATIONS_EMAIL],
            "subject": f"🔴 התראת תשלום - {len(orders_data)} הזמנות לא שולמו!",
            "html": email_body
        })
        return True, f"המייל נשלח בהצלחה! ID: {result.get('id', 'N/A')}"
    except Exception as e:
        return False, f"שגיאה בשליחת מייל: {str(e)}"

def send_payment_confirmation_email(orders_data, payment_method, attachment_data=None, attachment_name=None):
    """Send payment confirmation email to operations with optional attachment"""
    import base64
    
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        error_msg = (
            "לא נמצאו הגדרות Resend.\n\n"
            "💡 **פתרון:** הוסף את הפרטים ב-Streamlit Cloud Secrets:\n"
            "RESEND_API_KEY = \"re_xxxxxxxxxxxxxxxxxxxxxxxxxx\"\n"
            "RESEND_FROM_EMAIL = \"info@tiktik.co.il\""
        )
        return False, error_msg
    
    resend.api_key = api_key
    
    email_body = "<h2>✅ אישור תשלום - הזמנות נשלחו ושולמו</h2>"
    email_body += f"<p>תאריך: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>"
    email_body += f"<p style='background: #28a745; color: white; padding: 10px; border-radius: 5px; font-size: 18px;'><strong>אמצעי תשלום: {payment_method}</strong></p>"
    email_body += "<hr>"
    
    for idx, order in enumerate(orders_data):
        order_num = order.get('Order number', '-')
        event_name = order.get('event name', '-')
        docket = order.get('docket number', order.get('docket', order.get('Docket', '-')))
        source = order.get('source', '-')
        supp_order = order.get('SUPP order number', '-')
        event_date = order.get('Date of the event', '-')
        qty = order.get('Qty', order.get('QTY', '-'))
        price_sold = order.get('Price sold', '-')
        total_sold = order.get('total sold', order.get('TOTAL', order.get('TOTAL_clean', '-')))
        supp_price = order.get('SUPP PRICE', '-')
        
        if total_sold and total_sold != '-':
            try:
                total_display = f"€{float(str(total_sold).replace('€','').replace(',','').strip()):,.2f}"
            except:
                total_display = str(total_sold)
        else:
            total_display = '-'
        
        email_body += f"""
        <div style="background: #d4edda; padding: 15px; margin: 10px 0; border-radius: 8px; border-right: 4px solid #28a745;">
            <h3>הזמנה #{idx+1} - שולם ✅</h3>
            <table style="width: 100%;">
                <tr><td><strong>מספר הזמנה:</strong></td><td>{order_num}</td></tr>
                <tr><td><strong>שם אירוע:</strong></td><td>{event_name}</td></tr>
                <tr><td><strong>מספר דוקט:</strong></td><td>{docket}</td></tr>
                <tr><td><strong>מקור:</strong></td><td>{source}</td></tr>
                <tr><td><strong>מספר הזמנה ספק:</strong></td><td>{supp_order}</td></tr>
                <tr><td><strong>תאריך אירוע:</strong></td><td>{event_date}</td></tr>
                <tr><td><strong>כמות:</strong></td><td>{qty}</td></tr>
                <tr><td><strong>מחיר מקורי לכרטיס:</strong></td><td>{price_sold}</td></tr>
                <tr style="background: #28a745; color: white;"><td><strong>סכום ששולם:</strong></td><td><strong>{total_display}</strong></td></tr>
                <tr><td><strong>מחיר ספק:</strong></td><td>{supp_price}</td></tr>
                <tr style="background: #17a2b8; color: white;"><td><strong>אמצעי תשלום:</strong></td><td><strong>{payment_method}</strong></td></tr>
            </table>
        </div>
        """
    
    if attachment_data and attachment_name:
        email_body += f"<p style='background: #17a2b8; color: white; padding: 8px; border-radius: 5px;'>📎 קובץ אישור תשלום מצורף: {attachment_name}</p>"
    
    email_body += "<hr><p style='color: #666;'>הודעה זו נשלחה אוטומטית ממערכת ניהול הזמנות כרטיסים</p>"
    
    try:
        email_params = {
            "from": from_email,
            "to": [ACCOUNTING_EMAIL],
            "subject": f"✅ אישור תשלום - {len(orders_data)} הזמנות שולמו ({payment_method})",
            "html": email_body
        }
        
        if attachment_data and attachment_name:
            encoded_content = base64.b64encode(attachment_data).decode('utf-8')
            email_params["attachments"] = [{
                "filename": attachment_name,
                "content": encoded_content
            }]
        
        result = resend.Emails.send(email_params)
        attachment_msg = " + קובץ מצורף" if attachment_data else ""
        return True, f"המייל נשלח בהצלחה{attachment_msg}! ID: {result.get('id', 'N/A')}"
    except Exception as e:
        return False, f"שגיאה בשליחת מייל: {str(e)}"

AUTO_REFRESH_INTERVAL_MS = 300000

DEFAULT_NEW_ORDERS_EMAIL = "info@tiktik.co.il"

def send_new_orders_report_email(orders_df, to_email):
    """Send email report with all orders in 'new' status (not yet purchased) - Professional CRM style"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        # Try to get diagnostic info
        diagnostic_info = ""
        try:
            if hasattr(st, 'secrets'):
                available_keys = []
                try:
                    # Try to list available keys
                    if hasattr(st.secrets, 'keys'):
                        available_keys = list(st.secrets.keys())
                    elif hasattr(st.secrets, '__dict__'):
                        available_keys = list(st.secrets.__dict__.keys())
                except:
                    pass
                
                if available_keys:
                    diagnostic_info = f"\n\n**מפתחות זמינים ב-Secrets:** {', '.join(available_keys[:10])}"
                else:
                    diagnostic_info = "\n\n**הערה:** לא נמצאו מפתחות ב-Secrets"
        except:
            pass
        
        error_msg = (
            "❌ **לא נמצאו פרטי התחברות ל-Resend**\n\n"
            "💡 **פתרון:**\n"
            "1. לך ל-Streamlit Cloud Dashboard\n"
            "2. בחר את האפליקציה שלך\n"
            "3. לך ל-Settings > Secrets\n"
            "4. הוסף את השורות הבאות:\n\n"
            "```toml\n"
            "RESEND_API_KEY = \"re_LkgCCYuK_PP7PkrLaWhA4A4qNQ3b9yVFq\"\n"
            "RESEND_FROM_EMAIL = \"info@tiktik.co.il\"\n"
            "```\n\n"
            "5. **חשוב:** ודא שאין רווחים מיותרים או תווים מיוחדים\n"
            "6. שמור את ה-Secrets\n"
            "7. הפעל מחדש את האפליקציה (או לחץ על \"🔄 רענן נתונים\")"
            f"{diagnostic_info}"
        )
        return False, error_msg
    
    if orders_df.empty:
        return False, "אין הזמנות חדשות לשלוח"
    
    resend.api_key = api_key
    
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    if 'TOTAL_clean' not in orders_df.columns:
        if 'TOTAL' in orders_df.columns:
            orders_df = orders_df.copy()
            orders_df['TOTAL_clean'] = pd.to_numeric(
                orders_df['TOTAL'].astype(str).str.replace('€', '').str.replace('£', '').str.replace('$', '').str.replace(',', '').str.strip(),
                errors='coerce'
            ).fillna(0)
        else:
            orders_df = orders_df.copy()
            orders_df['TOTAL_clean'] = 0.0
    
    if 'parsed_date' not in orders_df.columns and 'Date of the event' in orders_df.columns:
        orders_df = orders_df.copy() if 'TOTAL_clean' in orders_df.columns else orders_df
        orders_df['parsed_date'] = pd.to_datetime(orders_df['Date of the event'], errors='coerce', dayfirst=True)
    
    total_tickets = int(pd.to_numeric(orders_df.get('Qty', 0), errors='coerce').sum())
    total_amount = orders_df['TOTAL_clean'].sum() if 'TOTAL_clean' in orders_df.columns else 0
    num_orders = len(orders_df)
    
    unique_events = orders_df['event name'].nunique() if 'event name' in orders_df.columns else 0
    unique_sources = orders_df['source'].nunique() if 'source' in orders_df.columns else 0
    
    urgent_orders = 0
    upcoming_7_days = 0
    if 'parsed_date' in orders_df.columns:
        today = datetime.now()
        week_ahead = today + timedelta(days=7)
        upcoming_mask = (orders_df['parsed_date'].notna()) & (orders_df['parsed_date'] <= week_ahead) & (orders_df['parsed_date'] >= today)
        upcoming_7_days = upcoming_mask.sum()
        urgent_orders = upcoming_7_days
    
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
        
        top_events = ""
        for i, row in event_counts.head(3).iterrows():
            top_events += f"<div style='background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px; border-right: 3px solid #667eea;'>"
            top_events += f"<strong>{row['event'][:50]}...</strong><br>"
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
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">📊 דוח יומי - כרטיסים לרכישה</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 14px;">קוד יהודה | {now.strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        
        <!-- Executive Summary - Mobile Friendly -->
        <div style="background: #1a1a2e; color: white; padding: 20px;">
            <h2 style="margin: 0 0 15px 0; color: #ffd700; font-size: 18px;">⚡ סיכום מנהלים</h2>
            
            <table style="width: 100%; border-spacing: 8px;">
                <tr>
                    <td class="metric-box" style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div class="metric-value" style="font-size: 36px; font-weight: bold; color: #667eea;">{num_orders}</div>
                        <div style="color: #aaa; font-size: 12px;">הזמנות פתוחות</div>
                    </td>
                    <td class="metric-box" style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div class="metric-value" style="font-size: 36px; font-weight: bold; color: #28a745;">{total_tickets}</div>
                        <div style="color: #aaa; font-size: 12px;">כרטיסים לרכישה</div>
                    </td>
                    <td class="metric-box" style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div class="metric-value" style="font-size: 36px; font-weight: bold; color: #17a2b8;">€{total_amount:,.0f}</div>
                        <div style="color: #aaa; font-size: 12px;">שווי כולל</div>
                    </td>
                    <td class="metric-box" style="width: 25%; text-align: center; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                        <div class="metric-value" style="font-size: 36px; font-weight: bold; color: #ffc107;">{unique_events}</div>
                        <div style="color: #aaa; font-size: 12px;">אירועים שונים</div>
                    </td>
                </tr>
            </table>
        </div>
        
        <!-- Alerts Section -->
        {"" if urgent_orders == 0 else f'''
        <div style="background: linear-gradient(90deg, #dc3545, #c82333); color: white; padding: 15px 20px;">
            <strong>🚨 התראה דחופה:</strong> {urgent_orders} הזמנות עם אירועים ב-7 ימים הקרובים!
        </div>
        '''}
        
        <!-- Insights Section -->
        <div style="background: #f8f9fa; padding: 25px;">
            <h2 style="margin: 0 0 20px 0; color: #333;">📈 תובנות מפתח</h2>
            
            <table style="width: 100%;">
                <tr>
                    <td style="width: 50%; vertical-align: top; padding: 10px;">
                        <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                            <h3 style="margin: 0 0 10px 0; color: #667eea;">🏆 אירועים מובילים (לפי שווי)</h3>
                            {top_events if top_events else "<p>אין נתונים</p>"}
                        </div>
                    </td>
                    <td style="width: 50%; vertical-align: top; padding: 10px;">
                        <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                            <h3 style="margin: 0 0 10px 0; color: #667eea;">📊 פילוח לפי מקור</h3>
                            {source_breakdown if source_breakdown else "<p>אין נתונים</p>"}
                        </div>
                    </td>
                </tr>
            </table>
            
            <div style="background: white; padding: 20px; border-radius: 10px; margin-top: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                <h3 style="margin: 0 0 15px 0; color: #667eea;">📊 מדדים נוספים</h3>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 10px; background: #e8f5e9; border-radius: 5px; text-align: center;">
                            <div style="font-size: 24px; font-weight: bold; color: #28a745;">€{avg_ticket_value:,.0f}</div>
                            <div style="color: #666; font-size: 12px;">ממוצע לכרטיס</div>
                        </td>
                        <td style="padding: 10px; background: #e3f2fd; border-radius: 5px; text-align: center;">
                            <div style="font-size: 24px; font-weight: bold; color: #1976d2;">{unique_sources}</div>
                            <div style="color: #666; font-size: 12px;">מקורות מכירה</div>
                        </td>
                        <td style="padding: 10px; background: #fff3e0; border-radius: 5px; text-align: center;">
                            <div style="font-size: 24px; font-weight: bold; color: #f57c00;">{total_tickets / num_orders:.1f}</div>
                            <div style="color: #666; font-size: 12px;">כרטיסים/הזמנה</div>
                        </td>
                        <td style="padding: 10px; background: #fce4ec; border-radius: 5px; text-align: center;">
                            <div style="font-size: 24px; font-weight: bold; color: #c2185b;">€{total_amount / num_orders:,.0f}</div>
                            <div style="color: #666; font-size: 12px;">ממוצע להזמנה</div>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        
        <!-- Order Details -->
        <div style="padding: 25px;">
            <h2 style="margin: 0 0 20px 0; color: #333;">📋 פירוט הזמנות ({num_orders})</h2>
            
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #667eea; color: white;">
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">#</th>
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">אירוע</th>
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">תאריך</th>
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">קטגוריה</th>
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">כמות</th>
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">מס' הזמנה</th>
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">מקור</th>
                        <th style="padding: 12px 8px; border: 1px solid #ddd;">סכום</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for idx, (_, order) in enumerate(orders_df.iterrows()):
        event_name = str(order.get('event name', '-'))[:40]
        event_date = order.get('Date of the event', '-')
        category = order.get('Category / Section', '-')
        qty = order.get('Qty', '-')
        order_num = order.get('Order number', '-')
        source = order.get('source', '-')
        total = order.get('TOTAL_clean', 0)
        
        row_bg = '#ffffff' if idx % 2 == 0 else '#f8f9fa'
        
        email_body += f"""
                <tr style="background: {row_bg};">
                    <td style="padding: 8px; border: 1px solid #eee; text-align: center;">{idx + 1}</td>
                    <td style="padding: 8px; border: 1px solid #eee;">{event_name}</td>
                    <td style="padding: 8px; border: 1px solid #eee;">{event_date}</td>
                    <td style="padding: 8px; border: 1px solid #eee;">{category}</td>
                    <td style="padding: 8px; border: 1px solid #eee; text-align: center; font-weight: bold;">{qty}</td>
                    <td style="padding: 8px; border: 1px solid #eee;">{order_num}</td>
                    <td style="padding: 8px; border: 1px solid #eee;">{source}</td>
                    <td style="padding: 8px; border: 1px solid #eee; text-align: left; font-weight: bold;">€{total:,.0f}</td>
                </tr>
        """
    
    email_body += f"""
                </tbody>
                <tfoot>
                    <tr style="background: #333; color: white; font-weight: bold;">
                        <td colspan="4" style="padding: 12px; border: 1px solid #333;">סה"כ</td>
                        <td style="padding: 12px; border: 1px solid #333; text-align: center;">{total_tickets}</td>
                        <td colspan="2" style="padding: 12px; border: 1px solid #333;"></td>
                        <td style="padding: 12px; border: 1px solid #333; text-align: left;">€{total_amount:,.0f}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        
        <!-- Footer -->
        <div style="background: #1a1a2e; color: #aaa; padding: 20px; text-align: center;">
            <p style="margin: 0; font-size: 14px;">מערכת ניהול הזמנות כרטיסים - קוד יהודה</p>
            <p style="margin: 8px 0 0 0; font-size: 11px;">דוח זה נוצר אוטומטית ב-{now.strftime('%d/%m/%Y %H:%M')}</p>
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
            "subject": f"📊 דוח מנהלים | {num_orders} הזמנות | {total_tickets} כרטיסים | €{total_amount:,.0f}",
            "html": email_body
        })
        return True, f"המייל נשלח בהצלחה! ID: {result.get('id', 'N/A')}"
    except Exception as e:
        return False, f"שגיאה בשליחת מייל: {str(e)}"

def send_daily_sales_report_email(orders_df, to_email, report_date=None):
    """Send daily sales report - professional dark design"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        error_msg = (
            "לא נמצאו פרטי התחברות ל-Resend.\n\n"
            "💡 **פתרון:** הוסף את הפרטים ב-Streamlit Cloud Secrets:\n"
            "RESEND_API_KEY = \"re_xxxxxxxxxxxxxxxxxxxxxxxxxx\"\n"
            "RESEND_FROM_EMAIL = \"info@tiktik.co.il\""
        )
        return False, error_msg
    
    resend.api_key = api_key
    
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    if report_date:
        date_str = report_date.strftime('%d.%m.%Y')
    else:
        date_str = now.strftime('%d.%m.%Y')
    
    num_orders = len(orders_df)
    total_tickets = int(pd.to_numeric(orders_df.get('Qty', 0), errors='coerce').sum())
    avg_tickets = total_tickets / num_orders if num_orders > 0 else 0
    total_revenue = orders_df['TOTAL_clean'].sum() if 'TOTAL_clean' in orders_df.columns else 0
    total_cost = orders_df['SUPP_PRICE_clean'].sum() if 'SUPP_PRICE_clean' in orders_df.columns else 0
    
    orders_with_cost = orders_df[orders_df['SUPP_PRICE_clean'] > 0] if 'SUPP_PRICE_clean' in orders_df.columns else pd.DataFrame()
    orders_without_cost = orders_df[~(orders_df['SUPP_PRICE_clean'] > 0)] if 'SUPP_PRICE_clean' in orders_df.columns else orders_df
    
    actual_profit = 0
    if not orders_with_cost.empty:
        if 'profit' in orders_with_cost.columns:
            actual_profit = orders_with_cost['profit'].sum()
        else:
            actual_profit = orders_with_cost['TOTAL_clean'].sum() - orders_with_cost['SUPP_PRICE_clean'].sum()
    
    revenue_without_cost = orders_without_cost['TOTAL_clean'].sum() if not orders_without_cost.empty and 'TOTAL_clean' in orders_without_cost.columns else 0
    potential_profit = revenue_without_cost * 0.30
    
    total_profit = actual_profit + potential_profit
    profit_note = "*" if potential_profit > 0 else ""
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    source_rows = ""
    if 'source' in orders_df.columns:
        source_stats = orders_df.groupby('source').agg({
            'Order number': 'count',
            'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum(),
            'TOTAL_clean': 'sum',
            'SUPP_PRICE_clean': 'sum'
        }).reset_index()
        source_stats.columns = ['source', 'orders', 'tickets', 'revenue', 'cost']
        source_stats['avg_tickets'] = source_stats['tickets'] / source_stats['orders']
        source_stats['profit'] = source_stats['revenue'] - source_stats['cost']
        source_stats['margin'] = (source_stats['profit'] / source_stats['revenue'] * 100).fillna(0)
        source_stats = source_stats.sort_values('revenue', ascending=False)
        max_revenue = source_stats['revenue'].max() if not source_stats.empty else 1
        
        for _, row in source_stats.iterrows():
            pct_width = int((row['revenue'] / max_revenue) * 100) if max_revenue > 0 else 0
            margin_display = f"{row['margin']:.0f}%" if row['cost'] > 0 else "~30%"
            source_rows += f"""<tr>
<td style="padding:14px 20px;border-bottom:1px solid #253146;color:#f1f5f9;font-size:14px;">{row['source']}</td>
<td style="padding:14px 20px;border-bottom:1px solid #253146;color:#94a3b8;text-align:center;font-family:Consolas,monospace;">{int(row['orders'])}</td>
<td style="padding:14px 20px;border-bottom:1px solid #253146;color:#94a3b8;text-align:center;font-family:Consolas,monospace;">{int(row['tickets'])}</td>
<td style="padding:14px 20px;border-bottom:1px solid #253146;color:#94a3b8;text-align:center;font-family:Consolas,monospace;">{row['avg_tickets']:.1f}</td>
<td style="padding:14px 20px;border-bottom:1px solid #253146;text-align:left;">
<span style="color:#38bdf8;font-family:Consolas,monospace;">EUR {row['revenue']:,.0f}</span>
<div style="background:#2d3b55;height:4px;width:60px;border-radius:2px;margin-top:4px;"><div style="background:#38bdf8;height:4px;width:{pct_width}%;border-radius:2px;"></div></div>
</td>
<td style="padding:14px 20px;border-bottom:1px solid #253146;color:#94a3b8;text-align:left;font-family:Consolas,monospace;">EUR {row['cost']:,.0f}</td>
<td style="padding:14px 20px;border-bottom:1px solid #253146;color:#34d399;text-align:left;font-family:Consolas,monospace;">EUR {row['profit']:,.0f}</td>
<td style="padding:14px 20px;border-bottom:1px solid #253146;color:#a855f7;text-align:center;font-family:Consolas,monospace;">{margin_display}</td>
</tr>"""
    
    potential_note_html = ""
    if potential_profit > 0:
        potential_note_html = f'<div style="color:#64748b;font-size:11px;margin-top:15px;text-align:center;">* כולל רווח פוטנציאלי משוער (30%) עבור הזמנות ללא עלות ספק</div>'
    
    email_body = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body, table, td {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
table {{ border-collapse: collapse !important; }}
body {{ margin: 0 !important; padding: 0 !important; background-color: #162032; color: #e2e8f0; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }}
@media only screen and (max-width: 600px) {{
.stats-cell {{ display: block !important; width: 100% !important; border-left: none !important; border-bottom: 1px solid #2d3b55 !important; }}
.stats-cell:last-child {{ border-bottom: none !important; }}
.inner-table {{ font-size: 12px !important; }}
.inner-table td, .inner-table th {{ padding: 10px 8px !important; }}
}}
</style>
</head>
<body dir="rtl" style="background-color:#162032;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#162032;">
<tr><td align="center">
<div class="email-container" style="width:100%;max-width:100%;background-color:#162032;overflow:hidden;">

<div style="background:linear-gradient(180deg, #1e293b 0%, #162032 100%);padding:30px;border-bottom:1px solid #2d3b55;">
<div style="display:inline-block;background-color:rgba(56,189,248,0.1);color:#38bdf8;padding:4px 10px;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:1px;border:1px solid rgba(56,189,248,0.2);margin-bottom:10px;">DAILY REPORT</div>
<h1 style="color:#ffffff;font-size:22px;margin:0;font-weight:300;">סיכום יומי: <span style="font-weight:700;">{date_str}</span></h1>
<div style="color:#94a3b8;font-size:13px;margin-top:8px;">
<span style="display:inline-block;height:8px;width:8px;background-color:#10b981;border-radius:50%;margin-left:6px;box-shadow:0 0 8px rgba(16,185,129,0.6);"></span>
קוד יהודה | נוצר ב-{now.strftime('%H:%M')}
</div>
</div>

<table width="100%" cellspacing="0" cellpadding="0" border="0">
<tr>
<td class="stats-cell" style="padding:20px;text-align:center;border-left:1px solid #2d3b55;width:25%;background:#1e293b;">
<div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">הזמנות</div>
<div style="font-size:26px;font-weight:700;color:#f8fafc;font-family:Consolas,monospace;">{num_orders}</div>
</td>
<td class="stats-cell" style="padding:20px;text-align:center;border-left:1px solid #2d3b55;width:25%;background:#1e293b;">
<div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">כרטיסים</div>
<div style="font-size:26px;font-weight:700;color:#f8fafc;font-family:Consolas,monospace;">{total_tickets}</div>
</td>
<td class="stats-cell" style="padding:20px;text-align:center;border-left:1px solid #2d3b55;width:25%;background:#1e293b;">
<div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">הכנסה</div>
<div style="font-size:26px;font-weight:700;color:#38bdf8;font-family:Consolas,monospace;">EUR {total_revenue:,.0f}</div>
</td>
<td class="stats-cell" style="padding:20px;text-align:center;width:25%;background:#1e293b;">
<div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">ממוצע/הזמנה</div>
<div style="font-size:26px;font-weight:700;color:#a855f7;font-family:Consolas,monospace;">{avg_tickets:.1f}</div>
</td>
</tr>
</table>

<div style="margin:20px;background-color:#1e293b;border-radius:8px;border:1px solid #334155;overflow:hidden;">
<div style="padding:16px 20px;border-bottom:1px solid #334155;background:linear-gradient(90deg, #1e293b 0%, #243045 100%);position:relative;">
<div style="position:absolute;right:0;top:0;bottom:0;width:4px;background-color:#3b82f6;box-shadow:-4px 0 15px rgba(59,130,246,0.5);"></div>
<span style="font-size:15px;font-weight:600;color:#f1f5f9;">פירוט לפי מקור</span>
</div>
<table class="inner-table" width="100%" cellspacing="0" cellpadding="0" style="background-color:#1a253a;">
<tr style="background-color:#172133;">
<th style="text-align:right;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">מקור</th>
<th style="text-align:center;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">הזמנות</th>
<th style="text-align:center;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">כרטיסים</th>
<th style="text-align:center;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">ממוצע</th>
<th style="text-align:left;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">הכנסה</th>
<th style="text-align:left;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">עלות</th>
<th style="text-align:left;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">רווח</th>
<th style="text-align:center;padding:12px 20px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #2d3b55;">מרווח</th>
</tr>
{source_rows}
</table>
</div>

<div style="background:#111827;padding:25px;margin:20px;border-radius:8px;border:1px solid #374151;text-align:center;position:relative;overflow:hidden;">
<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:200px;height:200px;background:radial-gradient(circle, rgba(52,211,153,0.1) 0%, rgba(0,0,0,0) 70%);"></div>
<div style="position:relative;z-index:1;">
<div style="color:#9ca3af;font-size:12px;letter-spacing:2px;text-transform:uppercase;margin-bottom:5px;">רווח כולל{profit_note}</div>
<div style="font-size:42px;font-weight:700;color:#34d399;letter-spacing:-1px;text-shadow:0 0 25px rgba(52,211,153,0.2);font-family:Consolas,monospace;">EUR {total_profit:,.0f}</div>
<div style="color:#64748b;font-size:13px;margin-top:8px;">מרווח רווח: {profit_margin:.1f}%</div>
</div>
{potential_note_html}
</div>

<div style="text-align:center;padding:25px;border-top:1px solid #1e293b;background-color:#0f172a;">
<div style="color:#475569;font-size:12px;line-height:1.5;">מערכת ניהול הזמנות - קוד יהודה</div>
<div style="color:#38bdf8;font-size:11px;margin-top:8px;">{now.strftime('%d.%m.%Y %H:%M')}</div>
</div>

</div>
</td></tr>
</table>
</body>
</html>"""
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": f"Daily Report {date_str} | {num_orders} Orders | EUR {total_revenue:,.0f} | Profit EUR {total_profit:,.0f}",
            "html": email_body
        })
        return True, f"המייל נשלח בהצלחה! ID: {result.get('id', 'N/A')}"
    except Exception as e:
        return False, f"שגיאה בשליחת מייל: {str(e)}"


def send_weekly_sales_report_email(orders_df, to_email, week_start_date=None, week_end_date=None):
    """Send weekly sales report - summary of the week's sales"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        error_msg = (
            "לא נמצאו פרטי התחברות ל-Resend.\n\n"
            "💡 **פתרון:** הוסף את הפרטים ב-Streamlit Cloud Secrets:\n"
            "RESEND_API_KEY = \"re_xxxxxxxxxxxxxxxxxxxxxxxxxx\"\n"
            "RESEND_FROM_EMAIL = \"info@tiktik.co.il\""
        )
        return False, error_msg
    
    resend.api_key = api_key
    
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    if week_start_date and week_end_date:
        week_start = week_start_date.strftime('%d/%m/%Y')
        week_end = week_end_date.strftime('%d/%m/%Y')
        days_in_week = (week_end_date - week_start_date).days + 1
    else:
        week_start = (now - timedelta(days=7)).strftime('%d/%m/%Y')
        week_end = now.strftime('%d/%m/%Y')
        days_in_week = 7
    
    num_orders = len(orders_df)
    total_tickets = int(pd.to_numeric(orders_df.get('Qty', 0), errors='coerce').sum())
    total_revenue = orders_df['TOTAL_clean'].sum() if 'TOTAL_clean' in orders_df.columns else 0
    
    orders_with_cost = orders_df[orders_df['SUPP_PRICE_clean'] > 0] if 'SUPP_PRICE_clean' in orders_df.columns else pd.DataFrame()
    orders_without_cost = orders_df[~(orders_df['SUPP_PRICE_clean'] > 0)] if 'SUPP_PRICE_clean' in orders_df.columns else orders_df
    
    actual_profit = 0
    if not orders_with_cost.empty:
        if 'profit' in orders_with_cost.columns:
            actual_profit = orders_with_cost['profit'].sum()
        else:
            actual_profit = orders_with_cost['TOTAL_clean'].sum() - orders_with_cost['SUPP_PRICE_clean'].sum()
    
    revenue_without_cost = orders_without_cost['TOTAL_clean'].sum() if not orders_without_cost.empty and 'TOTAL_clean' in orders_without_cost.columns else 0
    potential_profit = revenue_without_cost * 0.30
    
    total_profit = actual_profit + potential_profit
    profit_label = "רווח פוטנציאלי (30%)" if potential_profit > actual_profit else "רווח"
    
    unique_events = orders_df['event name'].nunique() if 'event name' in orders_df.columns else 0
    unique_sources = orders_df['source'].nunique() if 'source' in orders_df.columns else 0
    
    avg_daily_orders = num_orders / days_in_week if days_in_week > 0 else 0
    avg_daily_revenue = total_revenue / days_in_week if days_in_week > 0 else 0
    avg_daily_profit = total_profit / days_in_week if days_in_week > 0 else 0
    profit_margin = 30.0 if potential_profit > actual_profit else ((actual_profit / orders_with_cost['TOTAL_clean'].sum() * 100) if not orders_with_cost.empty and orders_with_cost['TOTAL_clean'].sum() > 0 else 0)
    avg_ticket_price = total_revenue / total_tickets if total_tickets > 0 else 0
    tickets_per_order = total_tickets / num_orders if num_orders > 0 else 0
    
    source_breakdown = ""
    if 'source' in orders_df.columns:
        source_stats = orders_df.groupby('source').agg({
            'Order number': 'count',
            'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum(),
            'TOTAL_clean': 'sum'
        }).reset_index()
        source_stats.columns = ['source', 'orders', 'tickets', 'revenue']
        source_stats = source_stats.sort_values('revenue', ascending=False)
        
        for _, row in source_stats.head(4).iterrows():
            pct = (row['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
            source_breakdown += f"<div style='padding:8px;margin:4px 0;background:#fff;border-radius:5px;'><b>{row['source']}</b><br><span style='color:#666;font-size:12px;'>{int(row['orders'])} הזמנות | €{row['revenue']:,.0f} ({pct:.0f}%)</span></div>"
    
    top_events = ""
    if 'event name' in orders_df.columns:
        event_stats = orders_df.groupby('event name').agg({
            'Order number': 'count',
            'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum(),
            'TOTAL_clean': 'sum'
        }).reset_index()
        event_stats.columns = ['event', 'orders', 'tickets', 'revenue']
        event_stats = event_stats.sort_values('revenue', ascending=False)
        
        for _, row in event_stats.head(4).iterrows():
            event_display = str(row['event'])[:28]
            top_events += f"<div style='padding:8px;margin:4px 0;background:#fff;border-radius:5px;border-right:3px solid #6f42c1;'><b>{event_display}...</b><br><span style='color:#666;font-size:12px;'>{int(row['orders'])} הזמנות | €{row['revenue']:,.0f}</span></div>"
    
    email_body = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,sans-serif;">
<div dir="rtl" style="max-width:600px;margin:0 auto;background:#fff;">

<div style="background:linear-gradient(135deg,#6f42c1,#9b59b6);color:#fff;padding:20px;text-align:center;">
<div style="font-size:22px;font-weight:bold;">📊 דוח מכירות שבועי</div>
<div style="font-size:13px;opacity:0.9;margin-top:5px;">קוד יהודה | {week_start} - {week_end}</div>
</div>

<div style="background:#1a1a2e;color:#fff;padding:15px;">
<div style="display:flex;flex-wrap:wrap;justify-content:space-around;text-align:center;">
<div style="flex:1;min-width:70px;padding:10px;">
<div style="font-size:26px;font-weight:bold;color:#6f42c1;">{num_orders}</div>
<div style="font-size:11px;color:#aaa;">הזמנות</div>
</div>
<div style="flex:1;min-width:70px;padding:10px;">
<div style="font-size:26px;font-weight:bold;color:#17a2b8;">{total_tickets}</div>
<div style="font-size:11px;color:#aaa;">כרטיסים</div>
</div>
<div style="flex:1;min-width:70px;padding:10px;">
<div style="font-size:26px;font-weight:bold;color:#28a745;">€{total_revenue:,.0f}</div>
<div style="font-size:11px;color:#aaa;">הכנסות</div>
</div>
<div style="flex:1;min-width:70px;padding:10px;">
<div style="font-size:26px;font-weight:bold;color:#ffc107;">€{total_profit:,.0f}</div>
<div style="font-size:11px;color:#aaa;">{profit_label}</div>
</div>
</div>
</div>

<div style="padding:15px;background:#f8f9fa;">
<div style="font-size:14px;font-weight:bold;color:#333;margin-bottom:10px;">📈 ממוצעים יומיים</div>
<div style="display:flex;flex-wrap:wrap;justify-content:space-around;text-align:center;">
<div style="flex:1;min-width:70px;padding:8px;margin:4px;background:#f3e5f5;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#6f42c1;">{avg_daily_orders:.1f}</div>
<div style="font-size:10px;color:#666;">הזמנות/יום</div>
</div>
<div style="flex:1;min-width:70px;padding:8px;margin:4px;background:#e8f5e9;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#28a745;">€{avg_daily_revenue:,.0f}</div>
<div style="font-size:10px;color:#666;">הכנסות/יום</div>
</div>
<div style="flex:1;min-width:70px;padding:8px;margin:4px;background:#fff3e0;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#f57c00;">€{avg_daily_profit:,.0f}</div>
<div style="font-size:10px;color:#666;">רווח/יום</div>
</div>
<div style="flex:1;min-width:70px;padding:8px;margin:4px;background:#e3f2fd;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#1976d2;">{profit_margin:.0f}%</div>
<div style="font-size:10px;color:#666;">מרווח</div>
</div>
</div>
</div>

<div style="padding:15px;background:#fff;">
<div style="font-size:14px;font-weight:bold;color:#333;margin-bottom:10px;">🏆 אירועים מובילים</div>
{top_events if top_events else "<div style='color:#666;'>אין נתונים</div>"}
</div>

<div style="padding:15px;background:#f8f9fa;">
<div style="font-size:14px;font-weight:bold;color:#333;margin-bottom:10px;">📊 מקורות</div>
{source_breakdown if source_breakdown else "<div style='color:#666;'>אין נתונים</div>"}
</div>

<div style="padding:15px;background:#fff;">
<div style="display:flex;flex-wrap:wrap;justify-content:space-around;text-align:center;">
<div style="flex:1;min-width:80px;padding:8px;margin:4px;background:#f3e5f5;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#6f42c1;">{unique_events}</div>
<div style="font-size:10px;color:#666;">אירועים</div>
</div>
<div style="flex:1;min-width:80px;padding:8px;margin:4px;background:#e8f5e9;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#28a745;">{unique_sources}</div>
<div style="font-size:10px;color:#666;">מקורות</div>
</div>
<div style="flex:1;min-width:80px;padding:8px;margin:4px;background:#e3f2fd;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#1976d2;">€{avg_ticket_price:,.0f}</div>
<div style="font-size:10px;color:#666;">ממוצע/כרטיס</div>
</div>
<div style="flex:1;min-width:80px;padding:8px;margin:4px;background:#fff3e0;border-radius:8px;">
<div style="font-size:18px;font-weight:bold;color:#f57c00;">{tickets_per_order:.1f}</div>
<div style="font-size:10px;color:#666;">כרטיסים/הזמנה</div>
</div>
</div>
</div>

<div style="background:#1a1a2e;color:#aaa;padding:15px;text-align:center;font-size:11px;">
<div>מערכת ניהול הזמנות - קוד יהודה</div>
<div style="margin-top:5px;">{now.strftime('%d/%m/%Y %H:%M')}</div>
</div>

</div>
</body>
</html>"""
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": f"📊 שבועי {week_start}-{week_end} | {num_orders} הזמנות | €{total_revenue:,.0f} | רווח €{total_profit:,.0f}",
            "html": email_body
        })
        return True, f"המייל נשלח בהצלחה! ID: {result.get('id', 'N/A')}"
    except Exception as e:
        return False, f"שגיאה בשליחת מייל: {str(e)}"


def send_unpaid_orders_report_email(orders_df, to_email):
    """Send email report with all unpaid orders (sent - not paid) - RED THEME with Mark as Paid buttons"""
    api_key, from_email = get_resend_credentials()
    
    if not api_key or not from_email:
        error_msg = (
            "❌ **לא נמצאו פרטי התחברות ל-Resend**\n\n"
            "💡 **פתרון:** הוסף את הפרטים ב-Streamlit Cloud Secrets:\n"
            "RESEND_API_KEY = \"re_xxxxxxxxxxxxxxxxxxxxxxxxxx\"\n"
            "RESEND_FROM_EMAIL = \"info@tiktik.co.il\""
        )
        return False, error_msg
    
    if orders_df.empty:
        return False, "אין הזמנות שלא שולמו לשלוח"
    
    resend.api_key = api_key
    
    israel_tz = pytz.timezone('Israel')
    now = datetime.now(israel_tz)
    
    # Get app base URL for mark-as-paid links
    # Try to get from Streamlit secrets first, then environment, then default
    app_url = None
    try:
        if hasattr(st, 'secrets') and 'APP_BASE_URL' in st.secrets:
            app_url = st.secrets['APP_BASE_URL']
    except:
        pass
    
    if not app_url:
        app_url = os.environ.get('APP_BASE_URL', None)
    
    if not app_url:
        # Try to get from Streamlit config
        try:
            import streamlit as st_module
            if hasattr(st_module, 'config') and hasattr(st_module.config, 'server'):
                # For Streamlit Cloud, we can try to construct the URL
                # But for now, use a default that works
                app_url = 'https://workspace-yehudatiktik.replit.app'
        except:
            app_url = 'https://workspace-yehudatiktik.replit.app'
    
    # Calculate totals
    total_amount = 0
    if 'TOTAL' in orders_df.columns:
        for total_val in orders_df['TOTAL']:
            if total_val and total_val != '-':
                try:
                    amount = float(str(total_val).replace('€','').replace('£','').replace('$','').replace(',','').strip())
                    total_amount += amount
                except:
                    pass
    
    email_body = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,sans-serif;">
<div dir="rtl" style="max-width:600px;margin:0 auto;background:#fff;">

<div style="background:linear-gradient(135deg,#dc2626,#ef4444);color:#fff;padding:20px;text-align:center;">
<div style="font-size:22px;font-weight:bold;">🔴 תזכורת - הזמנות לא שולמו</div>
<div style="font-size:13px;opacity:0.9;margin-top:5px;">קוד יהודה | {now.strftime('%d/%m/%Y %H:%M')}</div>
</div>

<div style="background:#dc2626;color:#fff;padding:15px;text-align:center;font-size:18px;font-weight:bold;">
{len(orders_df)} הזמנות ממתינות לתשלום
</div>

<div style="padding:20px;">
"""
    
    # Generate mark-as-paid tokens and build order cards
    for idx, (_, order) in enumerate(orders_df.iterrows()):
        order_num = order.get('Order number', '-')
        event_name = order.get('event name', '-')
        docket = order.get('docket number', order.get('docket', order.get('Docket', '-')))
        source = order.get('source', '-')
        supp_order = order.get('SUPP order number', '-')
        event_date = order.get('Date of the event', '-')
        qty = order.get('Qty', order.get('QTY', '-'))
        price_sold = order.get('Price sold', '-')
        total_sold = order.get('TOTAL', '-')
        row_index = order.get('row_index', '')
        
        if total_sold and total_sold != '-':
            try:
                amount = float(str(total_sold).replace('€','').replace('£','').replace('$','').replace(',','').strip())
                total_display = f"€{amount:,.2f}"
            except:
                total_display = str(total_sold)
        else:
            total_display = '-'
        
        # Generate mark-as-paid token and button
        mark_paid_button = ""
        
        # Get row_index - try multiple ways
        row_idx = None
        if 'row_index' in order:
            row_idx_val = order['row_index']
            if pd.notna(row_idx_val):
                try:
                    row_idx = int(row_idx_val)
                except:
                    try:
                        row_idx = int(float(row_idx_val))
                    except:
                        pass
        
        # If row_index is valid, create the button
        if row_idx and row_idx > 1:  # row_index should be >= 2 (row 1 is header)
            try:
                # Try to get SESSION_SECRET from environment or secrets
                secret = None
                try:
                    secret = os.environ.get('SESSION_SECRET')
                except:
                    pass
                
                if not secret:
                    try:
                        if hasattr(st, 'secrets') and 'SESSION_SECRET' in st.secrets:
                            secret = st.secrets['SESSION_SECRET']
                    except:
                        pass
                
                # Create URL with or without token
                if secret and len(secret) >= 10:
                    # With token (secure)
                    data = f"{order_num}:{row_idx}:{secret}"
                    token = hashlib.sha256(data.encode()).hexdigest()[:16]
                    mark_paid_url = f"{app_url}?mark_paid={order_num}&row={row_idx}&token={token}"
                else:
                    # Without token (less secure, but works)
                    mark_paid_url = f"{app_url}?mark_paid={order_num}&row={row_idx}"
                
                mark_paid_button = f"""
            <div style="margin-top: 15px; text-align: center;">
                <a href="{mark_paid_url}" style="display: inline-block; background: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px;">
                    ✅ סמן כשולם (Done!)
                </a>
            </div>
            """
            except Exception as e:
                # Even if there's an error, try to create a basic button
                try:
                    mark_paid_url = f"{app_url}?mark_paid={order_num}&row={row_idx}"
                    mark_paid_button = f"""
            <div style="margin-top: 15px; text-align: center;">
                <a href="{mark_paid_url}" style="display: inline-block; background: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px;">
                    ✅ סמן כשולם (Done!)
                </a>
            </div>
            """
                except:
                    pass
        
        email_body += f"""
        <div style="background: #fee2e2; padding: 15px; margin: 10px 0; border-radius: 8px; border-right: 4px solid #dc2626;">
            <h3 style="color: #dc2626; margin-top: 0;">הזמנה #{idx+1} - לא שולם</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 5px;"><strong>מספר הזמנה:</strong></td><td style="padding: 5px;">{order_num}</td></tr>
                <tr><td style="padding: 5px;"><strong>שם אירוע:</strong></td><td style="padding: 5px;">{event_name}</td></tr>
                <tr><td style="padding: 5px;"><strong>מספר דוקט:</strong></td><td style="padding: 5px;">{docket}</td></tr>
                <tr><td style="padding: 5px;"><strong>מקור:</strong></td><td style="padding: 5px;">{source}</td></tr>
                <tr><td style="padding: 5px;"><strong>מספר הזמנה ספק:</strong></td><td style="padding: 5px;">{supp_order}</td></tr>
                <tr><td style="padding: 5px;"><strong>תאריך אירוע:</strong></td><td style="padding: 5px;">{event_date}</td></tr>
                <tr><td style="padding: 5px;"><strong>כמות:</strong></td><td style="padding: 5px;">{qty}</td></tr>
                <tr><td style="padding: 5px;"><strong>מחיר מקורי לכרטיס:</strong></td><td style="padding: 5px;">{price_sold}</td></tr>
                <tr style="background: #dc2626; color: white;"><td style="padding: 5px;"><strong>סכום לגבייה:</strong></td><td style="padding: 5px;"><strong>{total_display}</strong></td></tr>
            </table>
            {mark_paid_button}
        </div>
        """
    
    if total_amount > 0:
        email_body += f"""
<div style="background: #dc2626; color: white; padding: 15px; border-radius: 8px; text-align: center; margin-top: 20px;">
<h2 style="margin: 0;">סה"כ לגבייה: €{total_amount:,.2f}</h2>
</div>
"""
    
    email_body += """
</div>

<div style="background:#1a1a2e;color:#aaa;padding:15px;text-align:center;font-size:11px;">
<div>מערכת ניהול הזמנות - קוד יהודה</div>
<div style="margin-top:5px;">דוח יזום - הזמנות שלא שולמו</div>
</div>

</div>
</body>
</html>"""
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": f"🔴 תזכורת - {len(orders_df)} הזמנות לא שולמו! (€{total_amount:,.2f})",
            "html": email_body
        })
        return True, f"המייל נשלח בהצלחה! ID: {result.get('id', 'N/A')}"
    except Exception as e:
        return False, f"שגיאה בשליחת מייל: {str(e)}"


SOURCE_DISPLAY_NAMES = {
    'goldenseat': 'Goldenseat/TikTik',
    'tiktik': 'Goldenseat/TikTik',
    'footballticketnet': 'FootballTicketNet',
    'faqs': 'FAQS',
    'orders.viagogo.com': 'Viagogo',
    'ticketgum': 'TicketGum',
    'go-go-passion': 'Go-Go-PASSION',
    'viagogo': 'Viagogo',
}

COMMISSION_RATES = {
    'tixstock': 0.03,
}

def get_commission_rate(source_val):
    """Get commission rate for a source (0 if no commission)"""
    normalized = normalize_source(source_val)
    return COMMISSION_RATES.get(normalized, 0.0)

def normalize_source(source_val):
    """Normalize source name to lowercase for consistent grouping"""
    if pd.isna(source_val) or source_val is None:
        return ''
    return str(source_val).strip().lower()

def get_source_display_name(source_val):
    """Get display name for source with proper formatting"""
    normalized = normalize_source(source_val)
    if normalized in SOURCE_DISPLAY_NAMES:
        return SOURCE_DISPLAY_NAMES[normalized]
    elif normalized:
        return normalized.title()
    return '-'

def get_sorted_event_options(dataframe, last_selected=None):
    """Get event names sorted by closest date to today (future first, then past).
    If last_selected is provided, it will be moved to the front of the list."""
    if dataframe.empty or 'event name' not in dataframe.columns:
        return []
    
    today = pd.Timestamp.now().normalize()
    all_events = dataframe['event name'].dropna().unique().tolist()
    result_list = []
    
    if 'parsed_date' in dataframe.columns:
        event_dates = dataframe.groupby('event name')['parsed_date'].min().reset_index()
        events_with_dates = event_dates[event_dates['parsed_date'].notna()].copy()
        events_without_dates = event_dates[event_dates['parsed_date'].isna()]['event name'].tolist()
        
        if not events_with_dates.empty:
            events_with_dates['days_from_today'] = (events_with_dates['parsed_date'] - today).dt.days
            future_events = events_with_dates[events_with_dates['days_from_today'] >= 0].sort_values('days_from_today')
            past_events = events_with_dates[events_with_dates['days_from_today'] < 0].sort_values('days_from_today', ascending=False)
            sorted_events = pd.concat([future_events, past_events])
            result_list = sorted_events['event name'].tolist() + events_without_dates
        else:
            result_list = all_events
    else:
        result_list = all_events
    
    if last_selected and last_selected in result_list:
        result_list.remove(last_selected)
        result_list.insert(0, last_selected)
    
    return result_list

st.set_page_config(
    page_title="Ticket Agency Management",
    page_icon="🎫",
    layout="wide"
)

import hashlib

def verify_mark_paid_token(order_num, row_index, token):
    """Verify the mark-as-paid token - requires SESSION_SECRET to be set"""
    secret = os.environ.get('SESSION_SECRET')
    if not secret or len(secret) < 10:
        return False
    data = f"{order_num}:{row_index}:{secret}"
    expected_token = hashlib.sha256(data.encode()).hexdigest()[:16]
    return token == expected_token

query_params = st.query_params
mark_paid_order = query_params.get('mark_paid', None)
mark_paid_row = query_params.get('row', None)
mark_paid_token = query_params.get('token', None)

if mark_paid_order and mark_paid_row and mark_paid_token:
    try:
        row_index = int(mark_paid_row)
        
        if not verify_mark_paid_token(mark_paid_order, row_index, mark_paid_token):
            st.error("קישור לא תקין - אין הרשאה לעדכן")
            st.query_params.clear()
        else:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); 
                        padding: 30px; border-radius: 15px; margin: 20px 0; text-align: center;">
                <h2 style="color: white; margin: 0;">מעדכן סטטוס הזמנה...</h2>
                <p style="color: white; font-size: 18px;">הזמנה: {order}</p>
            </div>
            """.format(order=mark_paid_order), unsafe_allow_html=True)
            
            client = get_gspread_client()
            sheet = client.open(SHEET_NAME)
            worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
            
            row_data = worksheet.row_values(row_index)
            headers = worksheet.row_values(1)
            order_col = None
            for i, header in enumerate(headers):
                if header.strip().lower() == 'order number':
                    order_col = i
                    break
            
            if order_col is not None and len(row_data) > order_col:
                sheet_order_num = str(row_data[order_col]).strip()
                if sheet_order_num != str(mark_paid_order).strip():
                    st.error(f"שגיאה: מספר הזמנה לא תואם (צפוי: {mark_paid_order}, בגיליון: {sheet_order_num})")
                    st.query_params.clear()
                else:
                    ordered_col = None
                    for i, header in enumerate(headers):
                        if header.strip().lower() == 'orderd':
                            ordered_col = i + 1
                            break
                    
                    if ordered_col:
                        col_letter = col_number_to_letter(ordered_col)
                        worksheet.update(f'{col_letter}{row_index}', [['Done!']])
                        
                        color = {"red": 0.85, "green": 1.0, "blue": 0.85}
                        last_col = len(headers)
                        requests_batch = [{
                            'repeatCell': {
                                'range': {
                                    'sheetId': worksheet.id,
                                    'startRowIndex': row_index - 1,
                                    'endRowIndex': row_index,
                                    'startColumnIndex': 0,
                                    'endColumnIndex': last_col
                                },
                                'cell': {
                                    'userEnteredFormat': {
                                        'backgroundColor': color
                                    }
                                },
                                'fields': 'userEnteredFormat.backgroundColor'
                            }
                        }]
                        sheet.batch_update({'requests': requests_batch})
                        
                        st.success(f"הסטטוס של הזמנה {mark_paid_order} עודכן ל-Done!")
                        st.balloons()
                        
                        st.query_params.clear()
                    else:
                        st.error("לא נמצאה עמודת סטטוס בגיליון")
            else:
                st.error("לא ניתן לאמת את מספר ההזמנה")
                st.query_params.clear()
    except Exception as e:
        st.error(f"שגיאה בעדכון הסטטוס: {e}")

refresh_count = st_autorefresh(interval=AUTO_REFRESH_INTERVAL_MS, limit=None, key="data_autorefresh")

if 'language' not in st.session_state:
    st.session_state.language = 'he'

is_rtl = st.session_state.get('language', 'he') == 'he'

if is_rtl:
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] {
            direction: rtl;
        }
        [data-testid="stSidebar"] {
            direction: rtl;
            text-align: right;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            background-color: #f0f2f6;
            padding: 8px;
            border-radius: 10px;
            direction: rtl !important;
            justify-content: stretch !important;
            flex-direction: row-reverse !important;
            width: 100% !important;
        }
        .stTabs [data-baseweb="tab"] {
            flex: 1 !important;
            height: 45px;
            padding: 8px 12px;
            background-color: white;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            border: 2px solid #e0e0e0;
            direction: rtl;
            white-space: nowrap;
            text-align: center;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ff6b6b !important;
            color: white !important;
            border: 2px solid #ff6b6b !important;
        }
        .stMarkdown, .stText, h1, h2, h3, h4, p {
            text-align: right;
        }
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
            text-align: center;
        }
        .alert-card {
            padding: 20px;
            border-radius: 10px;
            min-height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 20px;
            background-color: white;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            border: 2px solid #e0e0e0;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ff6b6b !important;
            color: white !important;
            border: 2px solid #ff6b6b !important;
        }
        .alert-card {
            padding: 20px;
            border-radius: 10px;
            min-height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
    </style>
    """, unsafe_allow_html=True)

SHEET_NAME = "מערכת הזמנות - קוד יהודה  "
WORKSHEET_INDEX = 0

TRANSLATIONS = {
    "en": {
        "title": "🎫 Ticket Agency Management System",
        "sidebar_header": "🎫 Ticket Agency",
        "refresh_data": "🔄 Refresh Data",
        "filters": "📊 Filters",
        "event_name": "🎭 Event Name",
        "date_range": "📅 Date Range",
        "source": "📍 Source",
        "alerts_dashboard": "### 🚨 Alerts Dashboard",
        "urgent_events": "events in < 48 hours with Status='New'",
        "no_urgent": "✅ No urgent events",
        "old_orders": "orders > 30 days old still 'New'",
        "no_old_orders": "✅ No old pending orders",
        "low_margin": "orders with < 10% profit margin",
        "margins_healthy": "✅ All margins healthy",
        "tab1": "🔥 Purchasing Center",
        "tab2": "💰 Profit Intelligence",
        "tab3": "📅 Operational View (Next 7 Days)",
        "tab4": "💾 Data Export",
        "tab5": "📈 Sales",
        "purchasing_header": "🔥 Purchasing Center",
        "purchasing_subtitle": "*View and manage orders with Status = 'New'*",
        "orders_grouped": "📊 Orders Grouped by Event & Category",
        "select_orders": "✅ Select Orders to Mark as Purchased",
        "mark_purchased": "🛒 Mark Selected as Purchased",
        "updating": "Updating Google Sheet...",
        "update_success": "Successfully updated",
        "orders_to_done": "order(s) to 'done!'",
        "select_warning": "Please select at least one order to update.",
        "orders_selected": "order(s) selected",
        "no_pending": "🎉 No pending orders! All orders are processed.",
        "no_orderd_col": "Could not find 'orderd' column in the data.",
        "profit_header": "💰 Profit Intelligence",
        "total_profit": "💵 Total Profit",
        "avg_margin": "📈 Average Margin",
        "highest_profit": "🏆 Highest Profit Event",
        "monthly_trend": "📈 Monthly Profit Trend",
        "profit_by_month": "Total Profit by Month",
        "month": "Month",
        "profit": "Profit ($)",
        "no_date_data": "No date data available for trend chart.",
        "top_10": "🏅 Top 10 Most Profitable Events",
        "top_10_title": "Top 10 Events by Profit",
        "no_event_data": "No event data available.",
        "no_event_col": "No event name column found.",
        "operational_header": "📅 Operational View (Next 7 Days)",
        "legend": "**Legend:** 🟢 Green = Done/Purchased | 🔴 Red = New | 🔵 Blue = Ordered",
        "no_events_7days": "No events scheduled in the next 7 days.",
        "date_not_found": "Date column not found or could not be parsed.",
        "export_header": "💾 Data Export",
        "full_data": "📋 Full Data View",
        "export_csv": "📥 Export to CSV",
        "showing_records": "Showing",
        "records": "records",
        "footer": "🎫 Ticket Agency Management System | Powered by Streamlit & Google Sheets",
        "no_data": "No data loaded. Please check your Google Sheet connection and credentials.",
        "select_col": "Select",
        "select_help": "Select to mark as purchased",
        "sheet_row": "Sheet Row",
        "sheet_row_help": "Original row number in Google Sheet",
        "total_qty": "Total Qty",
        "order_count": "Order Count",
        "language": "🌐 Language",
        "status": "📋 Status",
        "all_statuses": "All Statuses",
        "auto_update_btn": "🔄 Update Ordered Status",
        "auto_updated": "Updated",
        "orders": "orders",
        "no_orders_to_update": "No orders to update",
        "updated_orders_list": "Updated Orders",
        "order_num": "Order #",
        "updating": "Updating",
        "updating_orderd": "Updating to orderd",
        "updating_done": "Updating to done!",
        "and_more": "and more",
        "update_done_btn": "🟢 Update done! Status",
        "no_done_to_update": "No orders to mark as done!",
    },
    "he": {
        "title": "🎫 מערכת ניהול כרטיסים",
        "sidebar_header": "🎫 סוכנות כרטיסים",
        "refresh_data": "🔄 רענן נתונים",
        "filters": "📊 מסננים",
        "event_name": "🎭 שם אירוע",
        "date_range": "📅 טווח תאריכים",
        "source": "📍 מקור",
        "alerts_dashboard": "### 🚨 לוח התראות",
        "urgent_events": "אירועים ב-48 שעות הקרובות עם סטטוס 'חדש'",
        "no_urgent": "✅ אין אירועים דחופים",
        "old_orders": "הזמנות מעל 30 יום עדיין 'חדש'",
        "no_old_orders": "✅ אין הזמנות ישנות ממתינות",
        "low_margin": "הזמנות עם רווח מתחת ל-10%",
        "margins_healthy": "✅ כל הרווחים תקינים",
        "tab1": "🔥 מרכז רכישות",
        "tab2": "💰 ניתוח רווחיות",
        "tab3": "📅 תצוגה תפעולית (7 ימים הקרובים)",
        "tab4": "💾 ייצוא נתונים",
        "tab5": "📈 מכירות",
        "purchasing_header": "🔥 מרכז רכישות",
        "purchasing_subtitle": "*צפייה וניהול הזמנות עם סטטוס = 'חדש'*",
        "orders_grouped": "📊 הזמנות מקובצות לפי אירוע וקטגוריה",
        "select_orders": "✅ בחר הזמנות לסימון כנרכשו",
        "mark_purchased": "🛒 סמן נבחרים כנרכשו",
        "updating": "מעדכן את הגיליון...",
        "update_success": "עודכנו בהצלחה",
        "orders_to_done": "הזמנות ל-'בוצע!'",
        "select_warning": "נא לבחור לפחות הזמנה אחת לעדכון.",
        "orders_selected": "הזמנות נבחרו",
        "no_pending": "🎉 אין הזמנות ממתינות! כל ההזמנות טופלו.",
        "no_orderd_col": "לא נמצאה עמודת 'orderd' בנתונים.",
        "profit_header": "💰 ניתוח רווחיות",
        "total_profit": "💵 רווח כולל",
        "avg_margin": "📈 רווח ממוצע",
        "highest_profit": "🏆 אירוע הכי רווחי",
        "monthly_trend": "📈 מגמת רווח חודשית",
        "profit_by_month": "רווח כולל לפי חודש",
        "month": "חודש",
        "profit": "רווח ($)",
        "no_date_data": "אין נתוני תאריך זמינים לגרף.",
        "top_10": "🏅 10 האירועים הרווחיים ביותר",
        "top_10_title": "10 אירועים מובילים לפי רווח",
        "no_event_data": "אין נתוני אירועים זמינים.",
        "no_event_col": "לא נמצאה עמודת שם אירוע.",
        "operational_header": "📅 תצוגה תפעולית (7 ימים הקרובים)",
        "legend": "**מקרא:** 🟢 ירוק = בוצע/נרכש | 🔴 אדום = חדש | 🔵 כחול = הוזמן",
        "no_events_7days": "אין אירועים מתוכננים ב-7 הימים הקרובים.",
        "date_not_found": "עמודת תאריך לא נמצאה או לא ניתנת לפענוח.",
        "export_header": "💾 ייצוא נתונים",
        "full_data": "📋 תצוגת נתונים מלאה",
        "export_csv": "📥 ייצוא ל-CSV",
        "showing_records": "מציג",
        "records": "רשומות",
        "footer": "🎫 מערכת ניהול כרטיסים | מופעל על ידי Streamlit & Google Sheets",
        "no_data": "לא נטענו נתונים. אנא בדוק את החיבור ל-Google Sheet.",
        "select_col": "בחר",
        "select_help": "בחר לסימון כנרכש",
        "sheet_row": "שורה בגיליון",
        "sheet_row_help": "מספר השורה המקורי ב-Google Sheet",
        "total_qty": "כמות כוללת",
        "order_count": "מספר הזמנות",
        "language": "🌐 שפה",
        "status": "📋 סטטוס",
        "all_statuses": "כל הסטטוסים",
        "auto_update_btn": "🔄 עדכן סטטוס הוזמן",
        "auto_updated": "עודכנו",
        "orders": "הזמנות",
        "no_orders_to_update": "אין הזמנות לעדכון",
        "updated_orders_list": "הזמנות שעודכנו",
        "order_num": "הזמנה מס'",
        "updating": "מעדכן",
        "updating_orderd": "מעדכן ל-orderd",
        "updating_done": "מעדכן ל-done!",
        "and_more": "ועוד",
        "update_done_btn": "🟢 עדכן סטטוס done!",
        "no_done_to_update": "אין הזמנות לסמן כ-done!",
    }
}

def t(key):
    """Get translated text for current language."""
    lang = st.session_state.get('language', 'he')
    return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)

def normalize_order_number(order_num):
    """
    מנקה ומנרמל מספר הזמנה - מסיר כל תו שאינו אות או מספר.
    """
    if not order_num:
        return ""
    
    order_str = str(order_num)
    
    import re
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', order_str)
    
    cleaned = cleaned.upper()
    
    return cleaned

def get_gspread_client():
    """Create and return a gspread client using credentials from environment."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Try to get from Streamlit secrets first (if available)
    creds_json = None
    try:
        if hasattr(st, 'secrets') and 'GOOGLE_CREDENTIALS' in st.secrets:
            creds_json = st.secrets['GOOGLE_CREDENTIALS']
    except:
        pass
    
    # Fallback to environment variable
    if not creds_json:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS not found in environment. Please set it in Streamlit Cloud Secrets.")
    
    # Handle different input formats
    try:
        if isinstance(creds_json, dict):
            # Already a dictionary (from Streamlit secrets)
            creds_dict = creds_json
        elif isinstance(creds_json, str):
            # Parse JSON string
            creds_dict = json.loads(creds_json)
        else:
            # Try to convert to dict
            creds_dict = dict(creds_json)
        
        # Ensure private_key is properly formatted (handle escaped newlines)
        if 'private_key' in creds_dict and isinstance(creds_dict['private_key'], str):
            private_key = creds_dict['private_key']
            original_key = private_key  # Keep original for debugging
            
            # Step 1: Handle escaped newlines - convert \n (two characters: backslash + n) to actual newline
            # This is critical - JSON strings have "\\n" which needs to become actual "\n"
            # Handle all variations: \n, \\n, \\\n, etc.
            import re
            # First, handle multiple backslashes (2+) followed by 'n' - do this BEFORE simple replace
            # This handles cases like: \\n, \\\n, \\\\n, etc. -> all become actual newline
            private_key = re.sub(r'\\{2,}n', '\n', private_key)
            
            # Then handle single escaped newline (\n -> actual newline)
            # This handles the standard case where JSON has "\n" as a string
            if '\\n' in private_key:
                private_key = private_key.replace('\\n', '\n')
            
            # Step 2: Handle case where newlines might have been converted to spaces
            # Sometimes when loading from Streamlit Secrets, newlines become spaces
            # Check if BEGIN is followed by space instead of newline
            if '-----BEGIN PRIVATE KEY----- ' in private_key:
                private_key = private_key.replace('-----BEGIN PRIVATE KEY----- ', '-----BEGIN PRIVATE KEY-----\n')
            
            # Step 3: Ensure proper format - the key should have newlines
            # Verify BEGIN and END markers exist
            if '-----BEGIN PRIVATE KEY-----' not in private_key:
                raise ValueError(
                    "private_key לא מכיל '-----BEGIN PRIVATE KEY-----'.\n"
                    f"המפתח מתחיל ב: {private_key[:100] if len(private_key) > 100 else private_key}..."
                )
            
            if '-----END PRIVATE KEY-----' not in private_key:
                raise ValueError(
                    "private_key לא מכיל '-----END PRIVATE KEY-----'.\n"
                    f"המפתח מסתיים ב: ...{private_key[-100:] if len(private_key) > 100 else private_key}"
                )
            
            # Step 4: Ensure there are actual newlines in the key
            # The key MUST have newlines - if not, try to fix it
            if '\n' not in private_key:
                # Try to reconstruct with newlines
                # Split by BEGIN and END markers
                begin_idx = private_key.find('-----BEGIN PRIVATE KEY-----')
                end_idx = private_key.find('-----END PRIVATE KEY-----')
                
                if begin_idx >= 0 and end_idx > begin_idx:
                    begin_marker = '-----BEGIN PRIVATE KEY-----'
                    end_marker = '-----END PRIVATE KEY-----'
                    key_content = private_key[begin_idx + len(begin_marker):end_idx].strip()
                    # Remove any spaces and reconstruct with newlines every 64 chars (standard PEM format)
                    key_content = key_content.replace(' ', '')
                    # Reconstruct with newlines every 64 characters
                    key_lines = [key_content[i:i+64] for i in range(0, len(key_content), 64)]
                    private_key = f'{begin_marker}\n' + '\n'.join(key_lines) + f'\n{end_marker}\n'
                else:
                    raise ValueError(
                        "private_key לא מכיל newlines אמיתיים ולא ניתן לתקן אוטומטית.\n"
                        "ודא שה-private_key ב-JSON כולל \\n (escaped newlines)."
                    )
            
            # Step 5: Additional validation
            if len(private_key) < 100:
                raise ValueError(
                    "private_key נראה קצר מדי - ודא שהעתקת את כל המפתח מה-JSON file."
                )
            
            # Step 6: Final format check - ensure newlines are present after BEGIN and before END
            if not private_key.startswith('-----BEGIN PRIVATE KEY-----\n'):
                # Try to fix if missing newline after BEGIN
                private_key = private_key.replace('-----BEGIN PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----\n', 1)
            
            if not private_key.rstrip().endswith('\n-----END PRIVATE KEY-----'):
                # Try to fix if missing newline before END
                private_key = private_key.replace('-----END PRIVATE KEY-----', '\n-----END PRIVATE KEY-----', 1)
            
            creds_dict['private_key'] = private_key
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in GOOGLE_CREDENTIALS: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error parsing GOOGLE_CREDENTIALS: {str(e)}")
    
    # Validate required fields
    required_fields = ['type', 'project_id', 'private_key', 'client_email']
    missing_fields = [f for f in required_fields if f not in creds_dict]
    if missing_fields:
        raise ValueError(f"Missing required fields in GOOGLE_CREDENTIALS: {', '.join(missing_fields)}")
    
    try:
        # Create a copy to avoid modifying the original
        creds_dict_copy = creds_dict.copy()
        
        # Final validation and fix of private_key before passing to oauth2client
        if 'private_key' in creds_dict_copy:
            pk = creds_dict_copy['private_key']
            
            # Ensure it's a string
            if not isinstance(pk, str):
                raise ValueError(f"private_key צריך להיות string, אבל קיבלנו: {type(pk)}")
            
            # CRITICAL FIX: The private_key might be corrupted or incomplete
            # Let's ensure it's properly formatted
            
            # 1. Remove any leading/trailing whitespace
            pk = pk.strip()
            
            # 2. Ensure BEGIN marker is at the start
            if not pk.startswith('-----BEGIN'):
                begin_idx = pk.find('-----BEGIN')
                if begin_idx > 0:
                    pk = pk[begin_idx:]
            
            # 3. Ensure END marker is at the end
            if not pk.rstrip().endswith('-----END PRIVATE KEY-----'):
                end_idx = pk.rfind('-----END PRIVATE KEY-----')
                if end_idx > 0:
                    pk = pk[:end_idx + len('-----END PRIVATE KEY-----')]
            
            # 4. Verify the key is complete - check length (should be ~1600-1700 chars for RSA key)
            if len(pk) < 1000:
                raise ValueError(
                    f"private_key נראה קצר מדי ({len(pk)} תווים). המפתח צריך להיות ~1600 תווים.\n"
                    "המפתח כנראה נחתך או לא הועתק במלואו."
                )
            
            # 5. Verify BEGIN and END markers
            if '-----BEGIN PRIVATE KEY-----' not in pk:
                raise ValueError("private_key לא מכיל '-----BEGIN PRIVATE KEY-----'")
            
            if '-----END PRIVATE KEY-----' not in pk:
                raise ValueError("private_key לא מכיל '-----END PRIVATE KEY-----'")
            
            # 6. Extract and validate the key content
            begin_marker = '-----BEGIN PRIVATE KEY-----'
            end_marker = '-----END PRIVATE KEY-----'
            begin_idx = pk.find(begin_marker)
            end_idx = pk.find(end_marker)
            
            if begin_idx < 0 or end_idx < 0 or end_idx <= begin_idx:
                raise ValueError("private_key לא בפורמט תקין - בעיה במיקום BEGIN/END markers")
            
            # Extract the actual key content (between markers)
            key_content = pk[begin_idx + len(begin_marker):end_idx].strip()
            
            # Remove all whitespace and newlines to get pure base64
            key_content_clean = key_content.replace('\n', '').replace(' ', '').replace('\r', '')
            
            # Validate key content length (RSA private key should be ~1600-1700 base64 chars)
            if len(key_content_clean) < 1000:
                raise ValueError(
                    f"תוכן המפתח קצר מדי ({len(key_content_clean)} תווים). המפתח כנראה לא שלם.\n"
                    "ודא שהעתקת את כל המפתח מה-JSON file."
                )
            
            # Reconstruct the key with proper PEM format
            # PEM format: lines of 64 characters
            key_lines = [key_content_clean[i:i+64] for i in range(0, len(key_content_clean), 64)]
            pk = f'{begin_marker}\n' + '\n'.join(key_lines) + f'\n{end_marker}\n'
            
            # Update the dict with the fixed key
            creds_dict_copy['private_key'] = pk
        
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict_copy, scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        # Provide specific error messages for common issues
        if "seekable bit stream" in error_msg.lower() or "unsupportedsubstrateerror" in error_msg.lower() or "substrateunderrun" in error_msg.lower():
            # Check if we can see the private_key format
            private_key_preview = ""
            private_key_length = 0
            if 'private_key' in creds_dict:
                pk = str(creds_dict['private_key'])
                private_key_length = len(pk)
                if len(pk) > 0:
                    preview = pk[:100] + "..." if len(pk) > 100 else pk
                    private_key_preview = f"\n**תצוגה מקדימה של private_key:** {preview}\n**אורך המפתח:** {private_key_length} תווים"
            
            # Determine the specific issue
            if "substrateunderrun" in error_msg.lower() or "short substrate" in error_msg.lower():
                issue_desc = "ה-private_key לא שלם או נחתך - המפתח קצר מדי או פגום."
                solution_extra = "\n**חשוב במיוחד:** ודא שהעתקת את כל המפתח במלואו - המפתח צריך להיות ~1600 תווים."
            else:
                issue_desc = "ה-private_key לא בפורמט הנכון."
                solution_extra = ""
            
            detailed_msg = (
                f"❌ **שגיאה בפורמט ה-private_key ב-GOOGLE_CREDENTIALS**\n\n"
                f"**הבעיה:** {issue_desc}\n\n"
                f"**פתרון:**\n"
                f"1. פתח את הקובץ JSON המקורי מה-Google Cloud Console\n"
                f"2. **העתק את כל התוכן** של הקובץ (כולל ה-private_key המלא)\n"
                f"3. ב-Streamlit Cloud Secrets:\n"
                f"   - לך ל-Settings > Secrets\n"
                f"   - מחק את GOOGLE_CREDENTIALS הקיים\n"
                f"   - הוסף מחדש עם כל ה-JSON המלא\n"
                f"4. **ודא שה-private_key כולל `\\n` (escaped newlines) בתוך המחרוזת**\n"
                f"5. שמור והפעל מחדש את האפליקציה\n\n"
                f"{solution_extra}\n\n"
                f"{private_key_preview}\n\n"
                f"**סוג שגיאה:** {error_type}\n"
                f"**פרטים:** {error_msg}"
            )
            raise ValueError(detailed_msg)
        elif "invalid_grant" in error_msg.lower():
            detailed_msg = (
                f"אימות נכשל - האימות ל-Google API נכשל.\n"
                f"בדוק שהחשבון השירות פעיל ושהמפתח לא פג תוקף.\n"
                f"סוג שגיאה: {error_type}\n"
                f"פרטים: {error_msg}"
            )
            raise ValueError(detailed_msg)
        elif "invalid" in error_msg.lower():
            detailed_msg = (
                f"Credentials לא תקינים.\n"
                f"בדוק את GOOGLE_CREDENTIALS ב-Streamlit Cloud Secrets.\n"
                f"סוג שגיאה: {error_type}\n"
                f"פרטים: {error_msg}"
            )
            raise ValueError(detailed_msg)
        else:
            # Generic error with full details
            detailed_msg = (
                f"שגיאה בחיבור ל-Google API.\n"
                f"סוג שגיאה: {error_type}\n"
                f"פרטים: {error_msg}"
            )
            raise ValueError(detailed_msg)

def generate_order_number(df):
    """Generate new order number based on existing max"""
    try:
        if 'Order number' in df.columns:
            existing_orders = pd.to_numeric(df['Order number'], errors='coerce').dropna()
            if len(existing_orders) > 0:
                max_order = int(existing_orders.max())
                return str(max_order + 1)
        return "1"
    except:
        return str(int(datetime.now().timestamp()) % 100000)

def add_new_order_to_sheet(order_data):
    """Add a new order row to Google Sheets - using dynamic column lookup"""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        headers = worksheet.row_values(1)
        headers_lower = [h.lower().strip() for h in headers]
        
        new_row = [''] * len(headers)
        
        field_to_headers = {
            'order date': ['order date', 'order_date', 'orderdate'],
            'orderd': ['orderd', 'ordered', 'status', 'Status'],
            'source': ['source', 'Source'],
            'Order number': ['order number', 'order_number', 'ordernumber'],
            'docket number': ['docket number', 'docket_number', 'docketnumber', 'docket'],
            'event name': ['event name', 'event_name', 'eventname'],
            'Date of the event': ['date of the event', 'date_of_the_event', 'event date', 'eventdate'],
            'Category / Section': ['category / section', 'category/section', 'category', 'section'],
            'Qty': ['qty', 'quantity', 'כמות'],
            'Price sold': ['price sold', 'price_sold', 'pricesold', 'price'],
            'TOTAL': ['total'],
        }
        
        for field, possible_headers in field_to_headers.items():
            if field in order_data:
                col_idx = None
                for possible in possible_headers:
                    if possible.lower() in headers_lower:
                        col_idx = headers_lower.index(possible.lower())
                        break
                if col_idx is not None and col_idx < len(new_row):
                    new_row[col_idx] = order_data[field]
        
        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
        
        return True, "הזמנה חדשה נוספה בהצלחה!"
    except Exception as e:
        return False, f"שגיאה בהוספת הזמנה: {str(e)}"

def get_unique_sources_list(df):
    """Get list of unique sources from dataframe"""
    if 'source' in df.columns:
        sources = df['source'].dropna().unique().tolist()
        return sorted([s for s in sources if s and str(s).strip()])
    return []

def get_unique_events_dict(df):
    """Get list of unique events with their dates"""
    events = {}
    if 'event name' in df.columns:
        for idx, row in df.iterrows():
            event = row.get('event name', '')
            date = row.get('Date of the event', '')
            if event and str(event).strip():
                events[str(event).strip()] = str(date).strip() if date else ''
    return events

def add_missing_orders_simple():
    """
    גרסה פשוטה - מוסיף הזמנות חסרות בלחיצה אחת.
    עם נרמול מספרי הזמנה למניעת כפילויות.
    """
    OLD_SHEET_ID = "11MGLk4Gs20-olgRW-_z6GX_CsQEMHgcZUWiENnDeG0g"
    NEW_SHEET_NAME = "מערכת הזמנות - קוד יהודה  "
    
    st.subheader("➕ הוסף הזמנות חסרות מגיליון ישן")
    
    try:
        if st.button("🔍 מצא הזמנות חסרות", key="find_missing"):
            with st.spinner("בודק..."):
                client = get_gspread_client()
                
                st.info("📖 קורא גיליון ישן...")
                old_sheet = client.open_by_key(OLD_SHEET_ID).get_worksheet(0)
                old_data = old_sheet.get_all_values()
                old_headers = old_data[0]
                
                st.info("📖 קורא גיליון חדש...")
                new_sheet = client.open(NEW_SHEET_NAME).get_worksheet(0)
                new_data = new_sheet.get_all_values()
                new_headers = new_data[0]
                
                old_order_col = old_headers.index('Order number')
                new_order_col = new_headers.index('Order number')
                
                st.info(f"🔍 עמודת Order number: גיליון ישן={old_order_col}, גיליון חדש={new_order_col}")
                
                new_order_numbers_normalized = set()
                new_order_numbers_original = {}
                
                for row in new_data[1:]:
                    if len(row) > new_order_col:
                        original = row[new_order_col].strip()
                        if original:
                            normalized = normalize_order_number(original)
                            new_order_numbers_normalized.add(normalized)
                            new_order_numbers_original[normalized] = original
                
                st.success(f"✅ גיליון חדש: {len(new_order_numbers_normalized)} הזמנות ייחודיות")
                
                st.info("🔍 מחפש הזמנות חסרות (עם נרמול)...")
                missing_orders = []
                skipped_duplicates = []
                
                for row in old_data[1:]:
                    if len(row) > old_order_col:
                        original_order = row[old_order_col].strip()
                        
                        if original_order:
                            normalized_order = normalize_order_number(original_order)
                            
                            if normalized_order not in new_order_numbers_normalized:
                                missing_orders.append(row)
                            else:
                                matching_original = new_order_numbers_original.get(normalized_order, '?')
                                skipped_duplicates.append({
                                    'old_original': original_order,
                                    'old_normalized': normalized_order,
                                    'new_original': matching_original
                                })
                
                st.session_state.missing_orders = missing_orders
                st.session_state.skipped_duplicates = skipped_duplicates
                st.session_state.new_sheet_obj = new_sheet
                st.session_state.new_headers = new_headers
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("✅ הזמנות חדשות למהוספה", len(missing_orders))
                with col2:
                    st.metric("⏭️ דילגתי על כפילויות", len(skipped_duplicates))
                
                if skipped_duplicates:
                    with st.expander(f"⚠️ דילגתי על {len(skipped_duplicates)} כפילויות (לא יתווספו)", expanded=False):
                        st.caption("הזמנות אלה כבר קיימות בגיליון החדש (אחרי נרמול):")
                        for dup in skipped_duplicates[:20]:
                            st.write(f"- **{dup['old_original']}** (ישן) = **{dup['new_original']}** (חדש) → מנורמל: `{dup['old_normalized']}`")
                        if len(skipped_duplicates) > 20:
                            st.caption(f"... ועוד {len(skipped_duplicates) - 20}")
                
                if not missing_orders:
                    st.success("✅ אין הזמנות חדשות להוספה - הכל כבר קיים!")
        
        if 'missing_orders' in st.session_state and st.session_state.missing_orders:
            missing = st.session_state.missing_orders
            
            st.success(f"🎯 **{len(missing)} הזמנות חדשות** מוכנות להוספה")
            
            with st.expander(f"📋 דוגמאות (10 ראשונות מתוך {len(missing)})"):
                for row in missing[:10]:
                    try:
                        order_num = row[3] if len(row) > 3 else '-'
                        event_name = row[5] if len(row) > 5 else '-'
                        event_date = row[6] if len(row) > 6 else '-'
                        st.write(f"**Order {order_num}:** {event_name} | {event_date}")
                    except:
                        pass
            
            st.warning(f"""
            ⚠️ **לפני הוספה:**
            - {len(missing)} שורות יתווספו
            - בדיקת כפילויות בוצעה ✅
            - הפעולה בלתי הפיכה
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button(f"✅ הוסף {len(missing)} הזמנות", key="execute_add", type="primary"):
                    progress = st.progress(0)
                    status = st.empty()
                    
                    try:
                        new_sheet = st.session_state.new_sheet_obj
                        new_headers = st.session_state.new_headers
                        num_cols = len(new_headers)
                        
                        status.text("➕ מוסיף שורות לגיליון...")
                        
                        batch_size = 50
                        total = len(missing)
                        
                        for i in range(0, total, batch_size):
                            batch = missing[i:i+batch_size]
                            
                            formatted = []
                            for row in batch:
                                if len(row) < num_cols:
                                    formatted.append(row + [''] * (num_cols - len(row)))
                                elif len(row) > num_cols:
                                    formatted.append(row[:num_cols])
                                else:
                                    formatted.append(row)
                            
                            new_sheet.append_rows(formatted)
                            
                            progress.progress(min((i + batch_size) / total, 1.0))
                            status.text(f"➕ נוספו {min(i + batch_size, total)} מתוך {total}")
                            time.sleep(2)
                        
                        st.success(f"✅ הצלחה! נוספו **{total}** הזמנות לגיליון!")
                        st.balloons()
                        
                        if 'migration_history' not in st.session_state:
                            st.session_state.migration_history = []
                        
                        st.session_state.migration_history.append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'action': 'הוספת הזמנות חסרות',
                            'count': total,
                            'skipped': len(st.session_state.get('skipped_duplicates', []))
                        })
                        
                        del st.session_state.missing_orders
                        if 'skipped_duplicates' in st.session_state:
                            del st.session_state.skipped_duplicates
                        del st.session_state.new_sheet_obj
                        del st.session_state.new_headers
                        
                        time.sleep(2)
                        st.rerun()
                    
                    except Exception as e:
                        st.error(f"❌ שגיאה בהוספה: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
            
            with col2:
                if st.button("❌ ביטול", key="cancel_add2"):
                    del st.session_state.missing_orders
                    if 'skipped_duplicates' in st.session_state:
                        del st.session_state.skipped_duplicates
                    st.rerun()
    
    except Exception as e:
        st.error(f"❌ שגיאה: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

def parse_date_smart(date_str, event_name=None, date_hints=None):
    """Smart date parser that handles multiple formats."""
    if pd.isna(date_str) or date_str == '' or date_str is None:
        return None
    
    date_str = str(date_str).strip()
    
    formats = [
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y/%m/%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    if date_hints and event_name and event_name in date_hints:
        return date_hints[event_name]
    
    return None

def clean_numeric(value):
    """Clean numeric values by removing currency symbols and converting to float."""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    
    value_str = str(value)
    cleaned = re.sub(r'[^\d.\-]', '', value_str)
    
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

@st.cache_data(ttl=3600)
def get_exchange_rates():
    """Fetch real-time exchange rates to EUR from free API"""
    import urllib.request
    import json
    
    try:
        url = "https://api.exchangerate-api.com/v4/latest/EUR"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            rates = data.get('rates', {})
            gbp_to_eur = 1 / rates.get('GBP', 0.87) if rates.get('GBP') else 1.15
            usd_to_eur = 1 / rates.get('USD', 1.08) if rates.get('USD') else 0.93
            return {'GBP': gbp_to_eur, 'USD': usd_to_eur}
    except Exception as e:
        return {'GBP': 1.18, 'USD': 0.93}

def convert_to_euro(value, rates=None):
    """המר כל מטבע לאירו עם שערים אמיתיים"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    
    if rates is None:
        rates = get_exchange_rates()
    
    value_str = str(value).strip()
    
    if '€' in value_str:
        cleaned = re.sub(r'[^\d.\-]', '', value_str)
        return float(cleaned) if cleaned else 0.0
    elif '£' in value_str:
        cleaned = re.sub(r'[^\d.\-]', '', value_str)
        return (float(cleaned) if cleaned else 0.0) * rates['GBP']
    elif '$' in value_str:
        cleaned = re.sub(r'[^\d.\-]', '', value_str)
        return (float(cleaned) if cleaned else 0.0) * rates['USD']
    else:
        cleaned = re.sub(r'[^\d.\-]', '', value_str)
        return float(cleaned) if cleaned else 0.0

@st.cache_data(ttl=300)
def load_data_from_sheet():
    """Load data from Google Sheet with caching."""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        data = worksheet.get_all_values()
        
        if len(data) < 2:
            # Clear any previous error state on successful connection
            if 'sheet_error' in st.session_state:
                del st.session_state.sheet_error
            return pd.DataFrame()
        
        headers = [str(h).strip() for h in data[0]]
        rows = data[1:]
        
        df = pd.DataFrame(rows, columns=headers)
        
        df['row_index'] = range(2, len(df) + 2)
        
        df.columns = [col.strip() for col in df.columns]
        
        date_hints = {}
        if 'Date of the event' in df.columns and 'event name' in df.columns:
            for _, row in df.iterrows():
                event = row.get('event name', '')
                date_val = row.get('Date of the event', '')
                parsed = parse_date_smart(date_val)
                if parsed and event and event not in date_hints:
                    date_hints[event] = parsed
        
        if 'Date of the event' in df.columns:
            df['parsed_date'] = df.apply(
                lambda row: parse_date_smart(
                    row.get('Date of the event', ''),
                    row.get('event name', ''),
                    date_hints
                ),
                axis=1
            )
        
        if 'TOTAL' in df.columns:
            df['TOTAL_clean'] = df['TOTAL'].apply(convert_to_euro)
        else:
            df['TOTAL_clean'] = 0.0
            
        if 'SUPP PRICE' in df.columns:
            df['SUPP_PRICE_clean'] = df['SUPP PRICE'].apply(convert_to_euro)
        else:
            df['SUPP_PRICE_clean'] = 0.0
        
        if 'source' in df.columns:
            df['commission_rate'] = df['source'].apply(get_commission_rate)
            df['commission_amount'] = df['TOTAL_clean'] * df['commission_rate']
            df['revenue_net'] = df['TOTAL_clean'] - df['commission_amount']
        else:
            df['commission_rate'] = 0.0
            df['commission_amount'] = 0.0
            df['revenue_net'] = df['TOTAL_clean']
        
        df['profit'] = df['revenue_net'] - df['SUPP_PRICE_clean']
        df['profit_before_commission'] = df['TOTAL_clean'] - df['SUPP_PRICE_clean']
        df['margin_pct'] = df.apply(
            lambda row: (row['profit'] / row['revenue_net'] * 100) if row['revenue_net'] > 0 else 0,
            axis=1
        )
        
        status_col = 'orderd' if 'orderd' in df.columns else ('Status' if 'Status' in df.columns else None)
        if status_col:
            hebrew_to_english_status = {
                '🔴 חדש': 'new',
                'חדש': 'new',
                '📦 הוזמן': 'orderd',
                'הוזמן': 'orderd',
                '✅ הושלם': 'done',
                'הושלם': 'done',
                '🟠 נשלח ולא שולם': 'sent - not paid',
                'נשלח ולא שולם': 'sent - not paid',
                '💚 נשלח ושולם': 'sent - paid',
                'נשלח ושולם': 'sent - paid',
            }
            df[status_col] = df[status_col].apply(
                lambda x: hebrew_to_english_status.get(str(x).strip(), x) if pd.notna(x) else x
            )
        
        # Clear any previous error state on successful load
        if 'sheet_error' in st.session_state:
            del st.session_state.sheet_error
        
        return df
        
    except ValueError as e:
        error_msg = ""
        if "GOOGLE_CREDENTIALS" in str(e):
            error_msg = "❌ **שגיאת אימות:** משתנה הסביבה GOOGLE_CREDENTIALS לא נמצא. אנא הגדר אותו ב-Streamlit Cloud Secrets."
        else:
            error_msg = f"❌ **שגיאת אימות:** {str(e)}"
        st.session_state.sheet_error = error_msg
        st.error(error_msg)
        # Clear cache to retry on next call
        load_data_from_sheet.clear()
        return pd.DataFrame()
    except gspread.exceptions.SpreadsheetNotFound:
        error_msg = f"❌ **אין גישה לגוגל שיטס:** לא נמצא גיליון בשם '{SHEET_NAME}'. אנא ודא שהגיליון קיים ושם חשבון השירות יש לו גישה אליו."
        st.session_state.sheet_error = error_msg
        st.error(error_msg)
        load_data_from_sheet.clear()
        return pd.DataFrame()
    except gspread.exceptions.APIError as e:
        error_msg = str(e)
        if "PERMISSION_DENIED" in error_msg or "403" in error_msg:
            error_msg = f"❌ **אין גישה לגוגל שיטס:** אין הרשאות לגיליון '{SHEET_NAME}'. אנא ודא שחשבון השירות של Google יש לו הרשאות לעריכה בגיליון."
        elif "401" in error_msg or "UNAUTHENTICATED" in error_msg:
            error_msg = f"❌ **אין גישה לגוגל שיטס:** האימות נכשל. אנא בדוק את GOOGLE_CREDENTIALS ב-Streamlit Cloud Secrets."
        else:
            error_msg = f"❌ **אין גישה לגוגל שיטס:** {error_msg}"
        st.session_state.sheet_error = error_msg
        st.error(error_msg)
        load_data_from_sheet.clear()
        return pd.DataFrame()
    except Exception as e:
        error_type = type(e).__name__
        error_str = str(e)
        
        # Create detailed error message
        error_msg = f"❌ **שגיאה בטעינת נתונים ({error_type}):** {error_str}"
        
        # Add more specific information based on error type
        if "seekable bit stream" in error_str.lower():
            error_msg += "\n\n💡 **פתרון אפשרי:** בעיה בפורמט ה-JSON של GOOGLE_CREDENTIALS. ודא שהמשתנה הוא JSON תקין."
        elif "invalid_grant" in error_str.lower():
            error_msg += "\n\n💡 **פתרון אפשרי:** האימות נכשל. בדוק שהחשבון השירות פעיל ושהמפתח לא פג תוקף."
        elif "timeout" in error_str.lower() or "connection" in error_str.lower():
            error_msg += "\n\n💡 **פתרון אפשרי:** בעיית חיבור ל-Google API. נסה שוב בעוד כמה רגעים."
        
        st.session_state.sheet_error = error_msg
        st.error(error_msg)
        
        # Always show detailed traceback
        import traceback
        with st.expander("🔍 פרטי שגיאה מפורטים (לפיתוח)"):
            st.code(traceback.format_exc())
            st.write("**סוג שגיאה:**", error_type)
            st.write("**הודעת שגיאה:**", error_str)
        
        load_data_from_sheet.clear()
        return pd.DataFrame()

def col_number_to_letter(col_num):
    """Convert column number (1-based) to Excel-style letter (A, B, ..., Z, AA, AB, ...)"""
    result = ""
    while col_num > 0:
        col_num -= 1
        result = chr(65 + (col_num % 26)) + result
        col_num //= 26
    return result

from difflib import SequenceMatcher

def normalize_team_name(name):
    """נרמל שם קבוצה לצורך השוואה - שומר על שמות הקבוצות המקוריים"""
    import re
    if not name or pd.isna(name):
        return ""
    name = str(name).strip()
    
    remove_terms = [
        r'\b(cf|fc|sc|ac|as|a\.?f\.?c\.?|u\.?d\.?|f\.c\.)\b',
        r'\b(football|club)\b',
    ]
    
    for term in remove_terms:
        name = re.sub(term, ' ', name, flags=re.IGNORECASE)
    
    name = re.sub(r'[^\w\s\-]', '', name)
    name = ' '.join(name.split())
    return name.strip()

def extract_teams(event_name):
    """חלץ שני קבוצות משם אירוע"""
    import re
    if not event_name or pd.isna(event_name):
        return (normalize_team_name(str(event_name)),)
    
    event_name = str(event_name)
    separators = [' vs ', ' vs. ', ' v.s. ', ' v.s ', ' - ', ' – ', ' v ']
    
    for sep in separators:
        if sep.lower() in event_name.lower():
            parts = re.split(re.escape(sep), event_name, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                team1 = normalize_team_name(parts[0])
                team2 = normalize_team_name(parts[1])
                return tuple(sorted([team1, team2]))
    
    return (normalize_team_name(event_name),)

def similarity_score(str1, str2):
    """חישוב דמיון בין 2 מחרוזות (0-1)"""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1, str2).ratio()

def are_same_event(event1, event2, date1, date2):
    """בדוק אם 2 אירועים זהים (שם דומה + תאריך קרוב)"""
    teams1 = extract_teams(event1)
    teams2 = extract_teams(event2)
    
    if len(teams1) == len(teams2) == 2:
        similarity = (similarity_score(teams1[0], teams2[0]) + 
                     similarity_score(teams1[1], teams2[1])) / 2
    elif len(teams1) == 1 and len(teams2) == 1:
        similarity = similarity_score(teams1[0], teams2[0])
    else:
        all_teams1 = ' '.join(teams1)
        all_teams2 = ' '.join(teams2)
        similarity = similarity_score(all_teams1, all_teams2)
    
    if similarity < 0.75:
        return False
    
    try:
        if isinstance(date1, str):
            date1 = pd.to_datetime(date1, errors='coerce')
        if isinstance(date2, str):
            date2 = pd.to_datetime(date2, errors='coerce')
        
        if pd.isna(date1) or pd.isna(date2):
            return similarity >= 0.90
        
        if hasattr(date1, 'date'):
            d1 = date1.date() if hasattr(date1.date, '__call__') else date1.date
        else:
            d1 = date1
        if hasattr(date2, 'date'):
            d2 = date2.date() if hasattr(date2.date, '__call__') else date2.date
        else:
            d2 = date2
            
        date_diff = abs((d1 - d2).days) if hasattr(d1 - d2, 'days') else 999
        
        if date_diff <= 3:
            return True
    except:
        return similarity >= 0.90
    
    return False

def normalize_event_name(name):
    """נרמל שם אירוע להשוואה - הסר vs, מקפים, סיומות קבוצות (לתאימות אחורה)"""
    import re
    if not name or pd.isna(name):
        return ""
    name = str(name)
    name = re.sub(r'\s+(vs\.?|v\.?s\.?|VS\.?|-|–)\s+', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\b(CF|FC|SC|AC|AS|United|City|Real|Atletico|Athletic)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip().lower()

def has_supplier_data(row):
    """בודק אם להזמנה יש נתוני ספק"""
    supp_price = parse_supp_price(row.get('SUPP PRICE', ''))
    supp_name = str(row.get('Supplier NAME', '')).strip()
    supp_order = str(row.get('SUPP order number', '')).strip() if 'SUPP order number' in row.index else ''
    if supp_order == '':
        for col in row.index:
            if 'supp' in col.lower() and 'order' in col.lower():
                supp_order = str(row.get(col, '')).strip()
                break
    return supp_price > 0 or supp_name != '' or supp_order != ''

def get_category_color(category):
    """החזר אימוג'י צבעוני בהתאם לקטגוריה"""
    if not category or pd.isna(category):
        return '🟪'
    cat_upper = str(category).upper()
    if 'CAT 1' in cat_upper or 'CAT 2' in cat_upper:
        return '🟦'
    elif 'CAT 3' in cat_upper or 'CAT 4' in cat_upper:
        return '🟨'
    elif 'PREMIUM' in cat_upper or 'VIP' in cat_upper:
        return '🟩'
    elif 'LONGSIDE' in cat_upper or 'SHORTSIDE' in cat_upper or 'TIER' in cat_upper:
        return '🟥'
    else:
        return '🟪'

def display_category_summary(orders_df, key_prefix=""):
    """הצג סיכום קטגוריות עם פרוגרס בארים"""
    if orders_df.empty:
        return
    
    cat_col = 'Category / Section' if 'Category / Section' in orders_df.columns else 'Category'
    if cat_col not in orders_df.columns:
        return
    
    orders_df = orders_df.copy()
    orders_df['Qty_num'] = pd.to_numeric(orders_df.get('Qty', 0), errors='coerce').fillna(0)
    orders_df['TOTAL_num'] = orders_df.apply(lambda r: clean_numeric(r.get('TOTAL', 0)), axis=1)
    
    orders_df[cat_col] = orders_df[cat_col].fillna('לא צוין').replace('', 'לא צוין')
    
    cat_summary = orders_df.groupby(cat_col).agg({
        'Qty_num': 'sum',
        'TOTAL_num': 'sum'
    }).reset_index()
    cat_summary.columns = ['category', 'qty', 'revenue']
    cat_summary = cat_summary.sort_values('qty', ascending=False)
    
    total_qty = cat_summary['qty'].sum()
    total_revenue = cat_summary['revenue'].sum()
    num_categories = len(cat_summary)
    
    if total_qty == 0:
        return
    
    with st.expander(f"📊 סיכום קטגוריות ({int(total_qty)} כרטיסים)", expanded=False):
        for _, row in cat_summary.iterrows():
            cat_name = row['category']
            qty = int(row['qty'])
            revenue = row['revenue']
            pct = (qty / total_qty * 100) if total_qty > 0 else 0
            rev_pct = (revenue / total_revenue * 100) if total_revenue > 0 else 0
            
            color_emoji = get_category_color(cat_name)
            
            col1, col2, col3 = st.columns([3, 5, 2])
            with col1:
                st.markdown(f"**{color_emoji} {cat_name}**")
            with col2:
                st.progress(min(pct / 100, 1.0))
            with col3:
                st.markdown(f"**{qty}** ({pct:.0f}%)")
        
        st.markdown("---")
        
        st.markdown(f"📦 **סה\"כ:** {int(total_qty)} כרטיסים | {num_categories} קטגוריות שונות")
        
        st.markdown("**💰 סיכום כספי לפי קטגוריה:**")
        revenue_parts = []
        for _, row in cat_summary.iterrows():
            rev_pct = (row['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
            revenue_parts.append(f"• {row['category']}: €{row['revenue']:,.0f} ({rev_pct:.0f}%)")
        st.markdown("\n".join(revenue_parts))

def group_orders_by_event(df):
    """קבץ הזמנות לפי אירוע עם איחוד חכם (fuzzy matching)"""
    if df.empty:
        return {}
    
    df = df.copy()
    df['has_supplier'] = df.apply(has_supplier_data, axis=1)
    
    event_groups = []
    assigned = set()
    
    rows_list = list(df.iterrows())
    
    for i, (idx1, row1) in enumerate(rows_list):
        if idx1 in assigned:
            continue
        
        group = [idx1]
        assigned.add(idx1)
        
        event1 = row1.get('event name', '')
        date1 = row1.get('parsed_date', row1.get('Date of the event', ''))
        
        for j, (idx2, row2) in enumerate(rows_list):
            if idx2 in assigned or idx2 == idx1:
                continue
            
            event2 = row2.get('event name', '')
            date2 = row2.get('parsed_date', row2.get('Date of the event', ''))
            
            if are_same_event(event1, event2, date1, date2):
                group.append(idx2)
                assigned.add(idx2)
        
        event_groups.append(group)
    
    grouped = {}
    for group_idx, indices in enumerate(event_groups):
        group_rows = df.loc[indices]
        
        event_names = group_rows['event name'].value_counts()
        best_event_name = event_names.index[0] if len(event_names) > 0 else 'Unknown'
        
        if 'parsed_date' in group_rows.columns:
            dates = group_rows['parsed_date'].dropna()
            event_date = dates.min() if len(dates) > 0 else group_rows['Date of the event'].iloc[0]
        else:
            event_date = group_rows['Date of the event'].iloc[0] if 'Date of the event' in group_rows.columns else ''
        
        date_str = str(event_date)[:10] if event_date else ''
        
        key = f"group_{group_idx}_{normalize_team_name(best_event_name)}_{date_str}"
        
        grouped[key] = {
            'event_name': best_event_name,
            'event_date': group_rows['Date of the event'].iloc[0] if 'Date of the event' in group_rows.columns else '',
            'parsed_date_sort': event_date if isinstance(event_date, (pd.Timestamp, datetime)) else None,
            'orders': [row for _, row in group_rows.iterrows()],
            'total_qty': 0,
            'total_sold': 0,
            'total_supp_price': 0,
            'with_supplier': 0,
            'without_supplier': 0,
            'suppliers': set()
        }
        
        for _, row in group_rows.iterrows():
            qty = pd.to_numeric(row.get('Qty', 0), errors='coerce') or 0
            total_sold = clean_numeric(row.get('total sold', 0)) if 'total sold' in row.index else clean_numeric(row.get('TOTAL', 0))
            supp_price = parse_supp_price(row.get('SUPP PRICE', ''))
            supp_name = str(row.get('Supplier NAME', '')).strip()
            
            grouped[key]['total_qty'] += qty
            grouped[key]['total_sold'] += total_sold
            grouped[key]['total_supp_price'] += supp_price
            
            if row.get('has_supplier', False):
                grouped[key]['with_supplier'] += 1
                if supp_name:
                    grouped[key]['suppliers'].add(supp_name)
            else:
                grouped[key]['without_supplier'] += 1
    
    return grouped

def update_sheet_status(row_indices, new_status, progress_bar=None):
    """Update the 'orderd' column for specific rows in Google Sheet using batch updates."""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        headers = worksheet.row_values(1)
        ordered_col = None
        for i, header in enumerate(headers):
            if header.strip().lower() == 'orderd':
                ordered_col = i + 1
                break
        
        if ordered_col is None:
            st.error(t("no_orderd_col"))
            return False
        
        col_letter = col_number_to_letter(ordered_col)
        
        if new_status == 'orderd':
            color = {"red": 0.8, "green": 0.9, "blue": 1.0}
        elif new_status == 'done!':
            color = {"red": 0.85, "green": 1.0, "blue": 0.85}
        elif new_status == 'old no data':
            color = {"red": 0.9, "green": 0.9, "blue": 0.9}
        else:
            color = {"red": 1.0, "green": 1.0, "blue": 1.0}
        
        batch_size = 30
        total = len(row_indices)
        
        for i in range(0, total, batch_size):
            batch = row_indices[i:i+batch_size]
            
            cells = []
            for row_idx in batch:
                cells.append({
                    'range': f'{col_letter}{row_idx}',
                    'values': [[new_status]]
                })
            worksheet.batch_update(cells)
            
            requests = []
            for row_idx in batch:
                last_col = len(headers)
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': worksheet.id,
                            'startRowIndex': row_idx - 1,
                            'endRowIndex': row_idx,
                            'startColumnIndex': 0,
                            'endColumnIndex': last_col
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': color
                            }
                        },
                        'fields': 'userEnteredFormat.backgroundColor'
                    }
                })
            
            if requests:
                body = {'requests': requests}
                sheet.batch_update(body)
            
            if progress_bar:
                progress_bar.progress(min((i + batch_size) / total, 1.0))
            
            import time
            time.sleep(2)
        
        return True
        
    except Exception as e:
        st.error(f"Error updating sheet: {str(e)}")
        return False

def update_supplier_data(row_index, supp_price=None, supp_name=None, supp_order=None):
    """Update supplier columns (O, P, Q) for a specific row in Google Sheet."""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        cells = []
        if supp_price is not None:
            cells.append({'range': f'O{row_index}', 'values': [[str(supp_price)]]})
        if supp_name is not None:
            cells.append({'range': f'P{row_index}', 'values': [[str(supp_name)]]})
        if supp_order is not None:
            cells.append({'range': f'Q{row_index}', 'values': [[str(supp_order)]]})
        
        if cells:
            worksheet.batch_update(cells)
        
        return True
    except Exception as e:
        st.error(f"שגיאה בעדכון נתוני ספק: {str(e)}")
        return False

def delete_order_row(row_index):
    """Delete a row from Google Sheet."""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        worksheet.delete_rows(row_index)
        return True
    except Exception as e:
        st.error(f"שגיאה במחיקת ההזמנה: {str(e)}")
        return False

def parse_supp_price(price_str):
    """Parse SUPP PRICE and return numeric value or 0 if invalid."""
    if not price_str:
        return 0
    price_str = str(price_str).strip()
    if not price_str:
        return 0
    cleaned = re.sub(r'[^0-9.\-]', '', price_str.replace(',', ''))
    if cleaned in ("", "-", ".", "-."):
        return 0
    try:
        return float(cleaned)
    except:
        return 0

def find_column_flexible(df, keywords):
    """Find column by keywords, ignoring case and extra spaces."""
    keywords_lower = [k.lower() for k in keywords]
    for col in df.columns:
        col_clean = col.strip().lower()
        col_clean = ' '.join(col_clean.split())
        if all(kw in col_clean for kw in keywords_lower):
            return col
    return None

def get_rows_for_orderd(df):
    import pytz
    israel_tz = pytz.timezone('Asia/Jerusalem')
    today = datetime.now(israel_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    
    rows_to_update = []
    updated_orders_info = []
    
    supp_price_col = 'SUPP PRICE' if 'SUPP PRICE' in df.columns else None
    supp_name_col = 'Supplier NAME' if 'Supplier NAME' in df.columns else None
    supp_order_col = None
    for col in df.columns:
        if 'supp' in col.lower() and 'order' in col.lower():
            supp_order_col = col
            break
    status_col = 'orderd' if 'orderd' in df.columns else None
    
    if not all([status_col, 'parsed_date' in df.columns]):
        return [], []
    
    for idx, row in df.iterrows():
        event_date = row.get('parsed_date')
        current_status = str(row.get(status_col, '')).strip().lower()
        
        has_valid_date = event_date is not None and pd.notna(event_date)
        
        if has_valid_date:
            if event_date.tzinfo is None:
                event_date_aware = israel_tz.localize(event_date)
            else:
                event_date_aware = event_date.astimezone(israel_tz)
            is_future = event_date_aware.date() > today.date()
        else:
            is_future = False
        
        supp_price_raw = row.get(supp_price_col, '') if supp_price_col else ''
        supp_name = str(row.get(supp_name_col, '')).strip() if supp_name_col else ''
        supp_order = str(row.get(supp_order_col, '')).strip() if supp_order_col else ''
        
        supp_price_value = parse_supp_price(supp_price_raw)
        has_supp_price = supp_price_value > 0
        has_supp_name = supp_name != ''
        has_supp_order = supp_order != ''
        
        has_any_supp_data = has_supp_price or has_supp_name or has_supp_order
        
        already_orderd = current_status == 'orderd'
        
        if has_valid_date and is_future and has_any_supp_data and not already_orderd:
            rows_to_update.append(row['row_index'])
            event_name = row.get('event name', '') or row.get('Event name', '')
            updated_orders_info.append({
                'row': row['row_index'],
                'event': event_name,
                'date': event_date_aware.strftime('%d/%m/%Y'),
                'price': supp_price_value if has_supp_price else 0,
                'supplier': supp_name if has_supp_name else '-',
                'order': supp_order if has_supp_order else '-'
            })
    
    return rows_to_update, updated_orders_info

def get_rows_for_done(df):
    import pytz
    israel_tz = pytz.timezone('Asia/Jerusalem')
    today = datetime.now(israel_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    
    rows_to_update = []
    updated_orders_info = []
    
    supp_price_col = 'SUPP PRICE' if 'SUPP PRICE' in df.columns else None
    supp_name_col = 'Supplier NAME' if 'Supplier NAME' in df.columns else None
    supp_order_col = None
    for col in df.columns:
        if 'supp' in col.lower() and 'order' in col.lower():
            supp_order_col = col
            break
    status_col = 'orderd' if 'orderd' in df.columns else None
    
    if not all([status_col, 'parsed_date' in df.columns]):
        return [], []
    
    for idx, row in df.iterrows():
        event_date = row.get('parsed_date')
        current_status = str(row.get(status_col, '')).strip().lower()
        
        has_valid_date = event_date is not None and pd.notna(event_date)
        
        if has_valid_date:
            if event_date.tzinfo is None:
                event_date_aware = israel_tz.localize(event_date)
            else:
                event_date_aware = event_date.astimezone(israel_tz)
            is_past = event_date_aware.date() < today.date()
        else:
            is_past = False
        
        supp_price_raw = row.get(supp_price_col, '') if supp_price_col else ''
        supp_name = str(row.get(supp_name_col, '')).strip() if supp_name_col else ''
        supp_order = str(row.get(supp_order_col, '')).strip() if supp_order_col else ''
        
        supp_price_value = parse_supp_price(supp_price_raw)
        has_supp_price = supp_price_value > 0
        has_supp_name = supp_name != ''
        has_supp_order = supp_order != ''
        
        has_any_supp_data = has_supp_price or has_supp_name or has_supp_order
        
        already_done = current_status == 'done!'
        
        if has_valid_date and is_past and has_any_supp_data and not already_done:
            rows_to_update.append(row['row_index'])
            event_name = row.get('event name', '') or row.get('Event name', '')
            updated_orders_info.append({
                'row': row['row_index'],
                'event': event_name,
                'date': event_date_aware.strftime('%d/%m/%Y'),
                'price': supp_price_value if has_supp_price else 0,
                'supplier': supp_name if has_supp_name else '-',
                'order': supp_order if has_supp_order else '-'
            })
    
    return rows_to_update, updated_orders_info

def get_rows_for_old_no_data(df):
    """מוצא הזמנות ישנות (עבר) ללא נתוני ספק"""
    import pytz
    israel_tz = pytz.timezone('Asia/Jerusalem')
    today = datetime.now(israel_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    
    rows_to_update = []
    updated_orders_info = []
    
    supp_price_col = 'SUPP PRICE' if 'SUPP PRICE' in df.columns else None
    supp_name_col = 'Supplier NAME' if 'Supplier NAME' in df.columns else None
    supp_order_col = None
    for col in df.columns:
        if 'supp' in col.lower() and 'order' in col.lower():
            supp_order_col = col
            break
    status_col = 'orderd' if 'orderd' in df.columns else None
    
    if not all([status_col, 'parsed_date' in df.columns]):
        return [], []
    
    for idx, row in df.iterrows():
        event_date = row.get('parsed_date')
        current_status = str(row.get(status_col, '')).strip().lower()
        
        has_valid_date = event_date is not None and pd.notna(event_date)
        
        if has_valid_date:
            if event_date.tzinfo is None:
                event_date_aware = israel_tz.localize(event_date)
            else:
                event_date_aware = event_date.astimezone(israel_tz)
            is_past = event_date_aware.date() < today.date()
        else:
            is_past = False
        
        supp_price_raw = row.get(supp_price_col, '') if supp_price_col else ''
        supp_name = str(row.get(supp_name_col, '')).strip() if supp_name_col else ''
        supp_order = str(row.get(supp_order_col, '')).strip() if supp_order_col else ''
        
        supp_price_value = parse_supp_price(supp_price_raw)
        has_supp_price = supp_price_value > 0
        has_supp_name = supp_name != ''
        has_supp_order = supp_order != ''
        
        has_any_supp_data = has_supp_price or has_supp_name or has_supp_order
        
        already_old_no_data = current_status == 'old no data'
        already_done = current_status == 'done!'
        
        if has_valid_date and is_past and not has_any_supp_data and not already_old_no_data and not already_done:
            rows_to_update.append(row['row_index'])
            event_name = row.get('event name', '') or row.get('Event name', '')
            updated_orders_info.append({
                'row': row['row_index'],
                'event': event_name,
                'date': event_date_aware.strftime('%d/%m/%Y')
            })
    
    return rows_to_update, updated_orders_info

def display_update_summary(info_list, status_type, language='he'):
    """הצגת סיכום עדכון"""
    count = len(info_list)
    if count == 0:
        st.info("לא נמצאו הזמנות לעדכון")
        return
    
    if status_type == 'orderd':
        st.success(f"🎯 נמצאו **{count}** הזמנות עתידיות לעדכון ל-**הוזמן**")
    elif status_type == 'done!':
        st.success(f"✅ נמצאו **{count}** הזמנות שהסתיימו לעדכון ל-**בוצע**")
    elif status_type == 'old no data':
        st.warning(f"⚠️ נמצאו **{count}** הזמנות ישנות ללא נתונים")
    
    with st.expander(f"📋 פרטים ({count} הזמנות)"):
        for item in info_list[:10]:
            st.write(f"שורה {item['row']}: {item.get('event', '')} - {item.get('date', '')}")
        if count > 10:
            st.caption(f"... ועוד {count - 10}")

def setup_status_dropdown():
    """Set up data validation dropdown for status column in Google Sheet."""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        headers = worksheet.row_values(1)
        ordered_col = None
        for i, header in enumerate(headers):
            if header.strip().lower() == 'orderd':
                ordered_col = i + 1
                break
        
        if ordered_col is None:
            return False
        
        col_letter = chr(64 + ordered_col) if ordered_col <= 26 else 'B'
        
        from gspread_formatting import DataValidationRule, set_data_validation_for_cell_range
        from gspread_formatting.dataframe import DataValidationRule as DVR
        
        return True
        
    except Exception as e:
        st.error(f"Error setting up dropdown: {str(e)}")
        return False

def get_status_color(status):
    """Return color based on status."""
    if status is None:
        return ""
    status_lower = str(status).lower().strip()
    if status_lower in ['done!', 'done', 'purchased']:
        return "background-color: #90EE90"
    elif status_lower == 'new':
        return "background-color: #FFB6C1"
    elif status_lower == 'orderd':
        return "background-color: #ADD8E6"
    elif status_lower == 'old no data':
        return "background-color: #E5E5E5"
    return ""

def display_history(language='he'):
    """Display update history in a clean format."""
    if 'update_history' not in st.session_state or not st.session_state.update_history:
        if language == 'he':
            st.info("📜 אין היסטוריה עדיין")
        else:
            st.info("📜 No history yet")
        return
    
    st.subheader("📜 היסטוריית עדכונים" if language == 'he' else "📜 Update History")
    
    for idx, entry in enumerate(st.session_state.update_history[:20]):
        if entry['status'] == 'orderd':
            status_emoji = "🎯"
            status_text = "הוזמן"
        elif entry['status'] == 'done!':
            status_emoji = "✅"
            status_text = "בוצע"
        elif entry['status'] == 'old no data':
            status_emoji = "⚠️"
            status_text = "ישן ללא נתונים"
        else:
            status_emoji = "📝"
            status_text = entry['status']
        
        timestamp = entry['timestamp']
        date_part = timestamp.split(' ')[0]
        time_part = timestamp.split(' ')[1]
        
        with st.expander(f"{status_emoji} {date_part} {time_part} - **{entry['count']} הזמנות** → {status_text}"):
            st.write(f"**סטטוס:** {status_text}")
            st.write(f"**כמות:** {entry['count']} הזמנות")
            
            rows_str = ', '.join(map(str, entry['rows'][:10]))
            if len(entry['rows']) > 10:
                rows_str += f" ... ועוד {len(entry['rows']) - 10}"
            st.write(f"**שורות:** {rows_str}")
    
    st.markdown("---")
    if st.button("🗑️ נקה היסטוריה", key="clear_history"):
        st.session_state.update_history = []
        st.rerun()

def save_update_history(rows_updated, status, user_email=None):
    """Save update history to session state."""
    if 'update_history' not in st.session_state:
        st.session_state.update_history = []
    
    history_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': status,
        'count': len(rows_updated),
        'rows': rows_updated,
        'user': user_email or 'unknown'
    }
    
    st.session_state.update_history.insert(0, history_entry)
    
    if len(st.session_state.update_history) > 50:
        st.session_state.update_history = st.session_state.update_history[:50]

def scan_old_sheet_for_migration():
    """סריקת הגיליון הישן ושמירת הנתונים ב-session_state"""
    OLD_SHEET_ID = "11MGLk4Gs20-olgRW-_z6GX_CsQEMHgcZUWiENnDeG0g"
    NEW_SHEET_NAME = "מערכת הזמנות - קוד יהודה  "
    
    try:
        client = get_gspread_client()
        
        old_sheet = client.open_by_key(OLD_SHEET_ID).get_worksheet(0)
        old_data = old_sheet.get_all_values()
        old_headers = old_data[0]
        
        def find_col_index(headers, possible_names):
            for name in possible_names:
                if name in headers:
                    return headers.index(name)
            for idx, h in enumerate(headers):
                for name in possible_names:
                    if name.lower() in h.lower():
                        return idx
            return None
        
        old_order_col = find_col_index(old_headers, ['Order number', 'order number', 'Order Number'])
        old_status_col = find_col_index(old_headers, ['orderd', 'Orderd', 'status', 'Status'])
        old_supp_price_col = find_col_index(old_headers, ['SUPP PRICE', 'supp price', 'Supp Price'])
        old_supp_name_col = find_col_index(old_headers, ['Supplier NAME', 'supplier name', 'Supplier name'])
        old_supp_order_col = find_col_index(old_headers, ['SUPP order number', 'supp order number', 'SUPP order', 'supp order'])
        
        if old_order_col is None:
            return None, "לא נמצאה עמודת Order number בגיליון הישן"
        
        old_orders = {}
        for row in old_data[1:]:
            if len(row) <= old_order_col:
                continue
            order_num = row[old_order_col].strip()
            status = row[old_status_col].strip().lower() if old_status_col and len(row) > old_status_col else ''
            
            if order_num:
                supp_price = row[old_supp_price_col].strip() if old_supp_price_col and len(row) > old_supp_price_col else ''
                supp_name = row[old_supp_name_col].strip() if old_supp_name_col and len(row) > old_supp_name_col else ''
                supp_order = row[old_supp_order_col].strip() if old_supp_order_col and len(row) > old_supp_order_col else ''
                
                if supp_price or supp_name or supp_order:
                    old_orders[order_num] = {
                        'price': supp_price,
                        'name': supp_name,
                        'order': supp_order
                    }
        
        new_sheet = client.open(NEW_SHEET_NAME).get_worksheet(0)
        new_data = new_sheet.get_all_values()
        new_headers = new_data[0]
        
        new_order_col = new_headers.index('Order number')
        new_status_col = new_headers.index('orderd')
        
        updates = []
        for idx, row in enumerate(new_data[1:], start=2):
            order_num = row[new_order_col].strip()
            status = row[new_status_col].strip()
            
            if status == 'New' and order_num in old_orders:
                old_info = old_orders[order_num]
                updates.append({
                    'row': idx,
                    'order_num': order_num,
                    'price': old_info['price'],
                    'name': old_info['name'],
                    'order': old_info['order']
                })
        
        return updates, None
    
    except Exception as e:
        return None, str(e)

def execute_migration(updates):
    """ביצוע ההעתקה בפועל"""
    NEW_SHEET_NAME = "מערכת הזמנות - קוד יהודה  "
    
    try:
        client = get_gspread_client()
        new_sheet = client.open(NEW_SHEET_NAME).get_worksheet(0)
        
        batch_size = 30
        total = len(updates)
        
        for i in range(0, total, batch_size):
            batch = updates[i:i+batch_size]
            cells = []
            
            for update in batch:
                row_num = update['row']
                cells.append({'range': f'O{row_num}', 'values': [[update['price']]]})
                cells.append({'range': f'P{row_num}', 'values': [[update['name']]]})
                cells.append({'range': f'Q{row_num}', 'values': [[update['order']]]})
            
            new_sheet.batch_update(cells)
            time.sleep(1)
        
        return True, None
    except Exception as e:
        return False, str(e)

with st.sidebar:
    lang_options = {"עברית": "he", "English": "en"}
    selected_lang = st.selectbox(
        t("language"),
        options=list(lang_options.keys()),
        index=0 if st.session_state.language == 'he' else 1
    )
    if lang_options[selected_lang] != st.session_state.language:
        st.session_state.language = lang_options[selected_lang]
        st.rerun()
    
    st.header(t("sidebar_header"))
    st.markdown("---")
    
    if st.button(t("refresh_data"), use_container_width=True):
        load_data_from_sheet.clear()
        st.cache_data.clear()
        if 'sheet_error' in st.session_state:
            del st.session_state.sheet_error
        st.rerun()
    
    if st.button(t("auto_update_btn"), use_container_width=True):
        temp_df = load_data_from_sheet()
        if not temp_df.empty:
            rows_to_update, updated_orders = get_rows_for_orderd(temp_df)
            
            if rows_to_update:
                st.info(f"⏳ {t('updating')} {len(rows_to_update)} {t('orders')}...")
                progress_bar = st.progress(0)
                
                if update_sheet_status(rows_to_update, "orderd", progress_bar):
                    progress_bar.progress(1.0)
                    save_update_history(rows_to_update, 'orderd')
                    st.success(f"✅ {t('auto_updated')} {len(rows_to_update)} {t('orders')} → orderd")
                    
                    st.markdown(f"**{t('updated_orders_list')}:**")
                    for order in updated_orders[:15]:
                        st.write(f"🔵 {order['event']}")
                    if len(updated_orders) > 15:
                        st.write(f"... {t('and_more')} {len(updated_orders) - 15}")
                    
                    st.cache_data.clear()
                    import time
                    time.sleep(3)
                    st.rerun()
            else:
                st.info(t("no_orders_to_update"))
    
    if st.button(t("update_done_btn"), use_container_width=True, type="secondary"):
        temp_df = load_data_from_sheet()
        if not temp_df.empty:
            rows_to_update, updated_orders = get_rows_for_done(temp_df)
            
            if rows_to_update:
                st.info(f"⏳ {t('updating')} {len(rows_to_update)} {t('orders')}...")
                progress_bar = st.progress(0)
                
                if update_sheet_status(rows_to_update, "done!", progress_bar):
                    progress_bar.progress(1.0)
                    save_update_history(rows_to_update, 'done!')
                    st.success(f"✅ {t('auto_updated')} {len(rows_to_update)} {t('orders')} → done!")
                    
                    st.markdown(f"**{t('updated_orders_list')}:**")
                    for order in updated_orders[:15]:
                        st.write(f"🟢 {order['event']}")
                    if len(updated_orders) > 15:
                        st.write(f"... {t('and_more')} {len(updated_orders) - 15}")
                    
                    st.cache_data.clear()
                    import time
                    time.sleep(3)
                    st.rerun()
            else:
                st.info(t("no_done_to_update"))
    
    st.markdown("---")
    
    # Prominent action buttons with clear header
    st.markdown("### ⚡ פעולות מהירות")
    
    if 'show_manual_order_form' not in st.session_state:
        st.session_state.show_manual_order_form = False
    if 'show_global_search' not in st.session_state:
        st.session_state.show_global_search = False
    if 'sidebar_search_query' not in st.session_state:
        st.session_state.sidebar_search_query = ""
    
    if st.button("➕ הוספה ידנית של הזמנה", use_container_width=True, type="secondary"):
        st.session_state.show_manual_order_form = not st.session_state.show_manual_order_form
        st.session_state.show_global_search = False
        st.rerun()
    
    if st.session_state.show_manual_order_form:
        st.success("✓ הטופס פתוח למטה ⬇️")
    
    st.markdown("---")
    st.markdown("### 📧 שליחת דוחות למייל")
    
    temp_df_for_email = load_data_from_sheet()
    
    report_type = st.selectbox(
        "בחר סוג דוח:",
        options=["📋 כרטיסים לרכישה", "💰 מכירות יומי", "📊 מכירות שבועי", "🔴 הזמנות שלא שולמו"],
        key="email_report_type_selector"
    )
    
    email_recipient = st.text_input(
        "📬 שלח ל:",
        value=DEFAULT_NEW_ORDERS_EMAIL,
        key="report_email_recipient"
    )
    
    if report_type == "📋 כרטיסים לרכישה":
        new_orders_for_email = pd.DataFrame()
        if not temp_df_for_email.empty and 'orderd' in temp_df_for_email.columns:
            new_orders_for_email = temp_df_for_email[
                temp_df_for_email['orderd'].fillna('').str.strip().str.lower() == 'new'
            ].copy()
        
        new_count = len(new_orders_for_email)
        new_tickets = int(pd.to_numeric(new_orders_for_email.get('Qty', 0), errors='coerce').sum()) if not new_orders_for_email.empty else 0
        
        if new_count > 0:
            st.info(f"📋 {new_count} הזמנות ({new_tickets} כרטיסים)")
            if st.button("📤 שלח דוח", use_container_width=True, type="primary", key="send_new_orders_btn"):
                if email_recipient and '@' in email_recipient:
                    with st.spinner("שולח מייל..."):
                        success, message = send_new_orders_report_email(new_orders_for_email, email_recipient)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("❌ כתובת מייל לא תקינה")
        else:
            st.caption("✅ אין הזמנות חדשות")
    
    elif report_type == "💰 מכירות יומי":
        israel_tz = pytz.timezone('Israel')
        today = datetime.now(israel_tz).date()
        
        selected_date = st.date_input(
            "בחר תאריך:",
            value=today,
            key="daily_report_date_picker"
        )
        selected_date_str = selected_date.strftime('%d/%m/%Y')
        
        daily_orders = pd.DataFrame()
        if not temp_df_for_email.empty:
            temp_df_for_email = temp_df_for_email.copy()
            if 'order date' in temp_df_for_email.columns:
                temp_df_for_email['order_date_parsed'] = pd.to_datetime(
                    temp_df_for_email['order date'], 
                    format='%m/%d/%Y %H:%M:%S',
                    errors='coerce'
                )
                temp_df_for_email.loc[temp_df_for_email['order_date_parsed'].isna(), 'order_date_parsed'] = pd.to_datetime(
                    temp_df_for_email.loc[temp_df_for_email['order_date_parsed'].isna(), 'order date'],
                    dayfirst=True,
                    errors='coerce'
                )
                
                daily_orders = temp_df_for_email[
                    (temp_df_for_email['order_date_parsed'].dt.date == selected_date)
                ].copy()
        
        daily_count = len(daily_orders)
        daily_tickets = int(pd.to_numeric(daily_orders.get('Qty', 0), errors='coerce').sum()) if not daily_orders.empty else 0
        
        st.info(f"💰 {daily_count} הזמנות ({selected_date_str}) | {daily_tickets} כרטיסים")
        if daily_count > 0:
            if st.button("📤 שלח דוח יומי", use_container_width=True, type="primary", key="send_daily_sales_btn"):
                if email_recipient and '@' in email_recipient:
                    with st.spinner("שולח מייל..."):
                        success, message = send_daily_sales_report_email(daily_orders, email_recipient, selected_date)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("❌ כתובת מייל לא תקינה")
        else:
            st.caption(f"אין מכירות ב-{selected_date_str}")
    
    elif report_type == "📊 מכירות שבועי":
        israel_tz = pytz.timezone('Israel')
        today = datetime.now(israel_tz).date()
        default_start = today - timedelta(days=today.weekday() + 1)
        if today.weekday() == 6:
            default_start = today
        default_end = default_start + timedelta(days=6)
        
        col_start, col_end = st.columns(2)
        with col_start:
            start_of_week = st.date_input(
                "מתאריך:",
                value=default_start,
                key="weekly_report_start_date"
            )
        with col_end:
            end_of_week = st.date_input(
                "עד תאריך:",
                value=default_end,
                key="weekly_report_end_date"
            )
        
        weekly_orders = pd.DataFrame()
        if not temp_df_for_email.empty:
            temp_df_for_email = temp_df_for_email.copy()
            if 'order date' in temp_df_for_email.columns:
                temp_df_for_email['order_date_parsed'] = pd.to_datetime(
                    temp_df_for_email['order date'], 
                    format='%m/%d/%Y %H:%M:%S',
                    errors='coerce'
                )
                temp_df_for_email.loc[temp_df_for_email['order_date_parsed'].isna(), 'order_date_parsed'] = pd.to_datetime(
                    temp_df_for_email.loc[temp_df_for_email['order_date_parsed'].isna(), 'order date'],
                    dayfirst=True,
                    errors='coerce'
                )
                
                weekly_orders = temp_df_for_email[
                    (temp_df_for_email['order_date_parsed'].dt.date >= start_of_week) &
                    (temp_df_for_email['order_date_parsed'].dt.date <= end_of_week)
                ].copy()
        
        weekly_count = len(weekly_orders)
        weekly_tickets = int(pd.to_numeric(weekly_orders.get('Qty', 0), errors='coerce').sum()) if not weekly_orders.empty else 0
        
        st.info(f"📊 {weekly_count} הזמנות ({start_of_week.strftime('%d/%m')} - {end_of_week.strftime('%d/%m')}) | {weekly_tickets} כרטיסים")
        if weekly_count > 0:
            if st.button("📤 שלח דוח שבועי", use_container_width=True, type="primary", key="send_weekly_sales_btn"):
                if email_recipient and '@' in email_recipient:
                    with st.spinner("שולח מייל..."):
                        success, message = send_weekly_sales_report_email(weekly_orders, email_recipient, start_of_week, end_of_week)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("❌ כתובת מייל לא תקינה")
        else:
            st.caption(f"אין מכירות בתקופה זו")
    
    elif report_type == "🔴 הזמנות שלא שולמו":
        unpaid_orders_for_email = pd.DataFrame()
        if not temp_df_for_email.empty and 'orderd' in temp_df_for_email.columns:
            # Find orders with status 'sent_not_paid', 'sent - not paid', or 'נשלח ולא שולם'
            status_mask = (
                temp_df_for_email['orderd'].fillna('').str.strip().str.lower().str.contains('sent_not_paid', na=False) |
                temp_df_for_email['orderd'].fillna('').str.strip().str.lower().str.contains('sent - not paid', na=False) |
                temp_df_for_email['orderd'].fillna('').str.strip().str.contains('נשלח ולא שולם', na=False)
            )
            unpaid_orders_for_email = temp_df_for_email[status_mask].copy()
            
            # Ensure row_index exists - it should already be there from load_data_from_sheet, but double-check
            if 'row_index' not in unpaid_orders_for_email.columns and not unpaid_orders_for_email.empty:
                # Re-add row_index if missing (shouldn't happen, but just in case)
                unpaid_orders_for_email = unpaid_orders_for_email.copy()
                # Use the original index from temp_df_for_email to calculate row_index
                for idx, row in unpaid_orders_for_email.iterrows():
                    if idx in temp_df_for_email.index:
                        original_row_idx = temp_df_for_email.loc[idx, 'row_index'] if 'row_index' in temp_df_for_email.columns else idx + 2
                        unpaid_orders_for_email.at[idx, 'row_index'] = original_row_idx
                    else:
                        unpaid_orders_for_email.at[idx, 'row_index'] = idx + 2
        
        unpaid_count = len(unpaid_orders_for_email)
        unpaid_tickets = int(pd.to_numeric(unpaid_orders_for_email.get('Qty', 0), errors='coerce').sum()) if not unpaid_orders_for_email.empty else 0
        
        # Calculate total amount
        total_amount = 0
        if not unpaid_orders_for_email.empty and 'TOTAL' in unpaid_orders_for_email.columns:
            for total_val in unpaid_orders_for_email['TOTAL']:
                if total_val and total_val != '-':
                    try:
                        amount = float(str(total_val).replace('€','').replace('£','').replace('$','').replace(',','').strip())
                        total_amount += amount
                    except:
                        pass
        
        if unpaid_count > 0:
            st.info(f"🔴 {unpaid_count} הזמנות ({unpaid_tickets} כרטיסים) | סה״כ לגבייה: €{total_amount:,.2f}")
            if st.button("📤 שלח דוח הזמנות שלא שולמו", use_container_width=True, type="primary", key="send_unpaid_orders_btn"):
                if email_recipient and '@' in email_recipient:
                    with st.spinner("שולח מייל..."):
                        success, message = send_unpaid_orders_report_email(unpaid_orders_for_email, email_recipient)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("❌ כתובת מייל לא תקינה")
        else:
            st.caption("✅ אין הזמנות שלא שולמו")
    
    st.markdown("---")
    st.markdown("**🔍 חיפוש מהיר**")
    sidebar_search_input = st.text_input(
        "הקלד מספר הזמנה/דוקט:",
        value=st.session_state.sidebar_search_query,
        placeholder="חיפוש...",
        key="sidebar_search_input_box",
        label_visibility="collapsed"
    )
    
    if st.button("🔍 חפש", use_container_width=True, type="primary"):
        if sidebar_search_input and len(sidebar_search_input.strip()) >= 2:
            st.session_state.sidebar_search_query = sidebar_search_input.strip()
            st.session_state.show_global_search = True
            st.session_state.show_manual_order_form = False
            st.rerun()
        elif sidebar_search_input:
            st.warning("הקלד לפחות 2 תווים")
    
    if st.session_state.show_global_search and st.session_state.sidebar_search_query:
        st.info(f"🔍 תוצאות למטה ⬇️")
    
    st.markdown("---")
    st.subheader(t("filters"))
    
    df = load_data_from_sheet()
    
    # Initialize filter session state
    if 'filter_events' not in st.session_state:
        st.session_state.filter_events = []
    if 'filter_sources' not in st.session_state:
        st.session_state.filter_sources = []
    if 'filter_teams' not in st.session_state:
        st.session_state.filter_teams = []
    if 'filter_status' not in st.session_state:
        st.session_state.filter_status = 0
    if 'filter_cleared' not in st.session_state:
        st.session_state.filter_cleared = False
    if 'filter_date_reset' not in st.session_state:
        st.session_state.filter_date_reset = False
    
    if not df.empty:
        # Calculate date range limits
        min_date_val = None
        max_date_val = None
        if 'parsed_date' in df.columns:
            valid_dates = df['parsed_date'].dropna()
            if not valid_dates.empty:
                min_date_val = valid_dates.min()
                max_date_val = valid_dates.max()
        
        # Count active filters
        active_filter_count = 0
        active_filters_list = []
        
        # Check events filter
        if st.session_state.filter_events:
            active_filter_count += 1
            active_filters_list.append(("אירועים", f"{len(st.session_state.filter_events)} נבחרו", "events"))
        
        # Check sources filter
        if st.session_state.filter_sources:
            active_filter_count += 1
            active_filters_list.append(("מקורות", f"{len(st.session_state.filter_sources)} נבחרו", "sources"))
        
        # Check teams filter
        if st.session_state.filter_teams:
            active_filter_count += 1
            active_filters_list.append(("קבוצות", f"{len(st.session_state.filter_teams)} נבחרו", "teams"))
        
        # Check status filter (0 = all statuses - no filter)
        if st.session_state.filter_status > 0:
            active_filter_count += 1
            active_filters_list.append(("סטטוס", "סינון פעיל", "status"))
        
        # Check date range filter (compare to full range)
        date_range_key = f"date_range_filter"
        if date_range_key in st.session_state and min_date_val is not None and max_date_val is not None:
            current_date_range = st.session_state[date_range_key]
            if isinstance(current_date_range, tuple) and len(current_date_range) == 2:
                full_min = min_date_val.date() if isinstance(min_date_val, datetime) else min_date_val
                full_max = max_date_val.date() if isinstance(max_date_val, datetime) else max_date_val
                if current_date_range[0] != full_min or current_date_range[1] != full_max:
                    active_filter_count += 1
                    active_filters_list.append(("תאריכים", f"{current_date_range[0]} - {current_date_range[1]}", "dates"))
        
        # Show active filter count badge
        if active_filter_count > 0:
            st.markdown(f"**🔍 פילטרים פעילים ({active_filter_count})**")
            
            # Show active filters with × buttons
            for filter_name, filter_desc, filter_key in active_filters_list:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.caption(f"• {filter_name}: {filter_desc}")
                with col2:
                    if st.button("×", key=f"clear_{filter_key}", help=f"הסר סינון {filter_name}"):
                        if filter_key == "events":
                            st.session_state.filter_events = []
                        elif filter_key == "sources":
                            st.session_state.filter_sources = []
                        elif filter_key == "teams":
                            st.session_state.filter_teams = []
                        elif filter_key == "status":
                            st.session_state.filter_status = 0
                        elif filter_key == "dates":
                            st.session_state.filter_date_reset = True
                        st.rerun()
            
            st.markdown("")
        
        # Clear All Filters button (prominent, at top)
        if st.button("🧹 נקה את כל הפילטרים", use_container_width=True, type="primary" if active_filter_count > 0 else "secondary"):
            st.session_state.filter_events = []
            st.session_state.filter_sources = []
            st.session_state.filter_teams = []
            st.session_state.filter_status = 0
            st.session_state.filter_date_reset = True
            st.session_state.filter_cleared = True
            st.rerun()
        
        # Show success message after clearing
        if st.session_state.filter_cleared:
            st.success("✅ כל הפילטרים נוקו!")
            st.session_state.filter_cleared = False
        
        st.markdown("---")
        
        # Event filter - sorted by closest date to today
        if 'event name' in df.columns:
            today = pd.Timestamp.now().normalize()
            all_events = df['event name'].dropna().unique().tolist()
            
            if 'parsed_date' in df.columns:
                event_dates = df.groupby('event name')['parsed_date'].min().reset_index()
                events_with_dates = event_dates[event_dates['parsed_date'].notna()].copy()
                events_without_dates = event_dates[event_dates['parsed_date'].isna()]['event name'].tolist()
                
                if not events_with_dates.empty:
                    events_with_dates['days_from_today'] = (events_with_dates['parsed_date'] - today).dt.days
                    future_events = events_with_dates[events_with_dates['days_from_today'] >= 0].sort_values('days_from_today')
                    past_events = events_with_dates[events_with_dates['days_from_today'] < 0].sort_values('days_from_today', ascending=False)
                    sorted_events = pd.concat([future_events, past_events])
                    events = sorted_events['event name'].tolist() + events_without_dates
                else:
                    events = all_events
            else:
                events = all_events
            
            selected_events = st.multiselect(
                t("event_name"), 
                options=events, 
                default=st.session_state.filter_events,
                key="event_multiselect",
                help="מסודר לפי תאריך קרוב ביותר להיום"
            )
            st.session_state.filter_events = selected_events
        else:
            selected_events = []
        
        # Date range filter
        if min_date_val is not None and max_date_val is not None:
            if isinstance(min_date_val, datetime) and isinstance(max_date_val, datetime):
                full_date_range = (min_date_val.date(), max_date_val.date())
                
                # Reset date range if flag is set - directly update session state key
                if st.session_state.filter_date_reset:
                    st.session_state[date_range_key] = full_date_range
                    st.session_state.filter_date_reset = False
                
                date_range = st.date_input(
                    t("date_range"),
                    value=full_date_range,
                    min_value=min_date_val.date(),
                    max_value=max_date_val.date(),
                    key=date_range_key
                )
            else:
                date_range = None
        else:
            date_range = None
        
        # Source filter with normalized display names
        if 'source' in df.columns:
            raw_sources = df['source'].dropna().unique().tolist()
            display_to_raw = {}
            for src in raw_sources:
                display_name = get_source_display_name(src)
                if display_name not in display_to_raw:
                    display_to_raw[display_name] = []
                display_to_raw[display_name].append(src)
            
            source_display_options = sorted(display_to_raw.keys())
            selected_source_displays = st.multiselect(
                t("source"), 
                options=source_display_options, 
                default=[d for d in st.session_state.filter_sources if d in source_display_options],
                key="source_multiselect"
            )
            st.session_state.filter_sources = selected_source_displays
            
            selected_sources = []
            for display in selected_source_displays:
                selected_sources.extend(display_to_raw.get(display, []))
        else:
            selected_sources = []
        
        # Team filter - extract teams from all events
        all_sidebar_teams = set()
        if 'event name' in df.columns:
            for event in df['event name'].dropna().unique():
                teams = extract_teams(str(event))
                for team in teams:
                    if team and len(team) > 1:
                        all_sidebar_teams.add(team.title())
        
        if all_sidebar_teams:
            selected_teams = st.multiselect(
                "🏆 סינון לפי קבוצה", 
                options=sorted(list(all_sidebar_teams)), 
                default=st.session_state.filter_teams,
                key="team_multiselect"
            )
            st.session_state.filter_teams = selected_teams
        else:
            selected_teams = []
        
        # Status filter
        if 'orderd' in df.columns:
            statuses = df['orderd'].fillna('').unique().tolist()
            statuses = [s.strip() if s else '' for s in statuses]
            statuses = list(set(statuses))
            statuses = sorted([s for s in statuses if s])
            all_option = t("all_statuses")
            status_options = [all_option] + statuses
            selected_status = st.selectbox(
                t("status"), 
                options=status_options, 
                index=st.session_state.filter_status,
                key="status_select"
            )
            st.session_state.filter_status = status_options.index(selected_status)
        else:
            selected_status = None
        
    else:
        selected_events = []
        date_range = None
        selected_sources = []
        selected_teams = []
        selected_status = None
    
    st.markdown("---")
    st.subheader("🔧 כלים נוספים")
    
    if st.button("➕ הוסף הזמנות חסרות", key="add_missing_sidebar", use_container_width=True):
        st.session_state.show_add_missing = True
        st.rerun()
    
    if st.session_state.get('show_add_missing', False):
        add_missing_orders_simple()
        if st.button("❌ סגור", key="close_add_missing"):
            st.session_state.show_add_missing = False
            st.rerun()
    
    if 'migration_done' in st.session_state and st.session_state.migration_done:
        st.success("✅ העתקת נתונים הושלמה!")
        if st.button("🔄 אפס (אפשר להעתיק שוב)", key="reset_migration"):
            st.session_state.migration_done = False
            if 'migration_updates' in st.session_state:
                del st.session_state.migration_updates
            st.rerun()
    elif 'migration_updates' in st.session_state and st.session_state.migration_updates:
        updates = st.session_state.migration_updates
        st.success(f"🎯 נמצאו {len(updates)} הזמנות לעדכון!")
        
        with st.expander(f"📋 פרטים ({len(updates)} הזמנות)"):
            for update in updates[:5]:
                st.write(f"שורה {update['row']}: {update['order_num']}")
            if len(updates) > 5:
                st.caption(f"... ועוד {len(updates) - 5}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ אישור והעתקה", key="confirm_migration", type="primary"):
                with st.spinner("מעדכן..."):
                    success, error = execute_migration(updates)
                    if success:
                        st.session_state.migration_done = True
                        del st.session_state.migration_updates
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"שגיאה: {error}")
        with col2:
            if st.button("❌ ביטול", key="cancel_migration"):
                del st.session_state.migration_updates
                st.rerun()
    else:
        if st.button("📦 סרוק נתונים מגיליון ישן", key="migrate_btn"):
            with st.spinner("סורק גיליונות..."):
                updates, error = scan_old_sheet_for_migration()
                if error:
                    st.error(f"❌ {error}")
                elif not updates:
                    st.warning("⚠️ לא נמצאו הזמנות להעתקה")
                else:
                    st.session_state.migration_updates = updates
                    st.rerun()
    
    st.markdown("---")
    
    with st.expander("🔍 Debug Info", expanded=False):
        temp_df = load_data_from_sheet()
        st.write(f"**Total rows:** {len(temp_df)}")
        st.write(f"**Column names:** {temp_df.columns.tolist()[:10]}")
        
        supp_order_col = None
        for col in temp_df.columns:
            if 'supp' in col.lower() and 'order' in col.lower():
                supp_order_col = col
                st.write(f"**SUPP order col found:** '{col}'")
        
        rows_orderd, info_orderd = get_rows_for_orderd(temp_df)
        rows_done, info_done = get_rows_for_done(temp_df)
        
        st.write(f"**Rows to update to orderd:** {len(rows_orderd)}")
        st.write(f"**Rows to update to done!:** {len(rows_done)}")
        
        if 'orderd' in temp_df.columns:
            statuses = temp_df['orderd'].value_counts()
            st.write("**Status counts:**", statuses.to_dict())
        
        if 'SUPP PRICE' in temp_df.columns:
            has_price = temp_df['SUPP PRICE'].notna() & (temp_df['SUPP PRICE'] != '')
            st.write(f"**Rows with SUPP PRICE:** {has_price.sum()}")
        
        now = datetime.now()
        if 'orderd' in temp_df.columns and 'SUPP PRICE' in temp_df.columns and 'parsed_date' in temp_df.columns:
            new_rows = temp_df[temp_df['orderd'].str.lower().str.strip() == 'new']
            st.write(f"**New rows total:** {len(new_rows)}")
            
            orderd_rows = temp_df[temp_df['orderd'].str.lower().str.strip() == 'orderd']
            st.write(f"**orderd rows total:** {len(orderd_rows)}")
        
        if 'parsed_date' in temp_df.columns:
            valid_dates = temp_df['parsed_date'].notna().sum()
            st.write(f"**Valid dates:** {valid_dates}")
            future = temp_df[temp_df['parsed_date'] > now]
            past = temp_df[temp_df['parsed_date'] <= now]
            st.write(f"**Future events:** {len(future)}")
            st.write(f"**Past events:** {len(past)}")

def apply_filters(df):
    """Apply sidebar filters to the dataframe."""
    filtered_df = df.copy()
    
    if selected_events:
        filtered_df = filtered_df[filtered_df['event name'].isin(selected_events)]
    
    if date_range and len(date_range) == 2 and 'parsed_date' in filtered_df.columns:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df['parsed_date'] >= datetime.combine(start_date, datetime.min.time())) &
            (filtered_df['parsed_date'] <= datetime.combine(end_date, datetime.max.time()))
        ]
    
    if selected_sources and 'source' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['source'].isin(selected_sources)]
    
    # Team filter
    if selected_teams and 'event name' in filtered_df.columns:
        def has_matching_team(event_name):
            teams = extract_teams(str(event_name))
            for team in teams:
                if team.title() in selected_teams:
                    return True
            return False
        filtered_df = filtered_df[filtered_df['event name'].apply(has_matching_team)]
    
    if selected_status and selected_status != t("all_statuses") and 'orderd' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['orderd'].fillna('').str.strip() == selected_status]
    
    return filtered_df

st.title(t("title"))

if df.empty:
    # Show stored error if available
    if 'sheet_error' in st.session_state:
        error_to_show = st.session_state.sheet_error
        # Make sure error is displayed prominently
        st.error("🔴 **שגיאה בחיבור ל-Google Sheets**")
        st.error(error_to_show)
        # Also show in an expander for better visibility
        with st.expander("📋 פרטי השגיאה המלאים", expanded=True):
            st.markdown(error_to_show)
    else:
        # If no specific error but data is empty, show generic message
        st.warning("⚠️ **לא נטענו נתונים** - לא נמצאה שגיאה ספציפית")
    
    st.warning(t("no_data"))
    
    # Diagnostic section
    with st.expander("🔍 אבחון מפורט - בדיקת חיבור ל-Google Sheets", expanded=True):
        diagnostic_results = {}
        creds_dict = None  # Initialize for use in permission check
        
        # 1. Check GOOGLE_CREDENTIALS environment variable
        st.subheader("1️⃣ בדיקת משתנה הסביבה GOOGLE_CREDENTIALS")
        
        # Try to get from Streamlit secrets first
        creds_json = None
        creds_source = None
        try:
            if hasattr(st, 'secrets') and 'GOOGLE_CREDENTIALS' in st.secrets:
                creds_json = st.secrets['GOOGLE_CREDENTIALS']
                creds_source = "Streamlit Secrets"
        except:
            pass
        
        # Fallback to environment variable
        if not creds_json:
            creds_json = os.environ.get("GOOGLE_CREDENTIALS")
            creds_source = "Environment Variable"
        
        if not creds_json:
            st.error("❌ **GOOGLE_CREDENTIALS לא נמצא**")
            st.info("💡 **פתרון:** הגדר את המשתנה ב-Streamlit Cloud Secrets:")
            st.code("""
1. לך ל-Streamlit Cloud Dashboard
2. בחר את האפליקציה שלך
3. לך ל-Settings > Secrets
4. הוסף: GOOGLE_CREDENTIALS = {הקוד JSON המלא}
            """)
            diagnostic_results['credentials'] = False
        else:
            st.success(f"✅ **GOOGLE_CREDENTIALS נמצא** (מ-{creds_source})")
            try:
                if isinstance(creds_json, dict):
                    # Already a dictionary (from Streamlit secrets)
                    creds_dict = creds_json
                elif isinstance(creds_json, str):
                    creds_dict = json.loads(creds_json)
                else:
                    creds_dict = dict(creds_json)
                
                # Check required fields
                required_fields = ['type', 'project_id', 'private_key', 'client_email']
                missing_fields = [f for f in required_fields if f not in creds_dict]
                
                if missing_fields:
                    st.warning(f"⚠️ **שדות חסרים ב-JSON:** {', '.join(missing_fields)}")
                    diagnostic_results['credentials'] = False
                else:
                    # Check if private_key has proper format
                    private_key = creds_dict.get('private_key', '')
                    if private_key and isinstance(private_key, str):
                        if 'BEGIN PRIVATE KEY' not in private_key:
                            st.warning("⚠️ **private_key לא נראה תקין** - ודא שהוא כולל 'BEGIN PRIVATE KEY'")
                        elif '\\n' in private_key and '\n' not in private_key:
                            st.info("ℹ️ **private_key מכיל \\n** - זה יתוקן אוטומטית")
                    
                    st.success(f"✅ **JSON תקין** - חשבון שירות: `{creds_dict.get('client_email', 'לא נמצא')}`")
                    diagnostic_results['credentials'] = True
            except json.JSONDecodeError as e:
                st.error(f"❌ **JSON לא תקין:** {str(e)}")
                diagnostic_results['credentials'] = False
            except Exception as e:
                st.error(f"❌ **שגיאה בפענוח:** {str(e)}")
                diagnostic_results['credentials'] = False
        
        st.markdown("---")
        
        # 2. Check sheet name
        st.subheader("2️⃣ בדיקת שם הגיליון")
        expected_name = "מערכת הזמנות - קוד יהודה  "
        st.info(f"**שם גיליון צפוי:** `{expected_name}` (עם 2 רווחים בסוף)")
        st.write(f"**שם גיליון בקוד:** `{SHEET_NAME}`")
        
        if SHEET_NAME == expected_name:
            st.success("✅ **שם הגיליון נכון**")
            diagnostic_results['sheet_name'] = True
        else:
            st.warning(f"⚠️ **שם הגיליון שונה מהצפוי**")
            st.code(f"SHEET_NAME = \"{expected_name}\"")
            diagnostic_results['sheet_name'] = False
        
        st.markdown("---")
        
        # 3. Test connection and permissions (automatic check)
        st.subheader("3️⃣ בדיקת חיבור והרשאות")
        
        # Check if we should run connection test (first time or if refresh requested)
        should_test_connection = (
            'connection_test_done' not in st.session_state or 
            st.session_state.get('refresh_connection_test', False)
        )
        
        if diagnostic_results.get('credentials', False):
            if should_test_connection:
                with st.spinner("בודק חיבור ל-Google Sheets..."):
                    try:
                        client = get_gspread_client()
                        st.success("✅ **חיבור ל-Google API הצליח**")
                        
                        # Try to open the sheet
                        try:
                            sheet = client.open(SHEET_NAME)
                            st.success(f"✅ **גיליון נמצא:** `{SHEET_NAME}`")
                            
                            # Check worksheet
                            try:
                                worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
                                st.success(f"✅ **גיליון עבודה #{WORKSHEET_INDEX} נטען בהצלחה**")
                                
                                # Try to read data
                                try:
                                    data = worksheet.get_all_values()
                                    if len(data) > 0:
                                        st.success(f"✅ **נתונים נקראו בהצלחה:** {len(data)} שורות")
                                        if len(data) < 2:
                                            st.warning("⚠️ **הגיליון ריק או יש רק כותרות**")
                                        else:
                                            st.info(f"📊 **כותרות:** {', '.join(data[0][:5])}...")
                                    else:
                                        st.warning("⚠️ **הגיליון ריק לחלוטין**")
                                    
                                    diagnostic_results['connection'] = True
                                    diagnostic_results['permissions'] = True
                                    st.session_state.connection_test_done = True
                                    st.session_state.connection_test_results = diagnostic_results.copy()
                                except Exception as e:
                                    st.error(f"❌ **שגיאה בקריאת נתונים:** {str(e)}")
                                    diagnostic_results['connection'] = False
                                    st.session_state.connection_test_done = True
                                    st.session_state.connection_test_results = diagnostic_results.copy()
                            except Exception as e:
                                st.error(f"❌ **שגיאה בטעינת גיליון עבודה:** {str(e)}")
                                diagnostic_results['connection'] = False
                                st.session_state.connection_test_done = True
                                st.session_state.connection_test_results = diagnostic_results.copy()
                        except gspread.exceptions.SpreadsheetNotFound:
                            st.error(f"❌ **גיליון לא נמצא:** `{SHEET_NAME}`")
                            st.info("💡 **פתרון:** ודא שהגיליון קיים ושם חשבון השירות יש לו גישה אליו")
                            diagnostic_results['connection'] = False
                            st.session_state.connection_test_done = True
                            st.session_state.connection_test_results = diagnostic_results.copy()
                        except gspread.exceptions.APIError as e:
                            error_msg = str(e)
                            if "PERMISSION_DENIED" in error_msg or "403" in error_msg:
                                st.error(f"❌ **אין הרשאות לגיליון:** {error_msg}")
                                st.info("💡 **פתרון:** שתף את הגיליון עם חשבון השירות:")
                                if creds_dict and 'client_email' in creds_dict:
                                    service_email = creds_dict.get('client_email', 'חשבון השירות')
                                    st.code(f"1. פתח את הגיליון ב-Google Sheets\n2. לחץ על 'שתף' (Share)\n3. הוסף את: {service_email}\n4. תן הרשאות 'עורך' (Editor)")
                                else:
                                    st.code("1. פתח את הגיליון ב-Google Sheets\n2. לחץ על 'שתף' (Share)\n3. הוסף את כתובת האימייל של חשבון השירות\n4. תן הרשאות 'עורך' (Editor)")
                                diagnostic_results['permissions'] = False
                                st.session_state.connection_test_done = True
                                st.session_state.connection_test_results = diagnostic_results.copy()
                            else:
                                st.error(f"❌ **שגיאת API:** {error_msg}")
                                diagnostic_results['connection'] = False
                                st.session_state.connection_test_done = True
                                st.session_state.connection_test_results = diagnostic_results.copy()
                    except Exception as e:
                        error_type = type(e).__name__
                        error_str = str(e)
                        st.error(f"❌ **שגיאה בחיבור ({error_type}):** {error_str}")
                        
                        # Show detailed error info
                        with st.expander("🔍 פרטי שגיאה מפורטים"):
                            import traceback
                            st.code(traceback.format_exc())
                            st.write("**סוג שגיאה:**", error_type)
                            st.write("**הודעת שגיאה:**", error_str)
                        
                        diagnostic_results['connection'] = False
                        st.session_state.connection_test_done = True
                        st.session_state.connection_test_results = diagnostic_results.copy()
                
                # Clear refresh flag
                if 'refresh_connection_test' in st.session_state:
                    del st.session_state.refresh_connection_test
            else:
                # Show cached results
                cached_results = st.session_state.get('connection_test_results', {})
                if cached_results.get('connection'):
                    st.success("✅ **חיבור אומת בהצלחה** (תוצאות מבדיקה קודמת)")
                elif cached_results.get('connection') == False:
                    st.warning("⚠️ **נמצאו בעיות בחיבור** (תוצאות מבדיקה קודמת)")
                
                if st.button("🔄 בדוק שוב", key="retry_connection_test"):
                    st.session_state.refresh_connection_test = True
                    st.rerun()
        else:
            st.warning("⚠️ **לא ניתן לבדוק חיבור - GOOGLE_CREDENTIALS לא תקין**")
        
        st.markdown("---")
        
        # 4. Check Resend credentials
        st.subheader("4️⃣ בדיקת פרטי Resend")
        try:
            if hasattr(st, 'secrets'):
                # Check if Resend secrets exist
                has_resend_key = 'RESEND_API_KEY' in st.secrets
                has_resend_email = 'RESEND_FROM_EMAIL' in st.secrets
                
                if has_resend_key and has_resend_email:
                    api_key = st.secrets.get('RESEND_API_KEY', '') or getattr(st.secrets, 'RESEND_API_KEY', '')
                    from_email = st.secrets.get('RESEND_FROM_EMAIL', '') or getattr(st.secrets, 'RESEND_FROM_EMAIL', '')
                    
                    if api_key and from_email:
                        # Mask the API key for security
                        masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
                        st.success(f"✅ **Resend credentials נמצאו**")
                        st.info(f"**API Key:** `{masked_key}`\n**From Email:** `{from_email}`")
                        diagnostic_results['resend'] = True
                    else:
                        st.warning("⚠️ **Resend credentials נמצאו אבל ריקים**")
                        st.info("ודא שה-RESEND_API_KEY ו-RESEND_FROM_EMAIL מכילים ערכים")
                        diagnostic_results['resend'] = False
                else:
                    missing = []
                    if not has_resend_key:
                        missing.append("RESEND_API_KEY")
                    if not has_resend_email:
                        missing.append("RESEND_FROM_EMAIL")
                    st.error(f"❌ **חסרים פרטי Resend:** {', '.join(missing)}")
                    st.info("💡 **פתרון:** הוסף ב-Streamlit Secrets:\n```toml\nRESEND_API_KEY = \"re_...\"\nRESEND_FROM_EMAIL = \"info@tiktik.co.il\"\n```")
                    diagnostic_results['resend'] = False
            else:
                st.warning("⚠️ **לא ניתן לגשת ל-Streamlit Secrets**")
                diagnostic_results['resend'] = False
        except Exception as e:
            st.error(f"❌ **שגיאה בבדיקת Resend:** {str(e)}")
            diagnostic_results['resend'] = False
        
        st.markdown("---")
        
        # 5. Summary
        st.subheader("📋 סיכום אבחון")
        all_ok = all(diagnostic_results.values()) if diagnostic_results else False
        
        if all_ok:
            st.success("✅ **כל הבדיקות עברו בהצלחה!**")
        else:
            st.warning("⚠️ **נמצאו בעיות שצריך לפתור:**")
            for check, status in diagnostic_results.items():
                icon = "✅" if status else "❌"
                check_names = {
                    'credentials': 'משתנה הסביבה GOOGLE_CREDENTIALS',
                    'sheet_name': 'שם הגיליון',
                    'connection': 'חיבור ל-Google Sheets',
                    'permissions': 'הרשאות לגיליון',
                    'resend': 'פרטי Resend'
                }
                st.write(f"{icon} {check_names.get(check, check)}: {'תקין' if status else 'בעיה'}")
    
    st.info("💡 **טיפים לפתרון בעיות:**")
    st.markdown("""
    1. **בדוק את משתנה הסביבה GOOGLE_CREDENTIALS** - ודא שהוא מוגדר ב-Streamlit Cloud Secrets
    2. **ודא ששם הגיליון נכון** - השם צריך להיות בדיוק: `מערכת הזמנות - קוד יהודה  ` (עם רווחים בסוף)
    3. **בדוק הרשאות** - ודא שחשבון השירות של Google יש לו גישה לעריכה בגיליון
    4. **נסה לרענן** - לחץ על כפתור "🔄 רענן נתונים" בסרגל הצד
    5. **נקה את ה-cache** - אם הבעיה נמשכת, נסה לנקות את ה-cache של הנתונים
    """)
    
    # Add button to clear cache and retry
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 נסה שוב", key="retry_load", use_container_width=True):
            load_data_from_sheet.clear()
            if 'sheet_error' in st.session_state:
                del st.session_state.sheet_error
            st.rerun()
    with col2:
        if st.button("🗑️ נקה cache ונסה שוב", key="clear_cache_retry", use_container_width=True):
            load_data_from_sheet.clear()
            if 'sheet_error' in st.session_state:
                del st.session_state.sheet_error
            st.cache_data.clear()
            st.rerun()
    
    st.stop()

now = datetime.now()
status_col = 'orderd' if 'orderd' in df.columns else None

df['has_supplier_data'] = df.apply(has_supplier_data, axis=1)

supp_name_col = 'Supplier NAME' if 'Supplier NAME' in df.columns else None
supp_order_col = None
for col in df.columns:
    if 'supp' in col.lower() and 'order' in col.lower():
        supp_order_col = col
        break

week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
week_end = week_start + timedelta(days=7)

total_orders = len(df)
total_tickets = pd.to_numeric(df.get('Qty', 0), errors='coerce').sum()
total_sales = df['TOTAL_clean'].sum()
total_supp_cost = df[df['has_supplier_data'] == True]['SUPP_PRICE_clean'].sum()
total_profit = df[df['has_supplier_data'] == True]['profit'].sum()
profit_pct = (total_profit / total_sales * 100) if total_sales > 0 else 0

new_count = len(df[df[status_col].fillna('').str.lower().str.strip() == 'new']) if status_col else 0
orderd_count = len(df[df[status_col].fillna('').str.lower().str.strip() == 'orderd']) if status_col else 0
done_count = len(df[df[status_col].fillna('').str.lower().str.strip().isin(['done!', 'done'])]) if status_col else 0
needs_attention = len(df[(df['has_supplier_data'] == False) & (df[status_col].fillna('').str.lower().str.strip() == 'new')]) if status_col else 0

if 'dashboard_filter' not in st.session_state:
    st.session_state.dashboard_filter = None

st.markdown("### 📊 סיכום כללי")
main_cols = st.columns(4)
with main_cols[0]:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 15px; text-align: center; color: white;">
        <p style="margin:0; font-size: 14px; opacity: 0.9;">📦 הזמנות</p>
        <p style="font-size: 32px; margin: 5px 0; font-weight: bold;">{total_orders:,}</p>
        <p style="margin:0; font-size: 12px; opacity: 0.8;">סה"כ</p>
    </div>
    """, unsafe_allow_html=True)
with main_cols[1]:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 15px; text-align: center; color: white;">
        <p style="margin:0; font-size: 14px; opacity: 0.9;">🎫 כרטיסים</p>
        <p style="font-size: 32px; margin: 5px 0; font-weight: bold;">{int(total_tickets):,}</p>
        <p style="margin:0; font-size: 12px; opacity: 0.8;">סה"כ</p>
    </div>
    """, unsafe_allow_html=True)
with main_cols[2]:
    sales_display = f"€{total_sales/1000:,.0f}K" if total_sales >= 1000 else f"€{total_sales:,.0f}"
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 20px; border-radius: 15px; text-align: center; color: white;">
        <p style="margin:0; font-size: 14px; opacity: 0.9;">💰 מכירות</p>
        <p style="font-size: 32px; margin: 5px 0; font-weight: bold;">{sales_display}</p>
        <p style="margin:0; font-size: 12px; opacity: 0.8;">סה"כ</p>
    </div>
    """, unsafe_allow_html=True)
with main_cols[3]:
    profit_display = f"€{total_profit/1000:,.0f}K" if total_profit >= 1000 else f"€{total_profit:,.0f}"
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); padding: 20px; border-radius: 15px; text-align: center; color: white;">
        <p style="margin:0; font-size: 14px; opacity: 0.9;">📈 רווח</p>
        <p style="font-size: 32px; margin: 5px 0; font-weight: bold;">{profit_display}</p>
        <p style="margin:0; font-size: 12px; opacity: 0.8;">{profit_pct:.1f}%</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("### 📋 סטטוס הזמנות")
status_cols = st.columns(4)
with status_cols[0]:
    if st.button(f"🆕 חדש\n{new_count}", key="btn_new", use_container_width=True):
        st.session_state.dashboard_filter = 'new'
        st.rerun()
    st.markdown(f"<p style='text-align:center; color: #666;'>{new_count/total_orders*100:.1f}%</p>" if total_orders > 0 else "", unsafe_allow_html=True)
with status_cols[1]:
    if st.button(f"🎯 הוזמן\n{orderd_count}", key="btn_orderd", use_container_width=True):
        st.session_state.dashboard_filter = 'orderd'
        st.rerun()
    st.markdown(f"<p style='text-align:center; color: #666;'>{orderd_count/total_orders*100:.1f}%</p>" if total_orders > 0 else "", unsafe_allow_html=True)
with status_cols[2]:
    if st.button(f"✅ בוצע\n{done_count}", key="btn_done", use_container_width=True):
        st.session_state.dashboard_filter = 'done!'
        st.rerun()
    st.markdown(f"<p style='text-align:center; color: #666;'>{done_count/total_orders*100:.1f}%</p>" if total_orders > 0 else "", unsafe_allow_html=True)
with status_cols[3]:
    if st.button(f"⚠️ דורש טיפול\n{needs_attention}", key="btn_attention", use_container_width=True, type="primary" if needs_attention > 0 else "secondary"):
        st.session_state.dashboard_filter = 'needs_attention'
        st.rerun()

next_7_days_df = pd.DataFrame()
waiting_supplier_df = pd.DataFrame()
if 'parsed_date' in df.columns:
    next_7_days_df = df[
        (df['parsed_date'].notna()) &
        (df['parsed_date'] >= now) &
        (df['parsed_date'] <= week_end)
    ].copy()
    next_7_missing = next_7_days_df[next_7_days_df['has_supplier_data'] == False]
else:
    next_7_missing = pd.DataFrame()

if supp_name_col and supp_order_col:
    waiting_supplier_df = df[
        (df[supp_name_col].fillna('').str.strip() != '') &
        (df[supp_order_col].fillna('').str.strip() == '')
    ].copy()

st.markdown("### 🔔 התראות")

urgent_count = 0
if status_col and 'parsed_date' in df.columns:
    new_orders = df[df[status_col].fillna('').str.lower().str.strip() == 'new']
    if not new_orders.empty:
        upcoming_48h = new_orders[
            (new_orders['parsed_date'].notna()) &
            (new_orders['parsed_date'] <= now + timedelta(hours=48)) &
            (new_orders['parsed_date'] >= now)
        ]
        urgent_count = len(upcoming_48h)

missing_7days = len(next_7_missing) if not next_7_missing.empty else 0
waiting_count = len(waiting_supplier_df) if not waiting_supplier_df.empty else 0

alert_items = []
if urgent_count > 0:
    alert_items.append(f"🚨 {urgent_count} הזמנות ב-48 שעות הקרובות!")
if missing_7days > 0:
    alert_items.append(f"📅 {missing_7days} הזמנות ב-7 ימים חסרות קנייה")
if waiting_count > 0:
    alert_items.append(f"⏳ {waiting_count} הזמנות ממתינות לאישור ספק")

count_7days = len(next_7_days_df) if not next_7_days_df.empty else 0

if not next_7_days_df.empty and 'event name' in next_7_days_df.columns:
    week_events_grouped = next_7_days_df.groupby('event name').agg({
        'Date of the event': 'first',
        'parsed_date': 'first',
        'row_index': 'first'
    }).reset_index()
    week_events_grouped = week_events_grouped.sort_values('parsed_date')
    week_events_unique = len(week_events_grouped)
else:
    week_events_grouped = pd.DataFrame()
    week_events_unique = 0

col1, col2 = st.columns(2)

with col1:
    alert_count = len(alert_items) if alert_items else 0
    with st.expander(f"🔔 התראות דחופות ({alert_count})", expanded=True):
        if alert_items:
            for item in alert_items:
                st.markdown(item)
        else:
            st.markdown("✅ אין התראות דחופות")

with col2:
    with st.expander(f"📅 השבוע הקרוב ({week_events_unique} אירועים)", expanded=False):
        if not week_events_grouped.empty:
            for idx, row in week_events_grouped.iterrows():
                event_name = row.get('event name', '')
                event_date = row.get('Date of the event', '')
                
                event_orders = next_7_days_df[next_7_days_df['event name'] == event_name]
                has_supp_count = event_orders['has_supplier_data'].sum() if 'has_supplier_data' in event_orders.columns else 0
                total_count = len(event_orders)
                order_count = len(event_orders)
                
                sources = event_orders['source'].dropna().unique() if 'source' in event_orders.columns else []
                sources_str = ", ".join([get_source_display_name(s) for s in sources[:3]])
                if len(sources) > 3:
                    sources_str += "..."
                
                order_nums = event_orders['Order number'].dropna().unique() if 'Order number' in event_orders.columns else []
                order_nums_str = ", ".join([str(int(o)) if pd.notna(o) else str(o) for o in order_nums[:3]])
                if len(order_nums) > 3:
                    order_nums_str += "..."
                
                if has_supp_count == total_count:
                    icon = "✅"
                elif has_supp_count > 0:
                    icon = "🟡"
                else:
                    icon = "🔴"
                
                display_name = event_name[:35] + "..." if len(event_name) > 35 else event_name
                
                btn_col1, btn_col2 = st.columns([3, 2])
                with btn_col1:
                    if st.button(f"{icon} {display_name}", key=f"alert_event_{idx}", use_container_width=True):
                        st.session_state.selected_alert_event = event_name
                        st.session_state.dashboard_filter = None
                        st.session_state.purchase_filters = {
                            'date_range': 'הכל',
                            'urgency': [],
                            'amount': 'הכל',
                            'teams': [],
                            'suppliers': [],
                            'search': event_name[:25]
                        }
                        st.session_state.show_all_statuses_for_event = True
                        st.rerun()
                with btn_col2:
                    st.caption(f"📅 {event_date[:10]} | 🎫 {order_nums_str}")
                    if sources_str:
                        st.caption(f"📍 {sources_str}")
        else:
            st.markdown("אין אירועים השבוע")

st.markdown("---")

# Show success message if order was just added
if st.session_state.get('order_added_success'):
    st.success(st.session_state.order_added_success)
    st.session_state.order_added_success = None

# Manual order form - opens in main screen when button clicked in sidebar
if st.session_state.get('show_manual_order_form', False):
    with st.container():
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 15px; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0; text-align: center;">➕ הוספה ידנית של הזמנה</h2>
        </div>
        """, unsafe_allow_html=True)
        
        form_col1, form_col2, form_col3 = st.columns(3)
        
        add_current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M")
        add_status = "\u200f🔴 חדש\u200f"
        
        temp_df = load_data_from_sheet()
        
        status_display_to_storage = {
            "🔴 חדש": "new",
            "📦 הוזמן": "orderd",
            "✅ הושלם": "done",
            "🟠 נשלח ולא שולם": "sent - not paid",
            "💚 נשלח ושולם": "sent - paid"
        }
        
        with form_col1:
            st.markdown("**📅 פרטי הזמנה**")
            st.caption(f"תאריך: {add_current_datetime}")
            
            status_options = ["🔴 חדש", "📦 הוזמן", "✅ הושלם", "🟠 נשלח ולא שולם", "💚 נשלח ושולם"]
            add_status_selected = st.selectbox("סטטוס:", status_options, key="main_status")
            
            if add_status_selected == "💚 נשלח ושולם":
                add_payment_method = st.text_input(
                    "שולם ב:",
                    placeholder="PayPal, העברה בנקאית, כרטיס אשראי...",
                    key="main_payment_method"
                )
                add_status = f"paid via {add_payment_method}" if add_payment_method else status_display_to_storage[add_status_selected]
            else:
                add_payment_method = ""
                add_status = status_display_to_storage.get(add_status_selected, "new")
            
            add_source_mode = st.radio("מקור:", ["בחר קיים", "הזנה ידנית"], horizontal=True, key="main_source_mode")
            add_sources = get_unique_sources_list(temp_df) if not temp_df.empty else []
            
            if add_source_mode == "בחר קיים":
                add_source = st.selectbox("מקור:", ["-- בחר --"] + add_sources, key="main_source")
                add_final_source = "" if add_source == "-- בחר --" else add_source
            else:
                add_final_source = st.text_input("מקור:", placeholder="WhatsApp, Telegram", key="main_source_manual")
        
        with form_col2:
            st.markdown("**🎫 פרטי אירוע**")
            add_events = get_unique_events_dict(temp_df) if not temp_df.empty else {}
            last_manual_event = st.session_state.get('manual_order_last_event', None)
            sorted_event_keys = get_sorted_event_options(temp_df, last_selected=last_manual_event) if not temp_df.empty else []
            sorted_event_keys = [e for e in sorted_event_keys if e in add_events]
            add_event_options = ["-- בחר אירוע קיים --"] + sorted_event_keys + ["➕ חדש"]
            add_selected_event = st.selectbox("🎫 שם אירוע:", add_event_options, key="main_event")
            
            if add_selected_event == "➕ חדש":
                add_event_name = st.text_input("שם אירוע:", key="main_new_event")
                add_event_date = st.text_input("תאריך אירוע:", placeholder="DD/MM/YYYY", key="main_event_date")
            elif add_selected_event == "-- בחר אירוע קיים --":
                add_event_name = ""
                add_event_date = ""
            else:
                add_event_name = add_selected_event
                add_event_date = add_events.get(add_selected_event, "")
                st.caption(f"📅 {add_event_date}")
            
            add_cat_mode = st.radio("קטגוריה:", ["בחר", "ידני"], horizontal=True, key="main_cat_mode")
            add_cats = ["CAT 1", "CAT 2", "CAT 3", "CAT 4", "VIP", "PREMIUM", "LONGSIDE"]
            
            if add_cat_mode == "בחר":
                add_category = st.selectbox("קטגוריה:", ["-- בחר --"] + add_cats, key="main_cat")
                if add_category == "-- בחר --":
                    add_category = ""
            else:
                add_category = st.text_input("קטגוריה:", key="main_cat_manual")
        
        with form_col3:
            st.markdown("**💰 מספרים ומחיר**")
            add_order_num = generate_order_number(temp_df) if not temp_df.empty else "1"
            add_order_number = st.text_input("מספר הזמנה:", value=add_order_num, key="main_order_num")
            add_docket = st.text_input("מספר דוקט:", placeholder="הזן דוקט", key="main_docket")
            
            add_qty = st.number_input("כמות:", min_value=1, value=1, key="main_qty")
            add_price = st.number_input("מחיר לכרטיס:", min_value=0.0, value=0.0, format="%.2f", key="main_price")
            add_currency = st.selectbox("מטבע:", ["€", "£", "$"], key="main_currency")
            
            add_total = add_qty * add_price
            st.markdown(f"### סה\"כ: {add_currency}{add_total:.2f}")
        
        st.markdown("---")
        
        file_col, copy_col = st.columns(2)
        with file_col:
            st.markdown("**📎 קובץ אישור תשלום (אופציונלי)**")
            add_payment_file = st.file_uploader(
                "העלה קובץ:",
                type=['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'],
                key="main_payment_file",
                help="העלה קובץ אישור תשלום - יישלח כמצורף במייל"
            )
            if add_payment_file:
                st.success(f"📎 קובץ נבחר: {add_payment_file.name}")
        
        with copy_col:
            st.markdown("**📋 העתקה מהירה**")
            order_summary = f"""מספר הזמנה: {add_order_number}
אירוע: {add_event_name}
תאריך אירוע: {add_event_date}
מקור: {add_final_source}
קטגוריה: {add_category}
כמות: {add_qty}
מחיר לכרטיס: {add_currency}{add_price:.2f}
סה"כ: {add_currency}{add_total:.2f}
סטטוס: {add_status}"""
            st.code(order_summary, language="text")
        
        st.markdown("---")
        btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
        
        with btn_col1:
            if st.button("✅ הוסף הזמנה", key="main_add_order", type="primary", use_container_width=True):
                submit_datetime = datetime.now().strftime("%d/%m/%Y %H:%M")
                if not add_event_name:
                    st.error("❌ בחר או הזן אירוע")
                elif not add_final_source:
                    st.error("❌ בחר או הזן מקור")
                elif add_price <= 0:
                    st.error("❌ הזן מחיר")
                else:
                    order_data = {
                        'order date': submit_datetime,
                        'orderd': add_status,
                        'source': add_final_source,
                        'Order number': add_order_number,
                        'docket number': add_docket,
                        'event name': add_event_name,
                        'Date of the event': add_event_date,
                        'Category / Section': add_category,
                        'Qty': add_qty,
                        'Price sold': f"{add_currency}{add_price:.2f}",
                        'TOTAL': f"{add_currency}{add_total:.2f}",
                    }
                    
                    with st.spinner("מוסיף..."):
                        success, message = add_new_order_to_sheet(order_data)
                        if success:
                            email_sent_msg = ""
                            
                            if add_status_selected == "🟠 נשלח ולא שולם":
                                email_success, email_message = send_not_paid_email([order_data])
                                if email_success:
                                    email_sent_msg = " + 🔴 מייל התראה נשלח לאופרציה!"
                                else:
                                    email_sent_msg = f" (מייל לא נשלח: {email_message})"
                            
                            elif add_status_selected == "💚 נשלח ושולם" and add_payment_method:
                                attachment_data = None
                                attachment_name = None
                                if add_payment_file:
                                    attachment_data = add_payment_file.read()
                                    attachment_name = add_payment_file.name
                                
                                email_success, email_message = send_payment_confirmation_email(
                                    [order_data],
                                    add_payment_method,
                                    attachment_data,
                                    attachment_name
                                )
                                if email_success:
                                    file_msg = " + קובץ" if attachment_data else ""
                                    email_sent_msg = f" + 💚 מייל אישור נשלח{file_msg}!"
                                else:
                                    email_sent_msg = f" (מייל לא נשלח: {email_message})"
                            
                            st.cache_data.clear()
                            st.session_state.show_manual_order_form = False
                            st.session_state.order_added_success = f"✅ הזמנה {add_order_number} נוספה בהצלחה{email_sent_msg}!"
                            if add_event_name:
                                st.session_state.manual_order_last_event = add_event_name
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
        
        with btn_col3:
            if st.button("❌ סגור", key="close_manual_form", use_container_width=True):
                st.session_state.show_manual_order_form = False
                st.rerun()
        
        st.markdown("---")

# Global search popup - opens in main screen when search is triggered from sidebar
if st.session_state.get('show_global_search', False) and st.session_state.get('sidebar_search_query', ''):
    with st.container():
        st.markdown("""
        <div style="background: linear-gradient(135deg, #00b4db 0%, #0083b0 100%); 
                    padding: 20px; border-radius: 15px; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0; text-align: center;">🔍 תוצאות חיפוש</h2>
        </div>
        """, unsafe_allow_html=True)
        
        search_col1, search_col2 = st.columns([3, 1])
        
        with search_col1:
            st.markdown(f"**מחפש:** `{st.session_state.sidebar_search_query}`")
        
        with search_col2:
            if st.button("❌ סגור חיפוש", key="close_global_search", use_container_width=True):
                st.session_state.show_global_search = False
                st.session_state.sidebar_search_query = ""
                st.rerun()
        
        global_search_query = st.session_state.sidebar_search_query
        if global_search_query and len(global_search_query) >= 2:
            search_df = load_data_from_sheet()
            if not search_df.empty:
                query_lower = global_search_query.lower().strip()
                
                results = search_df[
                    (search_df['Order number'].astype(str).str.lower().str.contains(query_lower, na=False)) |
                    (search_df['docket number'].astype(str).str.lower().str.contains(query_lower, na=False) if 'docket number' in search_df.columns else False) |
                    (search_df['event name'].astype(str).str.lower().str.contains(query_lower, na=False) if 'event name' in search_df.columns else False) |
                    (search_df['SUPP order number'].astype(str).str.lower().str.contains(query_lower, na=False) if 'SUPP order number' in search_df.columns else False)
                ]
                
                if not results.empty:
                    st.success(f"נמצאו {len(results)} תוצאות")
                    
                    for idx, row in results.iterrows():
                        order_num = row.get('Order number', '-')
                        event_name = row.get('event name', '-')
                        docket = row.get('docket number', '-')
                        supp_order = row.get('SUPP order number', '-')
                        event_date = row.get('Date of the event', '-')
                        status = row.get('orderd', '-')
                        source = row.get('source', '-')
                        category = row.get('Category / Section', '-')
                        qty = row.get('Qty', '-')
                        total = row.get('TOTAL', '-')
                        row_index = row.get('row_index', None)
                        
                        event_name_str = str(event_name) if event_name and str(event_name) != 'nan' else '-'
                        with st.expander(f"🎫 {order_num} | {event_name_str[:40]}..." if len(event_name_str) > 40 else f"🎫 {order_num} | {event_name_str}"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown(f"**מספר הזמנה:** {order_num}")
                                st.markdown(f"**מספר דוקט:** {docket}")
                                st.markdown(f"**הזמנת ספק:** {supp_order}")
                            with col2:
                                st.markdown(f"**אירוע:** {event_name}")
                                st.markdown(f"**תאריך:** {event_date}")
                                st.markdown(f"**קטגוריה:** {category}")
                            with col3:
                                st.markdown(f"**מקור:** {source}")
                                st.markdown(f"**כמות:** {qty}")
                                st.markdown(f"**סה״כ:** {total}")
                                st.markdown(f"**סטטוס:** {status}")
                            
                            st.markdown("---")
                            st.markdown("**🔄 שינוי סטטוס:**")
                            status_options = ['new', 'orderd', 'Done!', 'sent - not paid', 'old no data', 'cancelled']
                            current_status = str(status).strip() if status and str(status) != 'nan' else 'new'
                            current_idx = 0
                            for i, opt in enumerate(status_options):
                                if opt.lower() == current_status.lower():
                                    current_idx = i
                                    break
                            
                            status_col1, status_col2 = st.columns([2, 1])
                            with status_col1:
                                new_status = st.selectbox(
                                    "בחר סטטוס חדש:",
                                    options=status_options,
                                    index=current_idx,
                                    key=f"search_status_{order_num}_{idx}",
                                    label_visibility="collapsed"
                                )
                            with status_col2:
                                if st.button("עדכן", key=f"update_status_{order_num}_{idx}", use_container_width=True):
                                    if row_index:
                                        success = update_sheet_status([row_index], new_status)
                                        if success:
                                            st.success(f"סטטוס עודכן ל-{new_status}")
                                            st.rerun()
                                        else:
                                            st.error("שגיאה בעדכון הסטטוס")
                                    else:
                                        st.error("לא ניתן לעדכן - חסר מספר שורה")
                            
                            st.markdown("---")
                            st.markdown("**📋 העתקה מהירה:**")
                            copy_text = f"""מספר הזמנה: {order_num}
אירוע: {event_name}
תאריך: {event_date}
מספר דוקט: {docket}
הזמנת ספק: {supp_order}
מקור: {source}
קטגוריה: {category}
כמות: {qty}
סה"כ: {total}
סטטוס: {status}"""
                            st.code(copy_text, language="text")
                else:
                    st.warning("לא נמצאו תוצאות")
        elif global_search_query and len(global_search_query) < 2:
            st.info("הקלד לפחות 2 תווים לחיפוש")
        
        st.markdown("---")

st.markdown("""
<style>
.stTabs [data-baseweb="tab-list"] {
    direction: ltr !important;
    flex-direction: row-reverse !important;
}
.stTabs [data-baseweb="tab-list"] button {
    direction: rtl !important;
}
</style>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    t("tab1"),
    t("tab2"), 
    t("tab3"),
    "🆕 הזמנות חדשות",
    t("tab5"),
    "📊 השוואת מקורות",
    "📧 מיילים אוטומטיים"
])

with tab1:
    st.header(t("purchasing_header"))
    st.markdown(t("purchasing_subtitle"))
    
    # Event filter for purchasing center
    if 'tab1_selected_event' not in st.session_state:
        st.session_state.tab1_selected_event = None
    
    last_event_selected_tab1 = st.session_state.get('manual_order_last_event', None)
    event_options_tab1 = get_sorted_event_options(df, last_selected=last_event_selected_tab1)
    filter_col1, filter_col2 = st.columns([3, 1])
    with filter_col1:
        selected_event_tab1 = st.selectbox(
            "🎯 סנן לפי אירוע (מסודר לפי תאריך קרוב):",
            options=["כל האירועים"] + event_options_tab1,
            index=0,
            key="tab1_event_filter"
        )
        st.session_state.tab1_selected_event = selected_event_tab1 if selected_event_tab1 != "כל האירועים" else None
    with filter_col2:
        if st.session_state.tab1_selected_event:
            if st.button("🧹 נקה", key="clear_tab1_event"):
                st.session_state.tab1_selected_event = None
                if 'tab1_event_filter' in st.session_state:
                    del st.session_state['tab1_event_filter']
                st.rerun()
    
    st.markdown("---")
    
    if status_col:
        base_filtered_df = apply_filters(df)
        
        # Apply event filter if selected
        if st.session_state.tab1_selected_event and 'event name' in base_filtered_df.columns:
            base_filtered_df = base_filtered_df[base_filtered_df['event name'] == st.session_state.tab1_selected_event]
        
        today = pd.Timestamp.now().normalize()
        
        dashboard_filter = st.session_state.get('dashboard_filter', None)
        show_all_for_event = st.session_state.get('show_all_statuses_for_event', False)
        sidebar_status_selected = selected_status and selected_status != t("all_statuses")
        apply_filters_clicked = st.session_state.get('apply_filters_clicked', False)
        
        has_sidebar_filters = (
            (selected_sources and len(selected_sources) > 0) or
            (selected_teams and len(selected_teams) > 0) or
            (date_range is not None) or
            (selected_events and len(selected_events) > 0) or
            sidebar_status_selected
        )
        
        # בדיקה אם יש פילטרים שהופעלו על ידי כפתורי Quick Action
        active_quick = st.session_state.get('purchase_active_quick', '30days')
        applied_pf = st.session_state.get('applied_purchase_filters', None)
        
        # אם יש quick action פעיל שדורש טווח תאריכים רחב - השתמש בכל הנתונים
        # הכפתורים משתמשים ב-applied_purchase_filters לסינון אמיתי
        if active_quick in ['new', 'ordered', 'urgent', 'all']:
            base_orders_df = base_filtered_df.copy()
        elif active_quick == '7days':
            base_orders_df = base_filtered_df[
                (base_filtered_df['parsed_date'].notna()) & 
                (base_filtered_df['parsed_date'] >= today) & 
                (base_filtered_df['parsed_date'] <= today + timedelta(days=7))
            ].copy()
        elif show_all_for_event:
            base_orders_df = base_filtered_df.copy()
            st.session_state.show_all_statuses_for_event = False
        elif apply_filters_clicked and has_sidebar_filters:
            base_orders_df = base_filtered_df.copy()
        elif dashboard_filter:
            if dashboard_filter == 'new':
                base_orders_df = base_filtered_df[base_filtered_df[status_col].fillna('').str.lower().str.strip() == 'new'].copy()
            elif dashboard_filter == 'orderd':
                base_orders_df = base_filtered_df[base_filtered_df[status_col].fillna('').str.lower().str.strip() == 'orderd'].copy()
            elif dashboard_filter == 'done!':
                base_orders_df = base_filtered_df[base_filtered_df[status_col].fillna('').str.lower().str.strip().isin(['done!', 'done'])].copy()
            elif dashboard_filter == 'needs_attention':
                base_orders_df = base_filtered_df[(base_filtered_df['has_supplier_data'] == False) & (base_filtered_df[status_col].fillna('').str.lower().str.strip() == 'new')].copy()
            else:
                base_orders_df = base_filtered_df[
                    (base_filtered_df['parsed_date'].notna()) & 
                    (base_filtered_df['parsed_date'] >= today) & 
                    (base_filtered_df['parsed_date'] <= today + timedelta(days=30))
                ].copy()
        else:
            # ברירת מחדל: 30 ימים קדימה
            base_orders_df = base_filtered_df[
                (base_filtered_df['parsed_date'].notna()) & 
                (base_filtered_df['parsed_date'] >= today) & 
                (base_filtered_df['parsed_date'] <= today + timedelta(days=30))
            ].copy()
        
        total_base_orders = len(base_orders_df)
        base_grouped = group_orders_by_event(base_orders_df) if not base_orders_df.empty else {}
        total_base_events = len(base_grouped)
        
        st.markdown(f"### 🔥 מרכז רכישות | {total_base_events} אירועים | {total_base_orders} הזמנות")
        
        if 'purchase_filters' not in st.session_state:
            st.session_state.purchase_filters = get_default_filters() if 'get_default_filters' in dir() else {
                'date_range': '30 ימים קדימה', 'urgency': [], 'amount': 'הכל',
                'teams': [], 'suppliers': [], 'search': '', 'status': []
            }
        
        if 'applied_purchase_filters' not in st.session_state:
            st.session_state.applied_purchase_filters = st.session_state.purchase_filters.copy()
            st.session_state.filters_applied = True
        
        all_teams = set()
        all_suppliers = set()
        all_sources = set()
        if 'event name' in df.columns:
            for event in df['event name'].dropna().unique():
                teams = extract_teams(str(event))
                for team in teams:
                    if team:
                        all_teams.add(team.title())
        if 'Supplier NAME' in df.columns:
            for supp in df['Supplier NAME'].dropna().unique():
                if str(supp).strip():
                    all_suppliers.add(str(supp).strip())
        if 'source' in df.columns:
            for src in df['source'].dropna().unique():
                if str(src).strip():
                    all_sources.add(str(src).strip())
        
        if 'purchase_active_quick' not in st.session_state:
            st.session_state.purchase_active_quick = '30days'
        
        active_quick = st.session_state.purchase_active_quick
        
        # =============================================================
        # כפתורי Quick Action משופרים
        # רק הכפתור הפעיל יהיה אדום, השאר אפורים
        # =============================================================
        
        # CSS + JavaScript מותאם אישית לכפתורים
        st.markdown(f"""
        <style>
        /* כפתור פעיל - אדום בולט */
        button[kind="primary"][key="quick_7days"],
        button[kind="primary"][key="quick_urgent"] {{
            background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4) !important;
            font-weight: 700 !important;
            transform: scale(1.02);
            transition: all 0.2s ease;
        }}
        
        /* כפתור לא פעיל - אפור בהיר */
        button[kind="secondary"][key="quick_7days"],
        button[kind="secondary"][key="quick_urgent"] {{
            background: #f3f4f6 !important;
            color: #6b7280 !important;
            border: 1px solid #e5e7eb !important;
            font-weight: 500 !important;
            box-shadow: none !important;
            transition: all 0.2s ease;
        }}
        
        /* כפתור נקה - תמיד אפור בהיר */
        button[key="quick_clear"] {{
            background: #f9fafb !important;
            color: #9ca3af !important;
            border: 1px solid #d1d5db !important;
            font-weight: 400 !important;
            box-shadow: none !important;
        }}
        
        /* Hover effects */
        button[kind="secondary"][key="quick_7days"]:hover,
        button[kind="secondary"][key="quick_urgent"]:hover {{
            background: #e5e7eb !important;
            border-color: #d1d5db !important;
        }}
        
        button[key="quick_clear"]:hover {{
            background: #f3f4f6 !important;
        }}
        </style>
        
        <script>
        // סקריפט להבטחה שהכפתור הנכון מסומן באדום
        setTimeout(function() {{
            const activeQuick = '{active_quick}';
            
            // מצא את כל הכפתורים
            const buttons = parent.document.querySelectorAll('button[kind]');
            
            buttons.forEach(btn => {{
                const btnText = btn.textContent.trim();
                
                // כפתור 7 ימים
                if (btnText.includes('7 ימים')) {{
                    if (activeQuick === '7days') {{
                        btn.setAttribute('kind', 'primary');
                        btn.style.background = 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)';
                        btn.style.color = 'white';
                        btn.style.boxShadow = '0 4px 15px rgba(220, 38, 38, 0.4)';
                        btn.style.border = 'none';
                    }} else if (activeQuick === '30days') {{
                        btn.setAttribute('kind', 'secondary');
                        btn.style.background = '#f3f4f6';
                        btn.style.color = '#6b7280';
                        btn.style.boxShadow = 'none';
                        btn.style.border = '1px solid #e5e7eb';
                    }} else {{
                        btn.setAttribute('kind', 'secondary');
                        btn.style.background = '#f3f4f6';
                        btn.style.color = '#6b7280';
                        btn.style.boxShadow = 'none';
                        btn.style.border = '1px solid #e5e7eb';
                    }}
                }}
                
                // כפתור חדש
                if (btnText.includes('חדש') && !btnText.includes('7')) {{
                    if (activeQuick === 'new') {{
                        btn.setAttribute('kind', 'primary');
                        btn.style.background = 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)';
                        btn.style.color = 'white';
                        btn.style.boxShadow = '0 4px 15px rgba(220, 38, 38, 0.4)';
                        btn.style.border = 'none';
                    }} else {{
                        btn.setAttribute('kind', 'secondary');
                        btn.style.background = '#f3f4f6';
                        btn.style.color = '#6b7280';
                        btn.style.boxShadow = 'none';
                        btn.style.border = '1px solid #e5e7eb';
                    }}
                }}
                
                // כפתור הוזמן
                if (btnText.includes('הוזמן')) {{
                    if (activeQuick === 'ordered') {{
                        btn.setAttribute('kind', 'primary');
                        btn.style.background = 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)';
                        btn.style.color = 'white';
                        btn.style.boxShadow = '0 4px 15px rgba(37, 99, 235, 0.4)';
                        btn.style.border = 'none';
                    }} else {{
                        btn.setAttribute('kind', 'secondary');
                        btn.style.background = '#f3f4f6';
                        btn.style.color = '#6b7280';
                        btn.style.boxShadow = 'none';
                        btn.style.border = '1px solid #e5e7eb';
                    }}
                }}
                
                // כפתור דורש טיפול
                if (btnText.includes('דורש טיפול')) {{
                    if (activeQuick === 'urgent') {{
                        btn.setAttribute('kind', 'primary');
                        btn.style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
                        btn.style.color = 'white';
                        btn.style.boxShadow = '0 4px 15px rgba(245, 158, 11, 0.4)';
                        btn.style.border = 'none';
                    }} else {{
                        btn.setAttribute('kind', 'secondary');
                        btn.style.background = '#f3f4f6';
                        btn.style.color = '#6b7280';
                        btn.style.boxShadow = 'none';
                        btn.style.border = '1px solid #e5e7eb';
                    }}
                }}
                
                // כפתור הכל
                if (btnText.includes('הכל') && !btnText.includes('נקה')) {{
                    if (activeQuick === 'all') {{
                        btn.setAttribute('kind', 'primary');
                        btn.style.background = 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)';
                        btn.style.color = 'white';
                        btn.style.boxShadow = '0 4px 15px rgba(107, 114, 128, 0.4)';
                        btn.style.border = 'none';
                    }} else {{
                        btn.setAttribute('kind', 'secondary');
                        btn.style.background = '#f3f4f6';
                        btn.style.color = '#6b7280';
                        btn.style.boxShadow = 'none';
                        btn.style.border = '1px solid #e5e7eb';
                    }}
                }}
                
                // כפתור נקה - תמיד אפור
                if (btnText.includes('נקה')) {{
                    btn.setAttribute('kind', 'secondary');
                    btn.style.background = '#f9fafb';
                    btn.style.color = '#9ca3af';
                    btn.style.boxShadow = 'none';
                    btn.style.border = '1px solid #d1d5db';
                }}
            }});
        }}, 100);
        </script>
        """, unsafe_allow_html=True)
        
        st.markdown("### ⚡ גישה מהירה")
        quick_cols = st.columns(6)
        
        with quick_cols[0]:
            btn_7days = st.button(
                "🔥 7 ימים", 
                key="quick_7days", 
                use_container_width=True,
                help="הצג הזמנות ב-7 הימים הקרובים"
            )
        
        with quick_cols[1]:
            btn_new = st.button(
                "🆕 חדש", 
                key="quick_new", 
                use_container_width=True,
                help="הזמנות בסטטוס 'חדש' - טרם הוזמנו"
            )
        
        with quick_cols[2]:
            btn_ordered = st.button(
                "✅ הוזמן", 
                key="quick_ordered", 
                use_container_width=True,
                help="הזמנות בסטטוס 'הוזמן'"
            )
        
        with quick_cols[3]:
            btn_urgent = st.button(
                "⚠️ דורש טיפול", 
                key="quick_urgent", 
                use_container_width=True,
                help="הזמנות שחסרות נתוני ספק"
            )
        
        with quick_cols[4]:
            btn_show_all = st.button(
                "📋 הכל", 
                key="quick_show_all", 
                use_container_width=True,
                help="הצג את כל ההזמנות"
            )
        
        with quick_cols[5]:
            btn_clear = st.button(
                "🔄 נקה", 
                key="quick_clear", 
                use_container_width=True,
                help="נקה את כל הפילטרים"
            )
        
        import copy
        
        def get_default_filters():
            return {
                'date_range': '30 ימים קדימה', 'urgency': [], 'event': 'כל האירועים',
                'teams': [], 'suppliers': [], 'sources': [], 'search': '', 'status': []
            }
        
        def apply_quick_filter(quick_type, filters):
            st.session_state.purchase_active_quick = quick_type
            st.session_state.purchase_filters = copy.deepcopy(filters)
            st.session_state.applied_purchase_filters = copy.deepcopy(filters)
            st.rerun()
        
        if btn_7days:
            with st.spinner("טוען..."):
                filters = get_default_filters()
                filters['date_range'] = '7 ימים קדימה'
                filters['status'] = []
                apply_quick_filter('7days', filters)
        
        if btn_new:
            with st.spinner("טוען חדשים..."):
                filters = get_default_filters()
                filters['status'] = ['new']
                filters['date_range'] = '60 ימים אחורה'
                apply_quick_filter('new', filters)
        
        if btn_ordered:
            with st.spinner("טוען הוזמנו..."):
                filters = get_default_filters()
                filters['status'] = ['orderd']
                filters['date_range'] = '60 ימים אחורה'
                apply_quick_filter('ordered', filters)
        
        if btn_urgent:
            with st.spinner("טוען..."):
                filters = get_default_filters()
                filters['urgency'] = ["חסר מספר הזמנה", "חסר שם ספק", "חסר מחיר ספק"]
                filters['date_range'] = '90 ימים אחורה'
                apply_quick_filter('urgent', filters)
        
        if btn_show_all:
            with st.spinner("טוען הכל..."):
                filters = get_default_filters()
                filters['date_range'] = 'הכל'
                apply_quick_filter('all', filters)
        
        if btn_clear:
            with st.spinner("מנקה..."):
                filters = get_default_filters()
                st.session_state.dashboard_filter = None
                apply_quick_filter('30days', filters)
        
        # בדיקה אם צריך לנקות פילטרים (מה-run הקודם)
        if st.session_state.get('clear_filters_pending', False):
            new_filters = get_default_filters()
            st.session_state.purchase_active_quick = '30days'
            st.session_state.purchase_filters = copy.deepcopy(new_filters)
            st.session_state.applied_purchase_filters = copy.deepcopy(new_filters)
            st.session_state.dashboard_filter = None
            st.session_state.clear_filters_pending = False
        
        pf = st.session_state.purchase_filters
        
        # קבלת כל הסטטוסים האפשריים
        all_statuses = []
        if 'orderd' in df.columns:
            all_statuses = [str(s).strip() for s in df['orderd'].dropna().unique() if str(s).strip()]
        
        with st.container(border=True):
            filter_cols = st.columns([1, 1, 1, 2.5, 1, 1, 1, 1.5, 0.8])
            
            with filter_cols[0]:
                date_options = ["הכל", "7 ימים קדימה", "30 ימים קדימה", "60 ימים אחורה", "90 ימים אחורה", "טווח מותאם"]
                try:
                    date_idx = date_options.index(st.session_state.purchase_filters.get('date_range', '30 ימים קדימה'))
                except ValueError:
                    date_idx = 1
                date_filter = st.selectbox("📅 תאריך", date_options, index=date_idx, key="pf_date")
                st.session_state.purchase_filters['date_range'] = date_filter
                
                if date_filter == "טווח מותאם":
                    custom_start = st.date_input("מתאריך", key="pf_custom_start")
                    custom_end = st.date_input("עד תאריך", key="pf_custom_end")
                    st.session_state.purchase_filters['custom_dates'] = (custom_start, custom_end)
            
            with filter_cols[1]:
                status_options = ["הכל"] + all_statuses
                current_status = st.session_state.purchase_filters.get('status', [])
                if isinstance(current_status, list) and len(current_status) > 0:
                    default_status = current_status[0] if current_status[0] in status_options else "הכל"
                else:
                    default_status = "הכל"
                try:
                    status_idx = status_options.index(default_status)
                except ValueError:
                    status_idx = 0
                status_filter = st.selectbox("📊 סטטוס", status_options, index=status_idx, key="pf_status")
                st.session_state.purchase_filters['status'] = [status_filter] if status_filter != "הכל" else []
            
            with filter_cols[2]:
                urgency_options = ["חסר מספר הזמנה", "חסר שם ספק", "חסר מחיר ספק"]
                urgency_filter = st.multiselect("⚠️ דחיפות", urgency_options, 
                    default=st.session_state.purchase_filters.get('urgency', []),
                    key="pf_urgency")
                st.session_state.purchase_filters['urgency'] = urgency_filter
            
            with filter_cols[3]:
                last_event_selected = st.session_state.get('manual_order_last_event', None)
                pf_event_options = ["כל האירועים"] + get_sorted_event_options(df, last_selected=last_event_selected)
                current_pf_event = st.session_state.purchase_filters.get('event', 'כל האירועים')
                try:
                    pf_event_idx = pf_event_options.index(current_pf_event) if current_pf_event in pf_event_options else 0
                except ValueError:
                    pf_event_idx = 0
                event_filter = st.selectbox("🎯 אירוע", pf_event_options, index=pf_event_idx, key="pf_event")
                st.session_state.purchase_filters['event'] = event_filter
            
            with filter_cols[4]:
                teams_filter = st.multiselect("⚽ קבוצות", sorted(list(all_teams)),
                    default=[t for t in st.session_state.purchase_filters.get('teams', []) if t in all_teams],
                    key="pf_teams")
                st.session_state.purchase_filters['teams'] = teams_filter
            
            with filter_cols[5]:
                supplier_options = ["ללא ספק"] + sorted(list(all_suppliers))
                suppliers_filter = st.multiselect("📦 ספקים", supplier_options,
                    default=[s for s in st.session_state.purchase_filters.get('suppliers', []) if s in supplier_options],
                    key="pf_suppliers")
                st.session_state.purchase_filters['suppliers'] = suppliers_filter
            
            with filter_cols[6]:
                sources_filter = st.multiselect("🏷️ מקור", sorted(list(all_sources)),
                    default=[s for s in st.session_state.purchase_filters.get('sources', []) if s in all_sources],
                    key="pf_sources")
                st.session_state.purchase_filters['sources'] = sources_filter
            
            with filter_cols[7]:
                search_filter = st.text_input("🔎 חיפוש", 
                    value=st.session_state.purchase_filters.get('search', ''),
                    placeholder="חפש משחק / הזמנה / ספק...",
                    key="pf_search")
                st.session_state.purchase_filters['search'] = search_filter
            
            with filter_cols[8]:
                # ספירת פילטרים פעילים (ללא Quick Actions)
                active_filters_count = 0
                if pf.get('date_range', 'הכל') != 'הכל' and pf.get('date_range', 'הכל') != '30 ימים קדימה':
                    active_filters_count += 1
                if len(pf.get('urgency', [])) > 0 and active_quick != 'urgent':
                    active_filters_count += 1
                if pf.get('event', 'כל האירועים') != 'כל האירועים':
                    active_filters_count += 1
                if len(pf.get('teams', [])) > 0:
                    active_filters_count += 1
                if len(pf.get('suppliers', [])) > 0:
                    active_filters_count += 1
                if len(pf.get('sources', [])) > 0:
                    active_filters_count += 1
                if pf.get('search', '').strip() != '':
                    active_filters_count += 1
                
                # הצגת מספר פילטרים פעילים
                if active_filters_count > 0:
                    st.caption(f"🔍 {active_filters_count} פילטרים פעילים")
                
                # כפתורים - הצג תוצאות + נקה הכל
                btn_cols = st.columns(2)
                with btn_cols[0]:
                    if st.button("🚀 הצג", key="apply_filters_inline", use_container_width=True, type="primary"):
                        with st.spinner("מסנן..."):
                            import copy
                            st.session_state.applied_purchase_filters = copy.deepcopy(st.session_state.purchase_filters)
                            st.session_state.filters_applied = True
                            st.session_state.purchase_active_quick = None
                            st.rerun()
                
                with btn_cols[1]:
                    if st.button("🔄 נקה", key="clear_filters_inline", use_container_width=True):
                        st.session_state.clear_filters_pending = True
                        st.rerun()
        
        st.markdown("---")
        
        # =============================================================
        # החלת פילטרים - משתמשים רק ב-applied_purchase_filters!
        # זה מונע מהפילטרים להיות מופעלים לפני לחיצה על הכפתור
        # =============================================================
        
        # השתמש בפילטרים שהופעלו (לא הנוכחיים בתפריט)
        applied_pf = st.session_state.get('applied_purchase_filters', get_default_filters())
        current_pf = st.session_state.purchase_filters
        
        # בדיקה אם הפילטרים הנוכחיים שונים מהמופעלים
        filters_changed = (
            current_pf.get('date_range') != applied_pf.get('date_range') or
            current_pf.get('teams', []) != applied_pf.get('teams', []) or
            current_pf.get('suppliers', []) != applied_pf.get('suppliers', []) or
            current_pf.get('sources', []) != applied_pf.get('sources', []) or
            current_pf.get('urgency', []) != applied_pf.get('urgency', []) or
            current_pf.get('event', 'כל האירועים') != applied_pf.get('event', 'כל האירועים') or
            current_pf.get('search', '').strip() != applied_pf.get('search', '').strip() or
            current_pf.get('status', []) != applied_pf.get('status', [])
        )
        
        # הודעה אם יש פילטרים שטרם הופעלו
        if filters_changed:
            st.info("💡 שינית פילטרים - לחץ על '🚀 הצג' כדי להפעיל")
        
        # בדיקה אם יש פילטרים פעילים מעבר ל-30 ימים קדימה
        has_active_filters = (
            applied_pf.get('date_range', '30 ימים קדימה') != '30 ימים קדימה' or
            len(applied_pf.get('teams', [])) > 0 or
            len(applied_pf.get('suppliers', [])) > 0 or
            len(applied_pf.get('sources', [])) > 0 or
            len(applied_pf.get('urgency', [])) > 0 or
            applied_pf.get('event', 'כל האירועים') != 'כל האירועים' or
            applied_pf.get('search', '').strip() != '' or
            len(applied_pf.get('status', [])) > 0
        )
        
        # אם יש פילטרים פעילים - מתחילים מכל הנתונים
        if has_active_filters:
            new_orders_df = base_filtered_df.copy()
        else:
            new_orders_df = base_orders_df.copy()
        
        # השתמש ב-applied_pf לסינון (לא current_pf!)
        pf = applied_pf
        
        # מפעילים פילטרים (תמיד על applied_pf)
        if pf.get('date_range', 'הכל') != 'הכל' and 'parsed_date' in new_orders_df.columns:
            filter_now = datetime.now()
            today_date = filter_now.date()
            
            if pf.get('date_range') == '7 ימים קדימה':
                end_date = filter_now + timedelta(days=7)
                new_orders_df = new_orders_df[(new_orders_df['parsed_date'].notna()) & 
                    (new_orders_df['parsed_date'] >= filter_now) & 
                    (new_orders_df['parsed_date'] <= end_date)]
            elif pf.get('date_range') == '30 ימים קדימה':
                end_date = filter_now + timedelta(days=30)
                new_orders_df = new_orders_df[(new_orders_df['parsed_date'].notna()) & 
                    (new_orders_df['parsed_date'] >= filter_now) & 
                    (new_orders_df['parsed_date'] <= end_date)]
            elif pf.get('date_range') == '60 ימים אחורה':
                start_date = filter_now - timedelta(days=60)
                new_orders_df = new_orders_df[(new_orders_df['parsed_date'].notna()) & 
                    (new_orders_df['parsed_date'] >= start_date)]
            elif pf.get('date_range') == '90 ימים אחורה':
                start_date = filter_now - timedelta(days=90)
                new_orders_df = new_orders_df[(new_orders_df['parsed_date'].notna()) & 
                    (new_orders_df['parsed_date'] >= start_date)]
            elif pf.get('date_range') == 'טווח מותאם' and 'custom_dates' in pf:
                start, end = pf.get('custom_dates', (None, None))
                new_orders_df = new_orders_df[(new_orders_df['parsed_date'].notna()) & 
                    (new_orders_df['parsed_date'] >= datetime.combine(start, datetime.min.time())) & 
                    (new_orders_df['parsed_date'] <= datetime.combine(end, datetime.max.time()))]
        
        if pf.get('urgency'):
            urgency_mask = pd.Series([False] * len(new_orders_df), index=new_orders_df.index)
            if "חסר מספר הזמנה" in pf.get('urgency', []):
                supp_order_col_name = None
                for col in new_orders_df.columns:
                    if 'supp' in col.lower() and 'order' in col.lower():
                        supp_order_col_name = col
                        break
                if supp_order_col_name:
                    urgency_mask = urgency_mask | (new_orders_df[supp_order_col_name].fillna('').str.strip() == '')
            if "חסר שם ספק" in pf.get('urgency', []):
                if 'Supplier NAME' in new_orders_df.columns:
                    urgency_mask = urgency_mask | (new_orders_df['Supplier NAME'].fillna('').str.strip() == '')
            if "חסר מחיר ספק" in pf.get('urgency', []):
                if 'SUPP_PRICE_clean' in new_orders_df.columns:
                    urgency_mask = urgency_mask | (new_orders_df['SUPP_PRICE_clean'].fillna(0) == 0)
            new_orders_df = new_orders_df[urgency_mask]
        
        if pf.get('amount', 'הכל') != 'הכל' and 'TOTAL_clean' in new_orders_df.columns:
            if pf.get('amount') == 'מעל €5,000':
                new_orders_df = new_orders_df[new_orders_df['TOTAL_clean'] > 5000]
            elif pf.get('amount') == '€1,000 - €5,000':
                new_orders_df = new_orders_df[(new_orders_df['TOTAL_clean'] >= 1000) & (new_orders_df['TOTAL_clean'] <= 5000)]
            elif pf.get('amount') == 'מתחת €1,000':
                new_orders_df = new_orders_df[new_orders_df['TOTAL_clean'] < 1000]
        
        if pf.get('teams') and 'event name' in new_orders_df.columns:
            def has_matching_team(event_name):
                teams = extract_teams(str(event_name))
                for team in teams:
                    if team.title() in pf.get('teams', []):
                        return True
                return False
            new_orders_df = new_orders_df[new_orders_df['event name'].apply(has_matching_team)]
        
        if pf.get('suppliers'):
            if 'Supplier NAME' in new_orders_df.columns:
                if "ללא ספק" in pf.get('suppliers', []):
                    other_suppliers = [s for s in pf.get('suppliers', []) if s != "ללא ספק"]
                    if other_suppliers:
                        new_orders_df = new_orders_df[
                            (new_orders_df['Supplier NAME'].fillna('').str.strip() == '') |
                            (new_orders_df['Supplier NAME'].isin(other_suppliers))
                        ]
                    else:
                        new_orders_df = new_orders_df[new_orders_df['Supplier NAME'].fillna('').str.strip() == '']
                else:
                    new_orders_df = new_orders_df[new_orders_df['Supplier NAME'].isin(pf.get('suppliers', []))]
        
        # סינון לפי מקור (source)
        if pf.get('sources') and 'source' in new_orders_df.columns:
            new_orders_df = new_orders_df[new_orders_df['source'].isin(pf.get('sources', []))]
        
        # סינון לפי אירוע (event)
        if pf.get('event', 'כל האירועים') != 'כל האירועים' and 'event name' in new_orders_df.columns:
            new_orders_df = new_orders_df[new_orders_df['event name'] == pf.get('event', 'כל האירועים')]
        
        # סינון לפי סטטוס (orderd) - case insensitive
        if pf.get('status') and 'orderd' in new_orders_df.columns:
            status_lower = [s.lower() for s in pf.get('status', [])]
            new_orders_df = new_orders_df[new_orders_df['orderd'].fillna('').str.strip().str.lower().isin(status_lower)]
        
        # =============================================================
        # חיפוש משופר - מחפש גם בקבוצות!
        # לדוגמה: "Real Madrid" ימצא כל המשחקים של Real Madrid
        # =============================================================
        if pf.get('search'):
            search_term = pf.get('search', '').lower().strip()
            search_mask = pd.Series([False] * len(new_orders_df), index=new_orders_df.index)
            
            # חיפוש בשם האירוע
            if 'event name' in new_orders_df.columns:
                search_mask = search_mask | new_orders_df['event name'].fillna('').str.lower().str.contains(search_term, regex=False)
            
            # חיפוש במספר הזמנה
            if 'Order number' in new_orders_df.columns:
                search_mask = search_mask | new_orders_df['Order number'].fillna('').astype(str).str.lower().str.contains(search_term, regex=False)
            
            # חיפוש בשם ספק
            if 'Supplier NAME' in new_orders_df.columns:
                search_mask = search_mask | new_orders_df['Supplier NAME'].fillna('').str.lower().str.contains(search_term, regex=False)
            
            # חיפוש חכם בקבוצות (NEW!)
            # אם מחפשים "Real Madrid" - ימצא גם "Barcelona vs Real Madrid"
            if 'event name' in new_orders_df.columns:
                def event_contains_team(event_name):
                    if pd.isna(event_name):
                        return False
                    teams = extract_teams(str(event_name))
                    for team in teams:
                        if search_term in team.lower():
                            return True
                    return False
                
                team_search_mask = new_orders_df['event name'].apply(event_contains_team)
                search_mask = search_mask | team_search_mask
            
            new_orders_df = new_orders_df[search_mask]
        
        if dashboard_filter:
            if st.button("🔄 נקה סינון דשבורד", key="clear_filter"):
                st.session_state.dashboard_filter = None
                st.rerun()
            st.info(f"מסנן דשבורד פעיל: {dashboard_filter}")
        
        if not new_orders_df.empty and 'event name' in new_orders_df.columns:
            grouped_events = group_orders_by_event(new_orders_df)
            
            def get_sort_date(item):
                parsed = item[1].get('parsed_date_sort')
                if parsed is None:
                    return datetime.max
                return parsed
            sorted_events = sorted(grouped_events.items(), key=get_sort_date)
            
            filtered_events = len(sorted_events)
            filtered_orders = len(new_orders_df)
            
            if filtered_events < total_base_events or filtered_orders < total_base_orders:
                st.markdown(f"### 📊 מציג {filtered_events} מתוך {total_base_events} אירועים | {filtered_orders} מתוך {total_base_orders} הזמנות")
            else:
                st.markdown(f"### 📊 {filtered_events} אירועים | {filtered_orders} הזמנות")
            
            def get_status_style(status_val):
                """מחזיר צבע וסגנון לפי סטטוס"""
                status_lower = str(status_val).lower().strip()
                if status_lower == 'new':
                    return {'color': '#dc2626', 'bg': '#ffcdd2', 'icon': '🔴', 'text': 'חדש'}
                elif status_lower in ['ordered', 'orderd']:
                    return {'color': '#1565c0', 'bg': '#bbdefb', 'icon': '📦', 'text': 'הוזמן'}
                elif status_lower in ['done', 'done!']:
                    return {'color': '#2e7d32', 'bg': '#c8e6c9', 'icon': '✅', 'text': 'הושלם'}
                elif 'old' in status_lower or 'no data' in status_lower:
                    return {'color': '#616161', 'bg': '#f5f5f5', 'icon': '⚪', 'text': 'ללא נתונים'}
                else:
                    return {'color': '#f57c00', 'bg': '#ffe0b2', 'icon': '🟡', 'text': str(status_val)}
            
            for key, event_data in sorted_events:
                order_count = len(event_data['orders'])
                without_supp = event_data['without_supplier']
                with_supp = event_data['with_supplier']
                suppliers_list = list(event_data['suppliers'])
                
                orders_temp_df = pd.DataFrame(event_data['orders'])
                tickets_to_buy = 0
                if 'orderd' in orders_temp_df.columns and 'Qty' in orders_temp_df.columns:
                    new_orders = orders_temp_df[orders_temp_df['orderd'].fillna('').str.lower().str.strip() == 'new']
                    tickets_to_buy = pd.to_numeric(new_orders['Qty'], errors='coerce').fillna(0).sum()
                
                if tickets_to_buy > 0:
                    status_icon = "🔴"
                    border_color = "#dc2626"
                elif without_supp > 0:
                    status_icon = "🟡"
                    border_color = "#f59e0b"
                else:
                    status_icon = "✅"
                    border_color = "#16a34a"
                
                with st.container():
                    tickets_to_buy_html = f'<span style="color: #dc2626; font-weight: bold;">🛒 <strong>{int(tickets_to_buy)} כרטיסים לקנייה</strong></span>' if tickets_to_buy > 0 else '<span style="color: #16a34a;">✅ הכל נקנה</span>'
                    
                    st.markdown(f"""
                    <div style="border-left: 5px solid {border_color}; padding: 15px; margin: 15px 0; background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                            <h3 style="margin:0; color: #1f2937; font-weight: 600;">
                                {status_icon} {event_data['event_name']}
                            </h3>
                        </div>
                        <div style="display: flex; gap: 20px; margin-top: 10px; flex-wrap: wrap; font-size: 14px;">
                            <span style="color: #6b7280;">📅 <strong>{event_data['event_date']}</strong></span>
                            <span style="color: #6b7280;">🎫 <strong>{int(event_data['total_qty'])} כרטיסים</strong></span>
                            {tickets_to_buy_html}
                            <span style="color: #6b7280;">💰 <strong>€{event_data['total_sold']:,.0f}</strong></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    orders_df = pd.DataFrame(event_data['orders'])
                    
                    new_only_df = orders_df[orders_df['orderd'].fillna('').str.lower().str.strip() == 'new'] if 'orderd' in orders_df.columns else orders_df
                    display_category_summary(new_only_df, key_prefix=f"cat_{key}")
                    
                    with st.expander(f"📋 פירוט {order_count} הזמנות", expanded=True):
                        
                        display_cols = [
                            'order date',
                            'orderd',
                            'source',
                            'event name',
                            'Order number',
                            'docket number',
                            'Category / Section',
                            'Seating Arrangements',
                            'Qty',
                            'Price sold',
                            'total sold',
                            'SUPP PRICE',
                            'Supplier NAME',
                            'SUPP order number'
                        ]
                        available_cols = [col for col in display_cols if col in orders_df.columns]
                        
                        if available_cols:
                            display_df = orders_df[available_cols].copy()
                            display_df.insert(0, 'Select', False)
                            display_df['row_index'] = orders_df['row_index']
                            
                            if 'orderd' in display_df.columns:
                                def format_status(status_val):
                                    if pd.isna(status_val) or str(status_val).strip() == '':
                                        return ''
                                    status_lower = str(status_val).lower().strip()
                                    if status_lower == 'new':
                                        return '🔴 חדש'
                                    elif status_lower in ['ordered', 'orderd']:
                                        return '📦 הוזמן'
                                    elif status_lower in ['done', 'done!']:
                                        return '✅ הושלם'
                                    elif 'old' in status_lower or 'no data' in status_lower:
                                        return '⚪ ללא נתונים'
                                    elif 'נשלח ולא שולם' in str(status_val) or 'sent_not_paid' in status_lower or 'sent unpaid' in status_lower:
                                        return '🟠 נשלח ולא שולם'
                                    elif 'נשלח ושולם' in str(status_val) or 'sent_paid' in status_lower or 'שולם ב' in str(status_val):
                                        return '💚 נשלח ושולם'
                                    else:
                                        return f'🟡 {status_val}'
                                display_df['orderd'] = display_df['orderd'].apply(format_status)
                            
                            original_supp_price = display_df['SUPP PRICE'].copy() if 'SUPP PRICE' in display_df.columns else None
                            original_supp_name = display_df['Supplier NAME'].copy() if 'Supplier NAME' in display_df.columns else None
                            original_supp_order = display_df['SUPP order number'].copy() if 'SUPP order number' in display_df.columns else None
                            original_rows = display_df['row_index'].copy()
                            
                            editable_cols = ['SUPP PRICE', 'Supplier NAME', 'SUPP order number']
                            non_editable_cols = [col for col in ['Select'] + available_cols if col not in editable_cols and col != 'Select']
                            
                            column_config = {
                                "Select": st.column_config.CheckboxColumn("בחר", default=False),
                                "order date": st.column_config.TextColumn("תאריך הזמנה"),
                                "orderd": st.column_config.TextColumn("סטטוס"),
                                "source": st.column_config.TextColumn("מקור"),
                                "event name": st.column_config.TextColumn("אירוע"),
                                "Order number": st.column_config.TextColumn("מס' הזמנה"),
                                "docket number": st.column_config.TextColumn("דוקט"),
                                "Category / Section": st.column_config.TextColumn("קטגוריה"),
                                "Seating Arrangements": st.column_config.TextColumn("מושבים"),
                                "Qty": st.column_config.NumberColumn("כמות"),
                                "Price sold": st.column_config.NumberColumn("מחיר לכרטיס", format="€%.0f"),
                                "total sold": st.column_config.NumberColumn("סה\"כ מכירה", format="€%.0f"),
                                "SUPP PRICE": st.column_config.TextColumn("מחיר ספק"),
                                "Supplier NAME": st.column_config.TextColumn("שם ספק"),
                                "SUPP order number": st.column_config.TextColumn("מס' הזמנה ספק"),
                                "row_index": None,
                            }
                            
                            show_cols = ['Select'] + available_cols
                            
                            edited_df = st.data_editor(
                                display_df[show_cols + ['row_index']],
                                column_config=column_config,
                                disabled=non_editable_cols + ['row_index'],
                                hide_index=True,
                                use_container_width=True,
                                key=f"editor_{key}"
                            )
                            
                            btn_cols = st.columns([2, 2, 2, 1])
                            with btn_cols[0]:
                                if st.button(f"💾 שמור שינויים", key=f"save_{key}", type="secondary"):
                                    changes_made = 0
                                    for i in range(len(edited_df)):
                                        row_idx = int(original_rows.iloc[i]) if i < len(original_rows) else None
                                        if not row_idx:
                                            continue
                                        
                                        new_price = str(edited_df.iloc[i].get('SUPP PRICE', '')).strip() if 'SUPP PRICE' in edited_df.columns else None
                                        old_price = str(original_supp_price.iloc[i]).strip() if original_supp_price is not None and i < len(original_supp_price) else ''
                                        
                                        new_name = str(edited_df.iloc[i].get('Supplier NAME', '')).strip() if 'Supplier NAME' in edited_df.columns else None
                                        old_name = str(original_supp_name.iloc[i]).strip() if original_supp_name is not None and i < len(original_supp_name) else ''
                                        
                                        new_order = str(edited_df.iloc[i].get('SUPP order number', '')).strip() if 'SUPP order number' in edited_df.columns else None
                                        old_order = str(original_supp_order.iloc[i]).strip() if original_supp_order is not None and i < len(original_supp_order) else ''
                                        
                                        price_changed = (new_price is not None) and (new_price != old_price)
                                        name_changed = (new_name is not None) and (new_name != old_name)
                                        order_changed = (new_order is not None) and (new_order != old_order)
                                        
                                        if price_changed or name_changed or order_changed:
                                            success = update_supplier_data(
                                                row_idx,
                                                supp_price=new_price if price_changed else None,
                                                supp_name=new_name if name_changed else None,
                                                supp_order=new_order if order_changed else None
                                            )
                                            if success:
                                                changes_made += 1
                                    
                                    if changes_made > 0:
                                        st.cache_data.clear()
                                        st.success(f"✅ עודכנו {changes_made} שורות!")
                                        st.rerun()
                                    else:
                                        st.info("לא זוהו שינויים")
                            
                            with btn_cols[1]:
                                selected = edited_df[edited_df['Select'] == True]
                                if len(selected) > 0:
                                    if st.button(f"🛒 סמן {len(selected)} כהוזמן", key=f"mark_orderd_{key}", type="secondary"):
                                        row_indices = selected['row_index'].tolist()
                                        with st.spinner("מעדכן..."):
                                            success = update_sheet_status(row_indices, "orderd")
                                        if success:
                                            st.success(f"✅ עודכנו {len(row_indices)} הזמנות לסטטוס הוזמן!")
                                            st.cache_data.clear()
                                            st.rerun()
                            
                            with btn_cols[2]:
                                selected = edited_df[edited_df['Select'] == True]
                                if len(selected) > 0:
                                    if st.button(f"📤 סמן {len(selected)} כנשלח", key=f"mark_sent_{key}", type="primary"):
                                        row_indices = selected['row_index'].tolist()
                                        with st.spinner("מעדכן..."):
                                            success = update_sheet_status(row_indices, "done!")
                                        if success:
                                            st.success(f"✅ עודכנו {len(row_indices)} הזמנות לסטטוס נשלח!")
                                            st.cache_data.clear()
                                            st.rerun()
                                    
                                    if st.button(f"⚠️ נשלח ולא שולם ({len(selected)})", key=f"mark_sent_not_paid_{key}"):
                                        row_indices = selected['row_index'].tolist()
                                        orders_data = selected.to_dict('records')
                                        
                                        with st.spinner("מעדכן סטטוס ושולח מייל לאופרציה..."):
                                            status_success = update_sheet_status(row_indices, "sent_not_paid")
                                            
                                            if status_success:
                                                email_success, email_message = send_not_paid_email(orders_data)
                                                
                                                if email_success:
                                                    st.success(f"🔴 עודכנו {len(row_indices)} הזמנות + נשלח מייל התראה לאופרציה!")
                                                    st.info(f"📧 {email_message}")
                                                else:
                                                    st.warning(f"✅ סטטוס עודכן, אבל המייל לא נשלח: {email_message}")
                                                
                                                st.cache_data.clear()
                                                st.rerun()
                                    
                                    st.markdown("---")
                                    st.markdown("##### 💚 נשלח ושולם")
                                    
                                    pay_col1, pay_col2 = st.columns(2)
                                    with pay_col1:
                                        payment_method = st.text_input(
                                            "שולם ב:",
                                            placeholder="לדוגמה: PayPal, העברה בנקאית, כרטיס אשראי...",
                                            key=f"payment_method_{key}"
                                        )
                                    
                                    with pay_col2:
                                        uploaded_file = st.file_uploader(
                                            "📎 העלה אישור תשלום (אופציונלי):",
                                            type=['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'],
                                            key=f"payment_file_{key}",
                                            help="העלה קובץ אישור תשלום - יישלח כקובץ מצורף במייל"
                                        )
                                    
                                    if uploaded_file:
                                        st.success(f"📎 קובץ נבחר: {uploaded_file.name}")
                                    
                                    if st.button(f"💚 סמן {len(selected)} כנשלח ושולם", key=f"mark_sent_paid_{key}", type="primary", disabled=not payment_method):
                                        if payment_method and payment_method.strip():
                                            row_indices = selected['row_index'].tolist()
                                            orders_data = selected.to_dict('records')
                                            status_text = f"שולם ב{payment_method.strip()}"
                                            
                                            attachment_data = None
                                            attachment_name = None
                                            if uploaded_file:
                                                attachment_data = uploaded_file.read()
                                                attachment_name = uploaded_file.name
                                            
                                            with st.spinner("מעדכן סטטוס ושולח מייל לאופרציה..."):
                                                status_success = update_sheet_status(row_indices, status_text)
                                                
                                                if status_success:
                                                    email_success, email_message = send_payment_confirmation_email(
                                                        orders_data, 
                                                        payment_method.strip(),
                                                        attachment_data,
                                                        attachment_name
                                                    )
                                                    
                                                    if email_success:
                                                        file_msg = " + קובץ מצורף" if attachment_data else ""
                                                        st.success(f"✅ עודכנו {len(row_indices)} הזמנות לסטטוס 'שולם' + נשלח מייל אישור לאופרציה{file_msg}!")
                                                        st.info(f"📧 {email_message}")
                                                    else:
                                                        st.warning(f"✅ סטטוס עודכן, אבל המייל לא נשלח: {email_message}")
                                                    
                                                    st.cache_data.clear()
                                                    st.rerun()
                                        else:
                                            st.warning("יש להזין אמצעי תשלום")
                            
                            if st.session_state.get(f'show_payment_copy_{key}', False):
                                payment_orders = st.session_state.get(f'payment_orders_{key}', [])
                                if payment_orders:
                                    st.markdown("---")
                                    st.markdown("### 💳 העתקה לגביית תשלום")
                                    st.info("העתק את הפרטים הבאים ושלח להנהלת חשבונות:")
                                    
                                    for idx, order in enumerate(payment_orders):
                                        order_num = order.get('Order number', '-')
                                        event_name = order.get('event name', '-')
                                        docket = order.get('docket number', order.get('docket', order.get('Docket', '-')))
                                        source = order.get('source', '-')
                                        supp_order = order.get('SUPP order number', '-')
                                        event_date = order.get('Date of the event', '-')
                                        qty = order.get('Qty', order.get('QTY', '-'))
                                        price_sold = order.get('Price sold', '-')
                                        total_sold = order.get('total sold', order.get('TOTAL', order.get('TOTAL_clean', '-')))
                                        supp_price = order.get('SUPP PRICE', '-')
                                        
                                        if total_sold and total_sold != '-':
                                            try:
                                                total_display = f"€{float(str(total_sold).replace('€','').replace(',','').strip()):,.2f}"
                                            except:
                                                total_display = str(total_sold)
                                        else:
                                            total_display = '-'
                                        
                                        payment_text = f"""הזמנה לגבייה #{idx+1}:
מספר הזמנה: {order_num}
שם אירוע: {event_name}
מספר דוקט: {docket}
מקור: {source}
מספר הזמנה ספק: {supp_order}
תאריך אירוע: {event_date}
כמות: {qty}
מחיר מקורי לכרטיס: {price_sold}
סכום לגבייה: {total_display}
מחיר ספק: {supp_price}
סטטוס: נשלח ולא שולם"""
                                        
                                        st.code(payment_text, language="text")
                                    
                                    if st.button("❌ סגור העתקה", key=f"close_payment_copy_{key}"):
                                        st.session_state[f'show_payment_copy_{key}'] = False
                                        st.rerun()
                    
                    st.markdown("---")
        elif new_orders_df.empty:
            st.success(t("no_pending"))
        else:
            st.warning("לא נמצאה עמודת שם אירוע")
    else:
        st.warning(t("no_orderd_col"))

with tab2:
    st.header(t("profit_header"))
    
    rates = get_exchange_rates()
    st.caption(f"💱 שערי המרה נוכחיים: £1 = €{rates['GBP']:.3f} | $1 = €{rates['USD']:.3f}")
    
    if 'tab2_filters' not in st.session_state:
        st.session_state.tab2_filters = {'event': None, 'team': None, 'date_range': 'הכל', 'month': None, 'source': None}
    
    with st.container(border=True):
        st.markdown("##### 🔍 סינון נתונים")
        filter_row1 = st.columns([2.5, 1.5, 1.5, 1.5, 1.5, 0.5])
        
        with filter_row1[0]:
            last_event_selected_tab2 = st.session_state.get('manual_order_last_event', None)
            event_options_tab2 = get_sorted_event_options(df, last_selected=last_event_selected_tab2)
            selected_event_tab2 = st.selectbox(
                "🎯 אירוע",
                options=["כל האירועים"] + event_options_tab2,
                index=0,
                key="tab2_event_filter"
            )
            st.session_state.tab2_filters['event'] = selected_event_tab2 if selected_event_tab2 != "כל האירועים" else None
        
        with filter_row1[1]:
            all_teams_tab2 = set()
            if 'event name' in df.columns:
                for event in df['event name'].dropna().unique():
                    teams = extract_teams(str(event))
                    for team in teams:
                        if team and len(team) > 1:
                            all_teams_tab2.add(team.title())
            team_options = ["כל הקבוצות"] + sorted(list(all_teams_tab2))
            selected_team_tab2 = st.selectbox("⚽ קבוצה", team_options, key="tab2_team_filter")
            st.session_state.tab2_filters['team'] = selected_team_tab2 if selected_team_tab2 != "כל הקבוצות" else None
        
        with filter_row1[2]:
            date_options_tab2 = ["הכל", "7 ימים אחרונים", "30 יום אחרונים", "90 יום אחרונים", "השנה הנוכחית"]
            selected_date_tab2 = st.selectbox("📅 טווח תאריכים", date_options_tab2, key="tab2_date_filter")
            st.session_state.tab2_filters['date_range'] = selected_date_tab2
        
        with filter_row1[3]:
            months_list = ["כל החודשים"] + [f"{i:02d}/{datetime.now().year}" for i in range(1, 13)] + [f"{i:02d}/{datetime.now().year - 1}" for i in range(1, 13)]
            selected_month_tab2 = st.selectbox("🗓️ חודש", months_list, key="tab2_month_filter")
            st.session_state.tab2_filters['month'] = selected_month_tab2 if selected_month_tab2 != "כל החודשים" else None
        
        with filter_row1[4]:
            all_sources_tab2 = ["כל המקורות"]
            if 'source' in df.columns:
                all_sources_tab2 += sorted([str(s).strip() for s in df['source'].dropna().unique() if str(s).strip()])
            selected_source_tab2 = st.selectbox("📍 מקור", all_sources_tab2, key="tab2_source_filter")
            st.session_state.tab2_filters['source'] = selected_source_tab2 if selected_source_tab2 != "כל המקורות" else None
        
        with filter_row1[5]:
            if st.button("🧹", key="clear_tab2_all", help="נקה הכל"):
                for key in ['tab2_event_filter', 'tab2_team_filter', 'tab2_date_filter', 'tab2_month_filter', 'tab2_source_filter']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.tab2_filters = {'event': None, 'team': None, 'date_range': 'הכל', 'month': None, 'source': None}
                st.rerun()
    
    st.markdown("---")
    
    filtered_df = apply_filters(df)
    
    if 'parsed_date' not in filtered_df.columns and 'Date of the event' in filtered_df.columns:
        filtered_df['parsed_date'] = filtered_df['Date of the event'].apply(lambda x: smart_date_parser(x, ''))
    
    if st.session_state.tab2_filters['event'] and 'event name' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['event name'] == st.session_state.tab2_filters['event']]
    
    if st.session_state.tab2_filters['team'] and 'event name' in filtered_df.columns:
        team_filter = st.session_state.tab2_filters['team']
        def has_team_tab2(event_name):
            teams = extract_teams(str(event_name))
            return any(team.title() == team_filter for team in teams)
        filtered_df = filtered_df[filtered_df['event name'].apply(has_team_tab2)]
    
    if st.session_state.tab2_filters['source'] and 'source' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['source'].str.strip() == st.session_state.tab2_filters['source']]
    
    if 'parsed_date' in filtered_df.columns:
        today = datetime.now()
        date_range = st.session_state.tab2_filters.get('date_range', 'הכל')
        if date_range == '7 ימים אחרונים':
            cutoff = today - timedelta(days=7)
            filtered_df = filtered_df[filtered_df['parsed_date'] >= cutoff]
        elif date_range == '30 יום אחרונים':
            cutoff = today - timedelta(days=30)
            filtered_df = filtered_df[filtered_df['parsed_date'] >= cutoff]
        elif date_range == '90 יום אחרונים':
            cutoff = today - timedelta(days=90)
            filtered_df = filtered_df[filtered_df['parsed_date'] >= cutoff]
        elif date_range == 'השנה הנוכחית':
            filtered_df = filtered_df[filtered_df['parsed_date'].dt.year == today.year]
        
        month_filter = st.session_state.tab2_filters.get('month')
        if month_filter:
            try:
                month_str, year_str = month_filter.split('/')
                filtered_df = filtered_df[(filtered_df['parsed_date'].dt.month == int(month_str)) & (filtered_df['parsed_date'].dt.year == int(year_str))]
            except:
                pass
    
    
    filtered_df['has_supplier_data'] = filtered_df.apply(has_supplier_data, axis=1)
    with_supplier_df = filtered_df[filtered_df['has_supplier_data'] == True].copy()
    without_supplier_df = filtered_df[filtered_df['has_supplier_data'] == False].copy()
    
    st.markdown("### 📊 הזמנות עם נתוני ספק (מחשב רווחיות)")
    
    if not with_supplier_df.empty:
        total_profit = with_supplier_df['profit'].sum()
        total_sales = with_supplier_df['TOTAL_clean'].sum()
        total_supp_cost = with_supplier_df['SUPP_PRICE_clean'].sum()
        total_commission = with_supplier_df['commission_amount'].sum() if 'commission_amount' in with_supplier_df.columns else 0
        total_revenue_net = with_supplier_df['revenue_net'].sum() if 'revenue_net' in with_supplier_df.columns else total_sales
        profit_before_commission = with_supplier_df['profit_before_commission'].sum() if 'profit_before_commission' in with_supplier_df.columns else total_profit
        avg_margin = with_supplier_df[with_supplier_df['TOTAL_clean'] > 0]['margin_pct'].mean()
        total_qty = pd.to_numeric(with_supplier_df.get('Qty', 0), errors='coerce').sum()
        profit_per_ticket = total_profit / total_qty if total_qty > 0 else 0
        
        metric_cols = st.columns(7)
        with metric_cols[0]:
            st.metric("הזמנות", len(with_supplier_df))
        with metric_cols[1]:
            st.metric("📦 סה\"כ כרטיסים", f"{int(total_qty):,}")
        with metric_cols[2]:
            st.metric("מכירות (ברוטו)", f"€{total_sales:,.0f}")
        with metric_cols[3]:
            st.metric("עלות ספקים", f"€{total_supp_cost:,.0f}")
        with metric_cols[4]:
            st.metric("רווח נטו", f"€{total_profit:,.0f}")
        with metric_cols[5]:
            st.metric("אחוז רווח", f"{avg_margin:.1f}%" if not pd.isna(avg_margin) else "N/A")
        with metric_cols[6]:
            st.metric("רווח/כרטיס", f"€{profit_per_ticket:,.1f}")
        
        if total_commission > 0:
            with st.expander("💳 פירוט עמלות מקור (Tixstock 3%)", expanded=True):
                comm_cols = st.columns(4)
                with comm_cols[0]:
                    st.metric("💰 מכירות לפני עמלה", f"€{total_sales:,.0f}")
                with comm_cols[1]:
                    pct_delta = f"-{(total_commission/total_sales*100):.1f}%" if total_sales > 0 else "0%"
                    st.metric("📉 עמלות שנלקחו", f"-€{total_commission:,.0f}", delta=pct_delta, delta_color="inverse")
                with comm_cols[2]:
                    st.metric("💵 מכירות אחרי עמלה", f"€{total_revenue_net:,.0f}")
                with comm_cols[3]:
                    comm_delta = f"-€{total_commission:,.0f}" if total_commission > 0 else None
                    st.metric("📊 רווח לפני עמלה", f"€{profit_before_commission:,.0f}", delta=comm_delta, delta_color="inverse")
                
                tixstock_df = with_supplier_df[with_supplier_df['commission_rate'] > 0] if 'commission_rate' in with_supplier_df.columns else pd.DataFrame()
                if not tixstock_df.empty:
                    st.caption(f"📌 {len(tixstock_df)} הזמנות עם עמלת Tixstock (3%)")
        
        if 'event name' in with_supplier_df.columns:
            st.markdown("#### 📈 רווחיות לפי אירוע")
            
            with_supplier_df['normalized_event'] = with_supplier_df['event name'].apply(normalize_event_name)
            
            with_supplier_df['Qty_numeric'] = pd.to_numeric(with_supplier_df.get('Qty', 0), errors='coerce').fillna(0)
            
            event_profit = with_supplier_df.groupby('normalized_event').agg({
                'TOTAL_clean': 'sum',
                'SUPP_PRICE_clean': 'sum',
                'profit': 'sum',
                'row_index': 'count',
                'Qty_numeric': 'sum'
            }).reset_index()
            
            original_names = with_supplier_df.groupby('normalized_event')['event name'].first()
            event_profit['event_display'] = event_profit['normalized_event'].map(original_names)
            
            event_profit['profit_per_ticket'] = event_profit.apply(
                lambda row: row['profit'] / row['Qty_numeric'] if row['Qty_numeric'] > 0 else 0, axis=1
            )
            
            event_profit = event_profit[['event_display', 'TOTAL_clean', 'SUPP_PRICE_clean', 'profit', 'row_index', 'Qty_numeric', 'profit_per_ticket']]
            event_profit.columns = ['אירוע', 'מכירות', 'עלות ספק', 'רווח', 'הזמנות', 'כרטיסים', 'רווח/כרטיס']
            event_profit['אחוז רווח'] = (event_profit['רווח'] / event_profit['מכירות'] * 100).round(1)
            event_profit = event_profit.sort_values('רווח', ascending=False)
            
            st.dataframe(
                event_profit.head(15).style.format({
                    'מכירות': '€{:,.0f}',
                    'עלות ספק': '€{:,.0f}',
                    'רווח': '€{:,.0f}',
                    'כרטיסים': '{:,.0f}',
                    'רווח/כרטיס': '€{:,.1f}',
                    'אחוז רווח': '{:.1f}%'
                }),
                use_container_width=True,
                hide_index=True
            )
        
        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.subheader(t("monthly_trend"))
            if 'parsed_date' in with_supplier_df.columns:
                monthly_df = with_supplier_df[with_supplier_df['parsed_date'].notna()].copy()
                if not monthly_df.empty:
                    monthly_df['month'] = monthly_df['parsed_date'].dt.to_period('M').astype(str)
                    monthly_profit = monthly_df.groupby('month')['profit'].sum().reset_index()
                    monthly_profit.columns = [t('month'), t('profit')]
                    
                    fig_line = px.line(monthly_profit, x=t('month'), y=t('profit'), markers=True)
                    fig_line.update_layout(showlegend=False)
                    st.plotly_chart(fig_line, use_container_width=True)
        
        with chart_cols[1]:
            st.subheader(t("top_10"))
            if 'event name' in with_supplier_df.columns:
                top_10 = event_profit.head(10)
                if not top_10.empty:
                    fig_bar = px.bar(top_10, x='רווח', y='אירוע', orientation='h')
                    fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("אין הזמנות עם נתוני ספק")
    
    st.markdown("---")
    st.markdown("### ⚠️ הזמנות ללא נתוני ספק (מכירות פוטנציאליות בלבד)")
    
    if not without_supplier_df.empty:
        potential_sales = without_supplier_df['TOTAL_clean'].sum()
        potential_qty = pd.to_numeric(without_supplier_df.get('Qty', 0), errors='coerce').sum()
        
        cols = st.columns(3)
        with cols[0]:
            st.metric("הזמנות ללא ספק", len(without_supplier_df))
        with cols[1]:
            st.metric("מכירות פוטנציאליות", f"€{potential_sales:,.0f}")
        with cols[2]:
            st.metric("כרטיסים", int(potential_qty))
        
        st.caption("⚠️ הזמנות אלה לא נכללות בחישוב הרווחיות - חסרים נתוני ספק")
    else:
        st.success("כל ההזמנות כוללות נתוני ספק!")

with tab3:
    st.header(t("operational_header"))
    
    if 'parsed_date' in df.columns:
        next_7_days = df[
            (df['parsed_date'].notna()) &
            (df['parsed_date'] >= now) &
            (df['parsed_date'] <= now + timedelta(days=7))
        ].copy()
        
        next_7_days = apply_filters(next_7_days)
        
        if not next_7_days.empty:
            next_7_days = next_7_days.sort_values('parsed_date')
            
            missing_purchase = len(next_7_days[next_7_days[status_col].fillna('').str.lower().str.strip() == 'new']) if status_col else 0
            waiting_supp = len(next_7_days[next_7_days[status_col].fillna('').str.lower().str.strip() == 'orderd']) if status_col else 0
            done_count = len(next_7_days[next_7_days[status_col].fillna('').str.lower().str.strip().isin(['done!', 'done'])]) if status_col else 0
            
            alert_cols = st.columns(4)
            with alert_cols[0]:
                st.caption(f"📊 סה\"כ: **{len(next_7_days)}** הזמנות")
            with alert_cols[1]:
                if missing_purchase > 0:
                    st.caption(f"🔴 **{missing_purchase}** חסר קנייה")
            with alert_cols[2]:
                if waiting_supp > 0:
                    st.caption(f"🟡 **{waiting_supp}** ממתין לספק")
            with alert_cols[3]:
                if done_count > 0:
                    st.caption(f"✅ **{done_count}** הושלם")
            
            op_grouped = group_orders_by_event(next_7_days)
            
            for key, event_data in op_grouped.items():
                order_count = len(event_data['orders'])
                without_supp = event_data['without_supplier']
                with_supp = event_data['with_supplier']
                
                if without_supp > 0:
                    status_icon = "🔴"
                    border_color = "#dc2626"
                elif with_supp == order_count:
                    status_icon = "✅"
                    border_color = "#16a34a"
                else:
                    status_icon = "🟡"
                    border_color = "#f59e0b"
                
                with st.container():
                    st.markdown(f"""
                    <div style="border-left: 5px solid {border_color}; padding: 12px; margin: 10px 0; background: #f8fafc; border-radius: 8px;">
                        <h4 style="margin:0; color: #1f2937;">{status_icon} {event_data['event_name']}</h4>
                        <span style="font-size: 13px; color: #6b7280;">📅 {event_data['event_date']} | 🎫 {int(event_data['total_qty'])} כרטיסים | 💰 €{event_data['total_sold']:,.0f}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    orders_df = pd.DataFrame(event_data['orders'])
                    
                    with st.expander(f"📋 פירוט {order_count} הזמנות", expanded=True):
                        display_cols = [
                            'order date',
                            'orderd',
                            'event name',
                            'Order number',
                            'docket number',
                            'Category / Section',
                            'Seating Arrangements',
                            'Qty',
                            'Price sold',
                            'total sold',
                            'SUPP PRICE',
                            'Supplier NAME',
                            'SUPP order number'
                        ]
                        available_cols = [col for col in display_cols if col in orders_df.columns]
                        
                        if available_cols:
                            display_df = orders_df[available_cols].copy()
                            display_df.insert(0, 'Select', False)
                            display_df['row_index'] = orders_df['row_index']
                            
                            if 'orderd' in display_df.columns:
                                def format_status_op(status_val):
                                    if pd.isna(status_val) or str(status_val).strip() == '':
                                        return ''
                                    status_lower = str(status_val).lower().strip()
                                    if status_lower == 'new':
                                        return '🔴 חדש'
                                    elif status_lower in ['ordered', 'orderd']:
                                        return '📦 הוזמן'
                                    elif status_lower in ['done', 'done!']:
                                        return '✅ הושלם'
                                    elif 'old' in status_lower or 'no data' in status_lower:
                                        return '⚪ ללא נתונים'
                                    elif 'נשלח ולא שולם' in str(status_val) or 'sent_not_paid' in status_lower or 'sent unpaid' in status_lower:
                                        return '🟠 נשלח ולא שולם'
                                    elif 'נשלח ושולם' in str(status_val) or 'sent_paid' in status_lower or 'שולם ב' in str(status_val):
                                        return '💚 נשלח ושולם'
                                    else:
                                        return f'🟡 {status_val}'
                                display_df['orderd'] = display_df['orderd'].apply(format_status_op)
                            
                            op_column_config = {
                                "Select": st.column_config.CheckboxColumn("בחר", default=False),
                                "order date": st.column_config.TextColumn("תאריך הזמנה"),
                                "orderd": st.column_config.TextColumn("סטטוס"),
                                "event name": st.column_config.TextColumn("אירוע"),
                                "Order number": st.column_config.TextColumn("מס' הזמנה"),
                                "docket number": st.column_config.TextColumn("דוקט"),
                                "Category / Section": st.column_config.TextColumn("קטגוריה"),
                                "Seating Arrangements": st.column_config.TextColumn("מושבים"),
                                "Qty": st.column_config.NumberColumn("כמות"),
                                "Price sold": st.column_config.NumberColumn("מחיר לכרטיס", format="€%.0f"),
                                "total sold": st.column_config.NumberColumn("סה\"כ מכירה", format="€%.0f"),
                                "SUPP PRICE": st.column_config.NumberColumn("מחיר ספק", format="€%.0f"),
                                "Supplier NAME": st.column_config.TextColumn("שם ספק"),
                                "SUPP order number": st.column_config.TextColumn("מס' הזמנה ספק"),
                                "row_index": None,
                            }
                            
                            show_cols = ['Select'] + available_cols
                            
                            edited_df = st.data_editor(
                                display_df[show_cols + ['row_index']],
                                column_config=op_column_config,
                                disabled=[col for col in show_cols if col != 'Select'] + ['row_index'],
                                hide_index=True,
                                use_container_width=True,
                                key=f"op_editor_{key}"
                            )
                            
                            selected = edited_df[edited_df['Select'] == True]
                            if len(selected) > 0:
                                btn_cols = st.columns([2, 1, 1])
                                with btn_cols[0]:
                                    if st.button(f"✅ סמן שנשלח והושלם", key=f"op_mark_{key}", type="primary"):
                                        row_indices = selected['row_index'].tolist()
                                        with st.spinner("מעדכן..."):
                                            success = update_sheet_status(row_indices, "done!")
                                        if success:
                                            st.success(f"✅ עודכנו {len(row_indices)} הזמנות!")
                                            st.cache_data.clear()
                                            st.rerun()
                    
                    st.markdown("---")
        else:
            st.info(t("no_events_7days"))
    else:
        st.warning(t("date_not_found"))

with tab4:
    st.header("🆕 הזמנות חדשות לטיפול")
    st.markdown("*כל ההזמנות עם סטטוס 'New' או ללא סטטוס - עדכן מספר הזמנה ספק וסטטוס*")
    
    # Load FRESH data directly - ignore sidebar filters
    fresh_df = load_data_from_sheet()
    tab4_status_col = 'orderd' if 'orderd' in fresh_df.columns else None
    
    if tab4_status_col:
        # Filter for new or empty status
        status_values = fresh_df[tab4_status_col].fillna('').astype(str).str.strip()
        all_new_orders = fresh_df[(status_values.str.lower() == 'new') | (status_values == '')].copy()
        
        # Sort by row index (descending) to get newest entries first
        if 'row_index' in all_new_orders.columns:
            all_new_orders = all_new_orders.sort_values('row_index', ascending=False)
        elif 'Order number' in all_new_orders.columns:
            all_new_orders['order_num_sort'] = pd.to_numeric(all_new_orders['Order number'], errors='coerce')
            all_new_orders = all_new_orders.sort_values('order_num_sort', ascending=False, na_position='last')
        
        if not all_new_orders.empty:
            st.success(f"📋 **{len(all_new_orders)} הזמנות חדשות** לטיפול")
            
            # Refresh button
            if st.button("🔄 רענן נתונים", key="refresh_new_orders"):
                st.cache_data.clear()
                st.rerun()
            
            st.markdown("---")
            
            for idx, (_, order) in enumerate(all_new_orders.iterrows()):
                order_num = order.get('Order number', '-')
                event_name = str(order.get('event name', '-'))[:50]
                event_date = order.get('Date of the event', '-')
                order_date = order.get('order date', '-')
                qty = order.get('Qty', '-')
                total = order.get('TOTAL', '-')
                source = order.get('source', '-')
                current_supp_order = str(order.get('SUPP order number', '')).strip()
                current_status = str(order.get(tab4_status_col, '')).strip()
                row_idx = order.get('row_index', None)
                category = order.get('Category / Section', '-')
                
                is_ordered = current_status.lower() == 'orderd'
                
                with st.container(border=True):
                    if is_ordered:
                        st.markdown("""
                        <style>
                        div[data-testid="stVerticalBlockBorderWrapper"]:has(h3:contains("הזמנה")) {
                            background-color: rgba(56, 189, 248, 0.15) !important;
                        }
                        </style>
                        <div style="background-color: rgba(56, 189, 248, 0.15); margin: -1rem; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem;">
                        <h4 style="margin:0; color: #0284c7;">🎫 הזמנה #""" + str(order_num) + """ ✓ הוזמן</h4>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"**{event_name}** | 📅 אירוע: {event_date} | 🛒 הזמנה: {order_date} | 🎫 {qty} כרטיסים | €{total} | 📍 {source} | 📁 {category}")
                    else:
                        st.markdown(f"### 🎫 הזמנה #{order_num}")
                        st.markdown(f"**{event_name}** | 📅 אירוע: {event_date} | 🛒 הזמנה: {order_date} | 🎫 {qty} כרטיסים | €{total} | 📍 {source} | 📁 {category}")
                    
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
                    with col1:
                        new_supp_order = st.text_input(
                            "מס' הזמנה ספק",
                            value=current_supp_order,
                            key=f"tab4_supp_{idx}_{order_num}",
                            placeholder="הכנס מספר הזמנה ספק"
                        )
                    with col2:
                        status_options = ['new', 'orderd', 'done!', 'old no data']
                        current_idx = status_options.index(current_status.lower()) if current_status.lower() in status_options else 0
                        new_status = st.selectbox(
                            "סטטוס",
                            options=status_options,
                            index=current_idx,
                            key=f"tab4_status_{idx}_{order_num}"
                        )
                    with col3:
                        supp_price_val = order.get('SUPP PRICE', '')
                        new_supp_price = st.text_input(
                            "מחיר ספק",
                            value=str(supp_price_val) if supp_price_val else "",
                            key=f"tab4_price_{idx}_{order_num}",
                            placeholder="מחיר"
                        )
                    with col4:
                        st.write("")
                        st.write("")
                        if st.button("💾 שמור", key=f"tab4_save_{idx}_{order_num}", type="primary"):
                            if row_idx:
                                try:
                                    client = get_gspread_client()
                                    sheet = client.open(SHEET_NAME)
                                    worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
                                    headers = worksheet.row_values(1)
                                    
                                    supp_order_col_idx = None
                                    status_col_idx = None
                                    supp_price_col_idx = None
                                    for i, h in enumerate(headers):
                                        h_lower = h.strip().lower()
                                        if h_lower in ['supp order number', 'supp order']:
                                            supp_order_col_idx = i + 1
                                        if h_lower == 'orderd':
                                            status_col_idx = i + 1
                                        if h_lower == 'supp price':
                                            supp_price_col_idx = i + 1
                                    
                                    updates = []
                                    if supp_order_col_idx and new_supp_order != current_supp_order:
                                        col_letter = col_number_to_letter(supp_order_col_idx)
                                        updates.append({'range': f'{col_letter}{row_idx}', 'values': [[new_supp_order]]})
                                    
                                    if status_col_idx and new_status != current_status:
                                        col_letter = col_number_to_letter(status_col_idx)
                                        updates.append({'range': f'{col_letter}{row_idx}', 'values': [[new_status]]})
                                    
                                    if supp_price_col_idx and new_supp_price and new_supp_price != str(supp_price_val):
                                        col_letter = col_number_to_letter(supp_price_col_idx)
                                        updates.append({'range': f'{col_letter}{row_idx}', 'values': [[new_supp_price]]})
                                    
                                    if updates:
                                        worksheet.batch_update(updates)
                                        st.success(f"✅ הזמנה #{order_num} עודכנה בהצלחה!")
                                        st.cache_data.clear()
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.info("אין שינויים לשמור")
                                except Exception as e:
                                    st.error(f"שגיאה: {str(e)}")
                            else:
                                st.warning("לא נמצא מספר שורה - לא ניתן לעדכן")
                    with col5:
                        st.write("")
                        st.write("")
                        if st.button("🗑️ מחק", key=f"tab4_delete_{idx}_{order_num}", type="secondary"):
                            if row_idx:
                                with st.spinner("מוחק הזמנה..."):
                                    success = delete_order_row(row_idx)
                                if success:
                                    st.success(f"✅ הזמנה #{order_num} נמחקה!")
                                    st.cache_data.clear()
                                    time.sleep(0.5)
                                    st.rerun()
                            else:
                                st.warning("לא נמצא מספר שורה")
        else:
            st.success("🎉 אין הזמנות חדשות לטיפול! כל ההזמנות טופלו.")
    else:
        st.warning("לא נמצאה עמודת סטטוס")

with tab5:
    st.header("📈 מכירות")
    st.markdown("מעקב אחר מכירות - יומי, שבועי וחודשי")
    
    if 'tab5_filters' not in st.session_state:
        st.session_state.tab5_filters = {'event': None, 'team': None, 'date_range': 'הכל', 'month': None, 'source': None}
    
    with st.container(border=True):
        st.markdown("##### 🔍 סינון נתונים")
        filter_row_t5 = st.columns([2.5, 1.5, 1.5, 1.5, 1.5, 0.5])
        
        with filter_row_t5[0]:
            last_event_selected_tab5 = st.session_state.get('manual_order_last_event', None)
            event_options_tab5 = get_sorted_event_options(df, last_selected=last_event_selected_tab5)
            selected_event_tab5 = st.selectbox(
                "🎯 אירוע",
                options=["כל האירועים"] + event_options_tab5,
                index=0,
                key="tab5_event_filter"
            )
            st.session_state.tab5_filters['event'] = selected_event_tab5 if selected_event_tab5 != "כל האירועים" else None
        
        with filter_row_t5[1]:
            all_teams_tab5 = set()
            if 'event name' in df.columns:
                for event in df['event name'].dropna().unique():
                    teams = extract_teams(str(event))
                    for team in teams:
                        if team and len(team) > 1:
                            all_teams_tab5.add(team.title())
            team_options_t5 = ["כל הקבוצות"] + sorted(list(all_teams_tab5))
            selected_team_tab5 = st.selectbox("⚽ קבוצה", team_options_t5, key="tab5_team_filter")
            st.session_state.tab5_filters['team'] = selected_team_tab5 if selected_team_tab5 != "כל הקבוצות" else None
        
        with filter_row_t5[2]:
            date_options_tab5 = ["הכל", "7 ימים אחרונים", "30 יום אחרונים", "90 יום אחרונים", "השנה הנוכחית"]
            selected_date_tab5 = st.selectbox("📅 טווח תאריכים", date_options_tab5, key="tab5_date_filter")
            st.session_state.tab5_filters['date_range'] = selected_date_tab5
        
        with filter_row_t5[3]:
            months_list_t5 = ["כל החודשים"] + [f"{i:02d}/{datetime.now().year}" for i in range(1, 13)] + [f"{i:02d}/{datetime.now().year - 1}" for i in range(1, 13)]
            selected_month_tab5 = st.selectbox("🗓️ חודש", months_list_t5, key="tab5_month_filter")
            st.session_state.tab5_filters['month'] = selected_month_tab5 if selected_month_tab5 != "כל החודשים" else None
        
        with filter_row_t5[4]:
            all_sources_tab5 = ["כל המקורות"]
            if 'source' in df.columns:
                all_sources_tab5 += sorted([str(s).strip() for s in df['source'].dropna().unique() if str(s).strip()])
            selected_source_tab5 = st.selectbox("📍 מקור", all_sources_tab5, key="tab5_source_filter")
            st.session_state.tab5_filters['source'] = selected_source_tab5 if selected_source_tab5 != "כל המקורות" else None
        
        with filter_row_t5[5]:
            if st.button("🧹", key="clear_tab5_all", help="נקה הכל"):
                for key in ['tab5_event_filter', 'tab5_team_filter', 'tab5_date_filter', 'tab5_month_filter', 'tab5_source_filter']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.tab5_filters = {'event': None, 'team': None, 'date_range': 'הכל', 'month': None, 'source': None}
                st.rerun()
    
    st.markdown("---")
    
    sales_base_df = df.copy()
    
    if 'parsed_date' not in sales_base_df.columns and 'Date of the event' in sales_base_df.columns:
        sales_base_df['parsed_date'] = sales_base_df['Date of the event'].apply(lambda x: smart_date_parser(x, ''))
    
    if st.session_state.tab5_filters['event'] and 'event name' in sales_base_df.columns:
        sales_base_df = sales_base_df[sales_base_df['event name'] == st.session_state.tab5_filters['event']]
    
    if st.session_state.tab5_filters['team'] and 'event name' in sales_base_df.columns:
        team_filter_t5 = st.session_state.tab5_filters['team']
        def has_team_tab5(event_name):
            teams = extract_teams(str(event_name))
            return any(team.title() == team_filter_t5 for team in teams)
        sales_base_df = sales_base_df[sales_base_df['event name'].apply(has_team_tab5)]
    
    if st.session_state.tab5_filters['source'] and 'source' in sales_base_df.columns:
        sales_base_df = sales_base_df[sales_base_df['source'].str.strip() == st.session_state.tab5_filters['source']]
    
    if 'parsed_date' in sales_base_df.columns:
        today = datetime.now()
        date_range_t5 = st.session_state.tab5_filters.get('date_range', 'הכל')
        if date_range_t5 == '7 ימים אחרונים':
            cutoff = today - timedelta(days=7)
            sales_base_df = sales_base_df[sales_base_df['parsed_date'] >= cutoff]
        elif date_range_t5 == '30 יום אחרונים':
            cutoff = today - timedelta(days=30)
            sales_base_df = sales_base_df[sales_base_df['parsed_date'] >= cutoff]
        elif date_range_t5 == '90 יום אחרונים':
            cutoff = today - timedelta(days=90)
            sales_base_df = sales_base_df[sales_base_df['parsed_date'] >= cutoff]
        elif date_range_t5 == 'השנה הנוכחית':
            sales_base_df = sales_base_df[sales_base_df['parsed_date'].dt.year == today.year]
        
        month_filter_t5 = st.session_state.tab5_filters.get('month')
        if month_filter_t5:
            try:
                month_str, year_str = month_filter_t5.split('/')
                sales_base_df = sales_base_df[(sales_base_df['parsed_date'].dt.month == int(month_str)) & (sales_base_df['parsed_date'].dt.year == int(year_str))]
            except:
                pass
    
    ORDER_DATE_COL = None
    for col in sales_base_df.columns:
        if col.lower().strip() in ['order date', 'orderdate']:
            ORDER_DATE_COL = col
            break
    
    if ORDER_DATE_COL:
        sales_df = sales_base_df.copy()
        
        def parse_order_date(date_val):
            if pd.isna(date_val) or str(date_val).strip() == '':
                return None
            date_str = str(date_val).strip()
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y', '%m/%d/%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            try:
                return pd.to_datetime(date_str)
            except:
                return None
        
        sales_df['order_date_parsed'] = sales_df[ORDER_DATE_COL].apply(parse_order_date)
        sales_df = sales_df[sales_df['order_date_parsed'].notna()].copy()
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        today_sales = sales_df[sales_df['order_date_parsed'].dt.date == today.date()]
        week_sales = sales_df[sales_df['order_date_parsed'] >= week_ago]
        month_sales = sales_df[sales_df['order_date_parsed'] >= month_ago]
        
        hist_profit_pct = 0.15
        if 'SUPP PRICE' in sales_df.columns and 'TOTAL' in sales_df.columns:
            hist_df = sales_df.copy()
            hist_df['revenue'] = hist_df.apply(lambda r: clean_numeric(r.get('TOTAL', 0)), axis=1)
            hist_df['cost'] = hist_df.apply(lambda r: parse_supp_price(r.get('SUPP PRICE', '')), axis=1)
            with_cost = hist_df[hist_df['cost'] > 0]
            if len(with_cost) > 0:
                total_rev = with_cost['revenue'].sum()
                total_cost = with_cost['cost'].sum()
                if total_rev > 0:
                    hist_profit_pct = (total_rev - total_cost) / total_rev
        
        def calc_sales_metrics(data):
            if data.empty:
                return {'count': 0, 'qty': 0, 'revenue': 0, 'profit': 0, 'profit_pct': 0, 'potential_profit': 0, 'actual_revenue': 0}
            qty = pd.to_numeric(data.get('Qty', 0), errors='coerce').fillna(0).sum()
            revenue = data.apply(lambda r: clean_numeric(r.get('TOTAL', 0)), axis=1).sum()
            
            actual_profit = 0
            actual_revenue = 0
            potential_profit = 0
            
            for _, row in data.iterrows():
                rev = clean_numeric(row.get('TOTAL', 0))
                cost = parse_supp_price(row.get('SUPP PRICE', ''))
                status = str(row.get('orderd', '')).lower().strip() if 'orderd' in row.index else ''
                
                is_purchased = status in ['orderd', 'ordered', 'done', 'done!']
                
                if is_purchased and cost > 0:
                    actual_profit += (rev - cost)
                    actual_revenue += rev
                else:
                    potential_profit += rev * hist_profit_pct
            
            total_profit = actual_profit + potential_profit
            profit_pct = (total_profit / revenue * 100) if revenue > 0 else 0
            
            return {
                'count': len(data), 
                'qty': int(qty), 
                'revenue': revenue,
                'profit': actual_profit,
                'actual_revenue': actual_revenue,
                'potential_profit': potential_profit,
                'total_profit': total_profit,
                'profit_pct': profit_pct
            }
        
        today_metrics = calc_sales_metrics(today_sales)
        week_metrics = calc_sales_metrics(week_sales)
        month_metrics = calc_sales_metrics(month_sales)
        
        metric_cols = st.columns(3)
        def build_profit_lines(metrics):
            lines = []
            if metrics['profit'] > 0:
                actual_pct = (metrics['profit'] / metrics['actual_revenue'] * 100) if metrics['actual_revenue'] > 0 else 0
                lines.append(f"💵 רווח ודאי: €{metrics['profit']:,.0f} ({actual_pct:.1f}%)")
            if metrics['potential_profit'] > 0:
                lines.append(f"💰 רווח צפוי: ~€{metrics['potential_profit']:,.0f}")
            total_expected = metrics['profit'] + metrics['potential_profit']
            if total_expected > 0:
                lines.append(f"🎯 רווח כולל צפוי: €{total_expected:,.0f}")
            if not lines:
                lines.append("💵 רווח: €0")
            return lines
        
        with metric_cols[0]:
            profit_lines = build_profit_lines(today_metrics)
            profit_html = "".join([f'<p style="font-size: 1rem; margin: 3px 0;">{line}</p>' for line in profit_lines])
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 15px; text-align: center; color: white;">
                <h2 style="margin: 0; font-size: 2rem;">📅 היום</h2>
                <p style="font-size: 1.8rem; margin: 8px 0; font-weight: bold;">{today_metrics['count']} הזמנות</p>
                <p style="font-size: 1.1rem; margin: 4px 0;">🎫 {today_metrics['qty']} כרטיסים</p>
                <p style="font-size: 1.3rem; margin: 4px 0;">💰 הכנסות: €{today_metrics['revenue']:,.0f}</p>
                {profit_html}
                <p style="font-size: 1.1rem; margin: 4px 0;">📈 {today_metrics['profit_pct']:.1f}% רווחיות</p>
            </div>
            """, unsafe_allow_html=True)
        
        with metric_cols[1]:
            profit_lines = build_profit_lines(week_metrics)
            profit_html = "".join([f'<p style="font-size: 1rem; margin: 3px 0;">{line}</p>' for line in profit_lines])
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 15px; text-align: center; color: white;">
                <h2 style="margin: 0; font-size: 2rem;">📆 השבוע</h2>
                <p style="font-size: 1.8rem; margin: 8px 0; font-weight: bold;">{week_metrics['count']} הזמנות</p>
                <p style="font-size: 1.1rem; margin: 4px 0;">🎫 {week_metrics['qty']} כרטיסים</p>
                <p style="font-size: 1.3rem; margin: 4px 0;">💰 הכנסות: €{week_metrics['revenue']:,.0f}</p>
                {profit_html}
                <p style="font-size: 1.1rem; margin: 4px 0;">📈 {week_metrics['profit_pct']:.1f}% רווחיות</p>
            </div>
            """, unsafe_allow_html=True)
        
        with metric_cols[2]:
            profit_lines = build_profit_lines(month_metrics)
            profit_html = "".join([f'<p style="font-size: 1rem; margin: 3px 0;">{line}</p>' for line in profit_lines])
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 20px; border-radius: 15px; text-align: center; color: white;">
                <h2 style="margin: 0; font-size: 2rem;">📊 החודש</h2>
                <p style="font-size: 1.8rem; margin: 8px 0; font-weight: bold;">{month_metrics['count']} הזמנות</p>
                <p style="font-size: 1.1rem; margin: 4px 0;">🎫 {month_metrics['qty']} כרטיסים</p>
                <p style="font-size: 1.3rem; margin: 4px 0;">💰 הכנסות: €{month_metrics['revenue']:,.0f}</p>
                {profit_html}
                <p style="font-size: 1.1rem; margin: 4px 0;">📈 {month_metrics['profit_pct']:.1f}% רווחיות</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        def display_sales_summary(data, title, key_prefix):
            """הצג סיכום מכירות לפי אירוע ומקור"""
            if data.empty:
                st.info(f"אין מכירות ב{title}")
                return
            
            summary_data = data.copy()
            summary_data['Qty_num'] = pd.to_numeric(summary_data.get('Qty', 0), errors='coerce').fillna(0)
            summary_data['TOTAL_num'] = summary_data.apply(lambda r: clean_numeric(r.get('TOTAL', 0)), axis=1)
            
            if 'event name' in summary_data.columns:
                event_summary = summary_data.groupby('event name').agg({
                    'Qty_num': 'sum',
                    'TOTAL_num': 'sum'
                }).reset_index()
                event_summary = event_summary.sort_values('TOTAL_num', ascending=False)
                
                st.markdown("#### 🎯 מכירות לפי אירוע")
                
                for _, row in event_summary.iterrows():
                    event_name = row['event name']
                    qty = int(row['Qty_num'])
                    revenue = row['TOTAL_num']
                    
                    st.markdown(f"""
                    <div style="background: #f8f9fa; border-right: 4px solid #667eea; padding: 12px 15px; margin: 8px 0; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 2;">
                            <strong style="font-size: 1.1rem; color: #1f2937;">{event_name}</strong>
                        </div>
                        <div style="flex: 1; text-align: center;">
                            <span style="background: #e0e7ff; color: #4338ca; padding: 4px 12px; border-radius: 20px; font-weight: 600;">🎟️ {qty}</span>
                        </div>
                        <div style="flex: 1; text-align: left;">
                            <span style="color: #059669; font-weight: 700; font-size: 1.1rem;">€{revenue:,.0f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            if 'source' in summary_data.columns:
                source_summary = summary_data.groupby('source').agg({
                    'Qty_num': 'sum',
                    'TOTAL_num': 'sum'
                }).reset_index()
                source_summary = source_summary.sort_values('TOTAL_num', ascending=False)
                
                st.markdown("#### 📍 מכירות לפי מקור")
                
                src_cols = st.columns(len(source_summary) if len(source_summary) <= 4 else 4)
                for idx, (_, row) in enumerate(source_summary.head(4).iterrows()):
                    with src_cols[idx]:
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); padding: 15px; border-radius: 12px; text-align: center;">
                            <p style="font-size: 1rem; font-weight: 600; margin: 0; color: #92400e;">{row['source']}</p>
                            <p style="font-size: 1.4rem; font-weight: 700; margin: 5px 0; color: #78350f;">€{row['TOTAL_num']:,.0f}</p>
                            <p style="font-size: 0.9rem; margin: 0; color: #a16207;">🎟️ {int(row['Qty_num'])} כרטיסים</p>
                        </div>
                        """, unsafe_allow_html=True)
            
            with st.expander(f"📋 פירוט כל ההזמנות ({len(data)} הזמנות)", expanded=False):
                display_cols = ['order_date_parsed', 'event name', 'Category / Section', 'Qty', 'TOTAL', 'source']
                available_cols = [c for c in display_cols if c in data.columns]
                
                if available_cols:
                    display_data = data[available_cols].copy()
                    
                    if 'order_date_parsed' in display_data.columns:
                        display_data = display_data.sort_values('order_date_parsed', ascending=False)
                    
                    col_rename = {
                        'order_date_parsed': '📅 תאריך הזמנה',
                        'event name': '🎫 משחק/אירוע',
                        'Category / Section': '🎟️ קטגוריה',
                        'Qty': '🔢 כמות',
                        'TOTAL': '💰 סכום',
                        'source': '📍 מקור'
                    }
                    display_data = display_data.rename(columns=col_rename)
                    
                    if '📅 תאריך הזמנה' in display_data.columns:
                        display_data['📅 תאריך הזמנה'] = display_data['📅 תאריך הזמנה'].dt.strftime('%d/%m/%Y')
                    
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
        
        sales_tab1, sales_tab2, sales_tab3 = st.tabs(["📅 מכירות היום", "📆 מכירות השבוע", "📊 מכירות החודש"])
        
        with sales_tab1:
            display_sales_summary(today_sales, "היום", "today")
        
        with sales_tab2:
            display_sales_summary(week_sales, "השבוע", "week")
            
            if not week_sales.empty:
                st.markdown("---")
                st.markdown("#### 📈 גרף מכירות יומיות")
                daily_sales = week_sales.copy()
                daily_sales['date'] = daily_sales['order_date_parsed'].dt.date
                daily_agg = daily_sales.groupby('date').agg({
                    'Qty': lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()
                }).reset_index()
                daily_agg.columns = ['תאריך', 'כרטיסים']
                
                import plotly.express as px
                fig = px.bar(daily_agg, x='תאריך', y='כרטיסים', 
                           title='מכירות יומיות - 7 ימים אחרונים',
                           color_discrete_sequence=['#667eea'])
                fig.update_layout(xaxis_title='תאריך', yaxis_title='כרטיסים שנמכרו')
                st.plotly_chart(fig, use_container_width=True)
        
        with sales_tab3:
            display_sales_summary(month_sales, "החודש", "month")
    else:
        st.warning("לא נמצאה עמודת תאריך הזמנה בנתונים")

with tab6:
    st.header("📊 השוואת מקורות")
    st.markdown("ניתוח רווחיות לפי מקור מכירה")
    
    # Get exchange rates
    rates = get_exchange_rates()
    st.caption(f"💱 שערי המרה: £1 = €{rates['GBP']:.3f} | $1 = €{rates['USD']:.3f}")
    
    # Event filter for source comparison
    if 'tab6_selected_event' not in st.session_state:
        st.session_state.tab6_selected_event = None
    
    last_event_selected_tab6 = st.session_state.get('manual_order_last_event', None)
    event_options_tab6 = get_sorted_event_options(df, last_selected=last_event_selected_tab6)
    event_filter_col, clear_col = st.columns([3, 1])
    with event_filter_col:
        selected_event_tab6 = st.selectbox(
            "🎯 סנן לפי אירוע:",
            options=["כל האירועים"] + event_options_tab6,
            index=0,
            key="tab6_event_filter"
        )
        st.session_state.tab6_selected_event = selected_event_tab6 if selected_event_tab6 != "כל האירועים" else None
    with clear_col:
        if st.session_state.tab6_selected_event:
            if st.button("🧹 נקה", key="clear_tab6_event"):
                st.session_state.tab6_selected_event = None
                if 'tab6_event_filter' in st.session_state:
                    del st.session_state['tab6_event_filter']
                st.rerun()
    
    # Filters for source comparison
    source_filter_cols = st.columns(3)
    
    with source_filter_cols[0]:
        # Team filter for source comparison
        all_teams_src = set()
        if 'event name' in df.columns:
            for event in df['event name'].dropna().unique():
                teams = extract_teams(str(event))
                for team in teams:
                    if team and len(team) > 1:
                        all_teams_src.add(team.title())
        
        team_options_src = ["כל הקבוצות"] + sorted(list(all_teams_src))
        selected_team_src = st.selectbox("🏆 קבוצה", team_options_src, key="src_team_filter")
    
    with source_filter_cols[1]:
        # Date range for source comparison
        date_options_src = ["הכל", "30 ימים אחרונים", "90 ימים אחרונים", "השנה", "טווח מותאם"]
        selected_date_src = st.selectbox("📅 טווח תאריכים", date_options_src, key="src_date_filter")
    
    with source_filter_cols[2]:
        if selected_date_src == "טווח מותאם":
            custom_range_src = st.date_input("בחר תאריכים", value=(now.date() - timedelta(days=90), now.date()), key="src_custom_date")
        else:
            custom_range_src = None
    
    # Filter data for source comparison
    source_df = df.copy()
    
    # Apply event filter first
    if st.session_state.tab6_selected_event and 'event name' in source_df.columns:
        source_df = source_df[source_df['event name'] == st.session_state.tab6_selected_event]
    
    # Apply team filter
    if selected_team_src != "כל הקבוצות" and 'event name' in source_df.columns:
        def has_team(event_name):
            teams = extract_teams(str(event_name))
            for team in teams:
                if team.title() == selected_team_src:
                    return True
            return False
        source_df = source_df[source_df['event name'].apply(has_team)]
    
    # Apply date filter
    if selected_date_src != "הכל" and 'parsed_date' in source_df.columns:
        if selected_date_src == "30 ימים אחרונים":
            start_date = now - timedelta(days=30)
            source_df = source_df[(source_df['parsed_date'].notna()) & (source_df['parsed_date'] >= start_date)]
        elif selected_date_src == "90 ימים אחרונים":
            start_date = now - timedelta(days=90)
            source_df = source_df[(source_df['parsed_date'].notna()) & (source_df['parsed_date'] >= start_date)]
        elif selected_date_src == "השנה":
            year_start = datetime(now.year, 1, 1)
            source_df = source_df[(source_df['parsed_date'].notna()) & (source_df['parsed_date'] >= year_start)]
        elif selected_date_src == "טווח מותאם" and custom_range_src and len(custom_range_src) == 2:
            start_d, end_d = custom_range_src
            source_df = source_df[
                (source_df['parsed_date'].notna()) &
                (source_df['parsed_date'] >= datetime.combine(start_d, datetime.min.time())) &
                (source_df['parsed_date'] <= datetime.combine(end_d, datetime.max.time()))
            ]
    
    st.markdown("---")
    
    if 'source' in source_df.columns and not source_df.empty:
        # Only include orders with supplier data for profit calculation
        source_with_supp = source_df[source_df['has_supplier_data'] == True].copy()
        
        if not source_with_supp.empty:
            # Add normalized source display name for grouping
            source_with_supp['source_display'] = source_with_supp['source'].apply(get_source_display_name)
            
            # Group by normalized source display name
            agg_dict = {
                'row_index': 'count',
                'Qty': lambda x: pd.to_numeric(x, errors='coerce').sum(),
                'TOTAL_clean': 'sum',
                'SUPP_PRICE_clean': 'sum',
                'profit': 'sum',
                'revenue_net': 'sum',
                'commission_amount': 'sum'
            }
            source_stats = source_with_supp.groupby('source_display').agg(agg_dict).reset_index()
            
            source_stats.columns = ['מקור', 'הזמנות', 'כמות כרטיסים', 'הכנסות', 'עלויות', 'רווח', 'הכנסות_נטו', 'עמלות']
            source_stats['רווח/כרטיס'] = source_stats.apply(
                lambda row: row['רווח'] / row['כמות כרטיסים'] if row['כמות כרטיסים'] > 0 else 0, axis=1
            )
            source_stats['אחוז רווח'] = source_stats.apply(
                lambda row: (row['רווח'] / row['הכנסות_נטו'] * 100) if row['הכנסות_נטו'] > 0 else 0, axis=1
            )
            
            # Sort by profit descending
            source_stats = source_stats.sort_values('רווח', ascending=False)
            
            # Find best performing source
            best_source = source_stats.iloc[0]['מקור'] if len(source_stats) > 0 else None
            
            # Summary metrics
            st.markdown("### 📈 סיכום כללי")
            total_commission_tab6 = source_stats['עמלות'].sum()
            total_tickets_tab6 = int(source_stats['כמות כרטיסים'].sum())
            summary_cols = st.columns(6)
            with summary_cols[0]:
                st.metric("סה\"כ מקורות", len(source_stats))
            with summary_cols[1]:
                st.metric("סה\"כ הזמנות", int(source_stats['הזמנות'].sum()))
            with summary_cols[2]:
                st.metric("📦 סה\"כ כרטיסים", f"{total_tickets_tab6:,}")
            with summary_cols[3]:
                st.metric("סה\"כ רווח", f"€{source_stats['רווח'].sum():,.0f}")
            with summary_cols[4]:
                if total_commission_tab6 > 0:
                    st.metric("💳 עמלות נלקחו", f"-€{total_commission_tab6:,.0f}")
                else:
                    st.metric("💳 עמלות", "€0")
            with summary_cols[5]:
                if best_source:
                    st.metric("🏆 מקור מוביל", best_source)
            
            st.markdown("### 📊 טבלת השוואה")
            
            # Add trophy icon to best source
            source_stats['מקור'] = source_stats.apply(
                lambda row: f"🏆 {row['מקור']}" if row['מקור'] == best_source else row['מקור'], axis=1
            )
            
            display_cols = ['מקור', 'הזמנות', 'כמות כרטיסים', 'הכנסות', 'עמלות', 'עלויות', 'רווח', 'רווח/כרטיס', 'אחוז רווח']
            source_stats_display = source_stats[[c for c in display_cols if c in source_stats.columns]]
            
            st.dataframe(
                source_stats_display.style.format({
                    'הכנסות': '€{:,.0f}',
                    'עמלות': '€{:,.0f}',
                    'עלויות': '€{:,.0f}',
                    'רווח': '€{:,.0f}',
                    'כמות כרטיסים': '{:,.0f}',
                    'רווח/כרטיס': '€{:,.1f}',
                    'אחוז רווח': '{:.1f}%'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Charts
            chart_cols = st.columns(2)
            
            with chart_cols[0]:
                st.markdown("#### 📊 רווח לפי מקור")
                # Reset source names without trophy for chart
                chart_data = source_stats.copy()
                chart_data['מקור'] = chart_data['מקור'].str.replace('🏆 ', '', regex=False)
                
                fig_bar = px.bar(
                    chart_data.head(10), 
                    x='רווח', 
                    y='מקור', 
                    orientation='h',
                    color='רווח',
                    color_continuous_scale='Greens'
                )
                fig_bar.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    showlegend=False,
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with chart_cols[1]:
                st.markdown("#### 🥧 חלוקת מכירות לפי מקור")
                chart_data_pie = source_stats.copy()
                chart_data_pie['מקור'] = chart_data_pie['מקור'].str.replace('🏆 ', '', regex=False)
                
                fig_pie = px.pie(
                    chart_data_pie, 
                    values='הכנסות', 
                    names='מקור',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # Additional analysis
            st.markdown("---")
            st.markdown("### 📈 ניתוח מעמיק")
            
            analysis_cols = st.columns(2)
            
            with analysis_cols[0]:
                st.markdown("#### 💰 רווח ממוצע לכרטיס")
                avg_profit_chart = chart_data.copy()
                avg_profit_chart = avg_profit_chart.sort_values('רווח/כרטיס', ascending=False)
                
                fig_avg = px.bar(
                    avg_profit_chart.head(10),
                    x='רווח/כרטיס',
                    y='מקור',
                    orientation='h',
                    color='רווח/כרטיס',
                    color_continuous_scale='Blues'
                )
                fig_avg.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    showlegend=False,
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_avg, use_container_width=True)
            
            with analysis_cols[1]:
                st.markdown("#### 📊 אחוז רווח לפי מקור")
                margin_chart = chart_data.copy()
                margin_chart = margin_chart.sort_values('אחוז רווח', ascending=False)
                
                fig_margin = px.bar(
                    margin_chart.head(10),
                    x='אחוז רווח',
                    y='מקור',
                    orientation='h',
                    color='אחוז רווח',
                    color_continuous_scale='Oranges'
                )
                fig_margin.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    showlegend=False,
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_margin, use_container_width=True)
        
        else:
            st.warning("אין הזמנות עם נתוני ספק בטווח הנבחר")
    else:
        st.warning("לא נמצאה עמודת מקור בנתונים")

with tab7:
    st.header("📧 מיילים אוטומטיים")
    st.markdown("ניהול ושליחה ידנית של דוחות אוטומטיים")
    
    st.markdown("---")
    
    st.subheader("📅 לוח זמנים מתוזמן")
    schedule_info = """
    | דוח | שעה | תיאור |
    |-----|-----|-------|
    | 🔴 תזכורת הזמנות לא שולמו | 10:00 | מייל לאופרציה עם הזמנות בסטטוס "נשלח ולא שולם" |
    | 💰 דוח מכירות יומי | 10:05 | סיכום מכירות יומי |
    | 📦 דוח הזמנות חדשות | 20:00 | הזמנות חדשות שטרם טופלו |
    | 📊 דוח מכירות שבועי | יום א' 09:00 | סיכום שבועי של מכירות |
    """
    st.markdown(schedule_info)
    
    st.markdown("---")
    st.subheader("🚀 שליחה ידנית")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔴 הזמנות לא שולמו")
        if st.button("📤 שלח עכשיו", key="send_unpaid_now"):
            with st.spinner("בודק הזמנות ושולח מייל..."):
                try:
                    from daily_reminder import get_unpaid_orders, send_daily_reminder_email
                    orders = get_unpaid_orders()
                    if orders:
                        success = send_daily_reminder_email(orders)
                        if success:
                            st.success(f"✅ נשלח בהצלחה! נמצאו {len(orders)} הזמנות לא שולמו")
                        else:
                            st.error("❌ שגיאה בשליחה")
                    else:
                        st.info("✅ אין הזמנות לא שולמו")
                except Exception as e:
                    st.error(f"שגיאה: {e}")
        
        unpaid_count = 0
        try:
            from daily_reminder import get_unpaid_orders
            unpaid_orders = get_unpaid_orders()
            unpaid_count = len(unpaid_orders)
        except:
            pass
        if unpaid_count > 0:
            st.warning(f"📋 {unpaid_count} הזמנות ממתינות לתשלום")
        else:
            st.success("✅ אין הזמנות לא שולמו")
    
    with col2:
        st.markdown("#### 📦 הזמנות חדשות")
        if st.button("📤 שלח עכשיו", key="send_new_orders_now"):
            with st.spinner("בודק הזמנות ושולח מייל..."):
                try:
                    from daily_new_orders_report import get_new_orders, send_daily_report_email, DEFAULT_EMAIL
                    orders_df = get_new_orders()
                    if not orders_df.empty:
                        success = send_daily_report_email(orders_df, DEFAULT_EMAIL)
                        if success:
                            st.success(f"✅ נשלח בהצלחה! {len(orders_df)} הזמנות חדשות")
                        else:
                            st.error("❌ שגיאה בשליחה")
                    else:
                        st.info("✅ אין הזמנות חדשות")
                except Exception as e:
                    st.error(f"שגיאה: {e}")
    
    st.markdown("---")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("#### 💰 דוח מכירות יומי")
        if st.button("📤 שלח עכשיו", key="send_daily_sales_now"):
            with st.spinner("מכין ושולח דוח..."):
                try:
                    from daily_sales_report import get_todays_orders, send_daily_sales_email, DEFAULT_EMAIL
                    orders_df = get_todays_orders()
                    if not orders_df.empty:
                        success = send_daily_sales_email(orders_df, DEFAULT_EMAIL)
                        if success:
                            st.success(f"✅ נשלח בהצלחה! {len(orders_df)} הזמנות היום")
                        else:
                            st.error("❌ שגיאה בשליחה")
                    else:
                        st.info("אין הזמנות להיום")
                except Exception as e:
                    st.error(f"שגיאה: {e}")
    
    with col4:
        st.markdown("#### 📊 דוח מכירות שבועי")
        if st.button("📤 שלח עכשיו", key="send_weekly_sales_now"):
            with st.spinner("מכין ושולח דוח..."):
                try:
                    from weekly_sales_report import get_weekly_orders, send_weekly_sales_email, DEFAULT_EMAIL
                    orders_df, start_of_week, end_of_week = get_weekly_orders()
                    if not orders_df.empty:
                        success = send_weekly_sales_email(orders_df, start_of_week, end_of_week, DEFAULT_EMAIL)
                        if success:
                            st.success(f"✅ נשלח בהצלחה! {len(orders_df)} הזמנות השבוע")
                        else:
                            st.error("❌ שגיאה בשליחה")
                    else:
                        st.info("אין הזמנות השבוע")
                except Exception as e:
                    st.error(f"שגיאה: {e}")
    
    st.markdown("---")
    st.info("💡 המיילים האוטומטיים נשלחים כאשר המתזמן פעיל. להפעלת המתזמן, הפעל את ה-workflow 'Email Scheduler'.")

st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: gray; font-size: 0.8em;'>"
    f"{t('footer')}"
    f"</div>",
    unsafe_allow_html=True
)
