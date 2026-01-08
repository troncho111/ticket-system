"""
Utility functions for the ticket system
פונקציות עזר למערכת הכרטיסים
"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from io import BytesIO
import json

def export_to_excel(df, filename_prefix="orders"):
    """Export DataFrame to Excel format"""
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Orders')
        output.seek(0)
        return output.getvalue()
    except ImportError:
        # Fallback to CSV if openpyxl not available
        return df.to_csv(index=False).encode('utf-8-sig')

def export_to_csv(df, filename_prefix="orders"):
    """Export DataFrame to CSV format"""
    return df.to_csv(index=False).encode('utf-8-sig')

def get_smart_alerts(df, docket_col=None, status_col=None, event_date_col=None):
    """Generate smart alerts based on data"""
    alerts = []
    
    if df.empty:
        return alerts
    
    # Alert 1: Orders without docket
    if docket_col and docket_col in df.columns:
        no_docket = df[
            (df[docket_col].isna()) | 
            (df[docket_col].astype(str).str.strip().isin(['', '-']))
        ]
        if len(no_docket) > 0:
            alerts.append({
                'type': 'warning',
                'icon': '⚠️',
                'title': 'הזמנות ללא דוקט',
                'count': len(no_docket),
                'message': f'{len(no_docket)} הזמנות ללא מספר דוקט - ייתכן שלא שולמו'
            })
    
    # Alert 2: Orders without supplier data
    if 'has_supplier_data' in df.columns:
        no_supplier = df[df['has_supplier_data'] == False]
        if len(no_supplier) > 0:
            alerts.append({
                'type': 'info',
                'icon': '📦',
                'title': 'הזמנות ללא נתוני ספק',
                'count': len(no_supplier),
                'message': f'{len(no_supplier)} הזמנות ללא נתוני ספק - צריך לעדכן'
            })
    
    # Alert 3: Upcoming events (next 7 days)
    if event_date_col and event_date_col in df.columns:
        try:
            now = datetime.now()
            next_week = now + timedelta(days=7)
            
            # Try to parse dates
            df_copy = df.copy()
            df_copy['_parsed_date'] = pd.to_datetime(df_copy[event_date_col], errors='coerce')
            upcoming = df_copy[
                (df_copy['_parsed_date'].notna()) &
                (df_copy['_parsed_date'] >= now) &
                (df_copy['_parsed_date'] <= next_week)
            ]
            
            if len(upcoming) > 0:
                alerts.append({
                    'type': 'success',
                    'icon': '📅',
                    'title': 'אירועים קרובים',
                    'count': len(upcoming),
                    'message': f'{len(upcoming)} הזמנות לאירועים ב-7 הימים הקרובים'
                })
        except:
            pass
    
    # Alert 4: New orders waiting
    if status_col and status_col in df.columns:
        new_orders = df[df[status_col].astype(str).str.lower().str.strip() == 'new']
        if len(new_orders) > 0:
            alerts.append({
                'type': 'error',
                'icon': '🔴',
                'title': 'הזמנות חדשות',
                'count': len(new_orders),
                'message': f'{len(new_orders)} הזמנות חדשות ממתינות לטיפול'
            })
    
    return alerts

def save_search_query(query_name, filters, session_key='saved_searches'):
    """Save a search query for later use"""
    if session_key not in st.session_state:
        st.session_state[session_key] = {}
    
    st.session_state[session_key][query_name] = {
        'filters': filters,
        'created_at': datetime.now().isoformat()
    }

def load_saved_searches(session_key='saved_searches'):
    """Load saved search queries"""
    if session_key not in st.session_state:
        return {}
    return st.session_state[session_key]

def create_change_log(action, order_id, old_value, new_value, user='system'):
    """Create a change log entry"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'order_id': order_id,
        'old_value': old_value,
        'new_value': new_value,
        'user': user
    }
    
    # Store in session state (in production, use database)
    if 'change_log' not in st.session_state:
        st.session_state['change_log'] = []
    
    st.session_state['change_log'].append(log_entry)
    
    # Keep only last 100 entries
    if len(st.session_state['change_log']) > 100:
        st.session_state['change_log'] = st.session_state['change_log'][-100:]
    
    return log_entry

def get_recent_changes(limit=10):
    """Get recent changes from log"""
    if 'change_log' not in st.session_state:
        return []
    
    return st.session_state['change_log'][-limit:][::-1]  # Most recent first
