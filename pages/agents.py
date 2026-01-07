import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import re
import os

st.set_page_config(
    page_title="הנהלת חשבונות - סוכנים",
    page_icon="💼",
    layout="wide"
)

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        direction: rtl;
    }
    [data-testid="stSidebar"] {
        direction: rtl;
        text-align: right;
    }
    .stMarkdown, .stText, h1, h2, h3, h4, p {
        text-align: right;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        text-align: center;
    }
    .missing-docket {
        background-color: #ffebee !important;
    }
    /* Center align table cells */
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th,
    [data-testid="stDataEditor"] td, [data-testid="stDataEditor"] th {
        text-align: center !important;
        vertical-align: middle !important;
    }
    [data-testid="stDataEditor"] [data-testid="column-header-name"] {
        text-align: center !important;
    }
</style>
""", unsafe_allow_html=True)

SHEET_NAME = "מערכת הזמנות - קוד יהודה  "
WORKSHEET_INDEX = 0

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
            creds_dict = creds_json
        elif isinstance(creds_json, str):
            creds_dict = json.loads(creds_json)
        else:
            creds_dict = dict(creds_json)
        
        # Ensure private_key is properly formatted (handle escaped newlines)
        if 'private_key' in creds_dict and isinstance(creds_dict['private_key'], str):
            private_key = creds_dict['private_key']
            import re
            private_key = re.sub(r'\\{2,}n', '\n', private_key)
            if '\\n' in private_key:
                private_key = private_key.replace('\\n', '\n')
            if '-----BEGIN PRIVATE KEY----- ' in private_key:
                private_key = private_key.replace('-----BEGIN PRIVATE KEY----- ', '-----BEGIN PRIVATE KEY-----\n')
            
            if '-----BEGIN PRIVATE KEY-----' not in private_key or '-----END PRIVATE KEY-----' not in private_key:
                raise ValueError("private_key לא תקין - חסרים BEGIN/END markers")
            
            if '\n' not in private_key:
                begin_idx = private_key.find('-----BEGIN PRIVATE KEY-----')
                end_idx = private_key.find('-----END PRIVATE KEY-----')
                if begin_idx >= 0 and end_idx > begin_idx:
                    begin_marker = '-----BEGIN PRIVATE KEY-----'
                    end_marker = '-----END PRIVATE KEY-----'
                    key_content = private_key[begin_idx + len(begin_marker):end_idx].strip()
                    key_content = key_content.replace(' ', '')
                    key_lines = [key_content[i:i+64] for i in range(0, len(key_content), 64)]
                    private_key = f'{begin_marker}\n' + '\n'.join(key_lines) + f'\n{end_marker}\n'
            
            if not private_key.startswith('-----BEGIN PRIVATE KEY-----\n'):
                private_key = private_key.replace('-----BEGIN PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----\n', 1)
            if not private_key.rstrip().endswith('\n-----END PRIVATE KEY-----'):
                private_key = private_key.replace('-----END PRIVATE KEY-----', '\n-----END PRIVATE KEY-----', 1)
            
            creds_dict['private_key'] = private_key
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in GOOGLE_CREDENTIALS: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error parsing GOOGLE_CREDENTIALS: {str(e)}")
    
    required_fields = ['type', 'project_id', 'private_key', 'client_email']
    missing_fields = [f for f in required_fields if f not in creds_dict]
    if missing_fields:
        raise ValueError(f"Missing required fields in GOOGLE_CREDENTIALS: {', '.join(missing_fields)}")
    
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        raise ValueError(f"Error creating gspread client: {str(e)}")

def find_column(df, *keywords):
    """Find column containing all keywords (case-insensitive)"""
    for col in df.columns:
        col_lower = col.lower()
        if all(kw.lower() in col_lower for kw in keywords):
            return col
    return None

@st.cache_data(ttl=300)
def load_data_from_sheet():
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        data = worksheet.get_all_values()
        
        if len(data) < 2:
            return pd.DataFrame()
        
        headers = [str(h).strip() for h in data[0]]
        rows = data[1:]
        
        df = pd.DataFrame(rows, columns=headers)
        df['row_index'] = range(2, len(df) + 2)
        df.columns = [col.strip() for col in df.columns]
        
        return df
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def update_docket_number(row_index, new_docket):
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        cell_address = f"E{row_index}"
        worksheet.update_acell(cell_address, str(new_docket))
        
        return True, f"מספר דוקט עודכן בהצלחה בשורה {row_index}"
    except Exception as e:
        return False, f"שגיאה בעדכון: {str(e)}"

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
    """Add a new order row to Google Sheets"""
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME)
        worksheet = sheet.get_worksheet(WORKSHEET_INDEX)
        
        headers = worksheet.row_values(1)
        
        new_row = [''] * len(headers)
        
        column_mapping = {
            'order date': 0,        # A (index 0)
            'orderd': 1,            # B (index 1)
            'source': 2,            # C (index 2)
            'Order number': 3,      # D (index 3)
            'docket number': 4,     # E (index 4)
            'event name': 5,        # F (index 5)
            'Date of the event': 6, # G (index 6)
            'Category / Section': 8, # I (index 8)
            'Qty': 10,              # K (index 10)
            'Price sold': 11,       # L (index 11) - numeric value
            'TOTAL': 12,            # M (index 12) - qty × price
        }
        
        for key, col_idx in column_mapping.items():
            if key in order_data and col_idx < len(new_row):
                new_row[col_idx] = order_data[key]
        
        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
        
        return True, "הזמנה חדשה נוספה בהצלחה!"
    except Exception as e:
        return False, f"שגיאה בהוספת הזמנה: {str(e)}"

def get_unique_sources(df):
    """Get list of unique sources from dataframe"""
    if 'source' in df.columns:
        sources = df['source'].dropna().unique().tolist()
        return sorted([s for s in sources if s and str(s).strip()])
    return []

def get_unique_events(df):
    """Get list of unique events with their dates"""
    events = {}
    if 'event name' in df.columns:
        for idx, row in df.iterrows():
            event = row.get('event name', '')
            date = row.get('Date of the event', '')
            if event and str(event).strip():
                events[str(event).strip()] = str(date).strip() if date else ''
    return events

def display_field_with_copy(label, value, key):
    safe_value = str(value) if value and str(value) != '-' else '-'
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(f"**{label}:**")
    with col2:
        st.code(safe_value, language=None)

def get_value(row, col_name, default='-'):
    """Safely get value from row"""
    if col_name and col_name in row.index:
        val = row.get(col_name, default)
        return val if val and str(val).strip() else default
    return default

def find_column_in_row(row, *keywords):
    """Find column in row index containing all keywords"""
    for col in row.index:
        col_lower = str(col).lower()
        if all(kw.lower() in col_lower for kw in keywords):
            return col
    return None

def show_order_details(row, docket_col, unique_key=""):
    order_num = get_value(row, 'Order number')
    st.success(f"✅ נמצאה הזמנה: **{order_num}**")
    
    supplier_name = get_value(row, 'Supplier NAME')
    supp_price = get_value(row, 'SUPP PRICE')
    
    supp_order_col = find_column_in_row(row, 'supp', 'order')
    supp_order = get_value(row, supp_order_col) if supp_order_col else '-'
    
    event_name = get_value(row, 'event name')
    event_date = get_value(row, 'Date of the event')
    docket = get_value(row, docket_col) if docket_col else '-'
    source = get_value(row, 'source')
    status = get_value(row, 'orderd')
    total_sold = get_value(row, 'total sold')
    qty = get_value(row, 'Qty') if 'Qty' in row.index else get_value(row, 'QTY')
    row_idx = row.get('row_index', None) if 'row_index' in row.index else None
    # Original prices with currency (columns L and M)
    price_sold_original = get_value(row, 'Price sold')
    total_original = get_value(row, 'TOTAL')
    
    all_data_text = f"""מספר הזמנה: {order_num}
שם אירוע: {event_name}
מספר דוקט: {docket}
ספק: {source}
מספר הזמנה ספק: {supp_order}
תאריך אירוע: {event_date}
כמות: {qty}
מחיר מקורי לכרטיס: {price_sold_original}
מחיר מקורי טוטל: {total_original}
מחיר ספק: {supp_price}
מחיר מכירה (€): {total_sold}
שם ספק: {supplier_name}
סטטוס: {status}"""
    
    st.markdown("### ⚡ העתקה מהירה")
    st.markdown("<div style='background: #e8f4f8; padding: 15px; border-radius: 10px; border-left: 4px solid #1E88E5;'>", unsafe_allow_html=True)
    
    quick_copy_fields = [
        ("מספר הזמנה", order_num),
        ("מספר דוקט", docket),
        ("שם אירוע", event_name),
        ("מספר הזמנה ספק", supp_order),
        ("מחיר מקורי לכרטיס", price_sold_original),
        ("מחיר מקורי טוטל", total_original),
    ]
    
    for label, value in quick_copy_fields:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"**{label}:**")
        with col2:
            safe_val = str(value) if value and str(value) != '-' else '-'
            st.code(safe_val, language="text")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    current_docket = str(docket) if docket and str(docket) != '-' else ''
    docket_is_empty = not current_docket or current_docket == '-' or current_docket.strip() == ''
    
    if docket_is_empty:
        st.warning("⚠️ להזמנה זו אין מספר דוקט - ייתכן שלא שולם")
    
    st.markdown("### ✏️ עדכון מספר דוקט")
    
    # Use form to prevent rerun on input change - only update on button click
    with st.form(key=f"docket_form_{unique_key}_{order_num}", clear_on_submit=False):
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            new_docket = st.text_input(
                "מספר דוקט חדש:",
                value="" if docket_is_empty else "",
                placeholder=f"נוכחי: {docket}" if not docket_is_empty else "הזן מספר דוקט",
                key=f"docket_input_{unique_key}_{order_num}"
            )
        
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            update_clicked = st.form_submit_button("✅ עדכן", type="primary", use_container_width=True)
    
    if update_clicked:
        if new_docket and new_docket.strip() and row_idx:
            with st.spinner("מעדכן בגוגל שיטס..."):
                success, message = update_docket_number(row_idx, new_docket.strip())
                if success:
                    load_data_from_sheet.clear()
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.info(f"דוקט עודכן: `{docket}` ➜ `{new_docket}` להזמנה {order_num}")
                else:
                    st.error(f"❌ {message}")
        elif not new_docket or not new_docket.strip():
            st.warning("יש להזין מספר דוקט חדש")
        else:
            st.error("לא נמצא מספר שורה לעדכון")
    
    st.markdown("---")
    st.markdown("**📋 העתק הכל:**")
    st.code(all_data_text, language="text")
    
    with st.expander("📦 פרטי ספק נוספים"):
        display_field_with_copy("שם ספק", supplier_name, f"supplier_{unique_key}")
        display_field_with_copy("מחיר ספק", supp_price, f"price_{unique_key}")
    
    with st.expander("🎫 פרטי אירוע נוספים"):
        display_field_with_copy("תאריך", event_date, f"date_{unique_key}")
        display_field_with_copy("מקור", source, f"source_{unique_key}")
        display_field_with_copy("כמות", qty, f"qty_{unique_key}")
    
    with st.expander("💳 פרטי הזמנה נוספים"):
        display_field_with_copy("סטטוס", status, f"status_{unique_key}")
        display_field_with_copy("מחיר מקורי לכרטיס", price_sold_original, f"price_orig_{unique_key}")
        display_field_with_copy("מחיר מקורי טוטל", total_original, f"total_orig_{unique_key}")
        display_field_with_copy("מחיר מכירה (€)", total_sold, f"total_sold_{unique_key}")

df = load_data_from_sheet()

DOCKET_COL = find_column(df, 'docket', 'number')
ORDER_COL = 'Order number' if 'Order number' in df.columns else None
SUPPLIER_COL = 'Supplier NAME' if 'Supplier NAME' in df.columns else None
STATUS_COL = 'orderd' if 'orderd' in df.columns else None

if 'selected_order_idx' not in st.session_state:
    st.session_state.selected_order_idx = None

if 'agents_active_tab' not in st.session_state:
    st.session_state.agents_active_tab = "🔍 חיפוש הזמנות"

st.header("💼 הנהלת חשבונות - סוכנים")

TAB_OPTIONS = ["🔍 חיפוש הזמנות", "📦 ניהול ספקים", "➕ הוספה ידנית"]

selected_tab = st.radio(
    "",
    TAB_OPTIONS,
    index=TAB_OPTIONS.index(st.session_state.agents_active_tab),
    horizontal=True,
    key="agents_tab_selector"
)

if selected_tab != st.session_state.agents_active_tab:
    st.session_state.agents_active_tab = selected_tab

st.markdown("---")

if selected_tab == "🔍 חיפוש הזמנות":
    st.subheader("🔍 חיפוש הזמנות")
    st.markdown("חיפוש מהיר של נתוני ספק לפי מספר הזמנה, דוקט או מספר הזמנה ספק + עדכון מספר דוקט")
    
    st.markdown("---")
    search_query = st.text_input(
        "🔍 הזן מספר הזמנה (Order number), דוקט (docket number) או מספר הזמנה ספק (SUPP order number):",
        placeholder="לדוגמה: 5498 או 111599 או 28623487",
        key="accounting_search"
    )
    
    if search_query:
        search_query = search_query.strip()
        
        if ORDER_COL or DOCKET_COL:
            results_list = []
            seen_indices = set()
            
            if ORDER_COL:
                order_matches = df[df[ORDER_COL].astype(str).str.contains(search_query, case=False, na=False)]
                for idx, row in order_matches.iterrows():
                    if idx not in seen_indices:
                        seen_indices.add(idx)
                        results_list.append({'row': row, 'found_in': '🔢 מספר הזמנה', 'original_idx': idx})
            
            if DOCKET_COL:
                docket_matches = df[df[DOCKET_COL].astype(str).str.contains(search_query, case=False, na=False)]
                for idx, row in docket_matches.iterrows():
                    if idx not in seen_indices:
                        seen_indices.add(idx)
                        results_list.append({'row': row, 'found_in': '📄 מספר דוקט', 'original_idx': idx})
            
            if 'SUPP order number' in df.columns:
                supp_order_matches = df[df['SUPP order number'].astype(str).str.contains(search_query, case=False, na=False)]
                for idx, row in supp_order_matches.iterrows():
                    if idx not in seen_indices:
                        seen_indices.add(idx)
                        results_list.append({'row': row, 'found_in': '📦 מספר הזמנה ספק', 'original_idx': idx})
            
            if results_list:
                results = pd.DataFrame([r['row'] for r in results_list])
                found_in_list = [r['found_in'] for r in results_list]
            else:
                results = pd.DataFrame()
                found_in_list = []
        else:
            results = pd.DataFrame()
            found_in_list = []
        
        if len(results) == 0:
            st.session_state.selected_order_idx = None
            st.warning(f"⚠️ לא נמצאה הזמנה עם המספר: **{search_query}**")
        
        elif len(results) == 1:
            st.session_state.selected_order_idx = None
            row = results.iloc[0]
            show_order_details(row, DOCKET_COL, unique_key="single")
        
        else:
            if st.session_state.selected_order_idx is not None:
                if st.button("← חזור לתוצאות", key="back_to_results"):
                    st.session_state.selected_order_idx = None
                    st.rerun()
                
                selected_idx = st.session_state.selected_order_idx
                if selected_idx < len(results):
                    row = results.iloc[selected_idx]
                    show_order_details(row, DOCKET_COL, unique_key=f"multi_{selected_idx}")
                else:
                    st.session_state.selected_order_idx = None
                    st.rerun()
            else:
                st.info(f"📊 נמצאו **{len(results)}** הזמנות תואמות")
                
                st.markdown("**בחר הזמנה לצפייה בפרטים:**")
                
                for i, (idx, row) in enumerate(results.iterrows()):
                    order_num = get_value(row, ORDER_COL)
                    docket_num = get_value(row, DOCKET_COL) if DOCKET_COL else '-'
                    event = get_value(row, 'event name')
                    found_in = found_in_list[i] if i < len(found_in_list) else ''
                    
                    has_docket = docket_num and str(docket_num).strip() and str(docket_num) != '-'
                    docket_indicator = "✅" if has_docket else "❌"
                    
                    col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1.5, 0.5, 2.5, 1.5, 1.5])
                    with col1:
                        st.markdown(f"**{order_num}**")
                    with col2:
                        st.markdown(f"{docket_num if has_docket else '-'}")
                    with col3:
                        st.markdown(docket_indicator)
                    with col4:
                        st.markdown(f"{event[:35]}..." if len(str(event)) > 35 else str(event))
                    with col5:
                        st.markdown(f"<span style='font-size: 0.85em;'>{found_in}</span>", unsafe_allow_html=True)
                    with col6:
                        if st.button("📋 פרטים", key=f"select_order_{i}"):
                            st.session_state.selected_order_idx = i
                            st.rerun()
                    
                    st.markdown("<hr style='margin: 5px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
                
                st.caption("💡 לחץ על 'פרטים' לצפייה בפרטים המלאים ועדכון דוקט")
    
    else:
        st.info("""
        💡 **איך להשתמש:**
        1. הזן מספר הזמנה (Order number) או דוקט
        2. לחץ Enter או המתן
        3. צפה בפרטי ההזמנה
        4. עדכן מספר דוקט במידת הצורך
        
        **דוגמאות:**
        - `5498`
        - `111599`
        - `5536`
        """)
        
        st.markdown("---")
        st.markdown("### 📊 סטטיסטיקות מהירות")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_orders = len(df)
            st.metric("סך הזמנות", total_orders)
        
        with col2:
            if DOCKET_COL:
                with_docket = len(df[df[DOCKET_COL].notna() & (df[DOCKET_COL].astype(str).str.strip() != '')])
            else:
                with_docket = 0
            st.metric("עם דוקט", with_docket)
        
        with col3:
            without_docket = total_orders - with_docket
            st.metric("ללא דוקט ⚠️", without_docket)

elif selected_tab == "📦 ניהול ספקים":
    st.subheader("📦 ניהול ספקים")
    st.markdown("צפייה וסינון הזמנות לפי ספק")
    
    st.markdown("---")
    
    SOURCE_COL_FILTER = find_column(df, 'source')
    EVENT_COL = find_column(df, 'event', 'name')
    
    col_top = st.columns([1, 1, 4])
    with col_top[0]:
        show_missing_docket = st.checkbox(
            "⚠️ רק ללא דוקט",
            value=False,
            key="missing_docket_filter"
        )
    with col_top[1]:
        if st.button("🔄 רענן נתונים", key="refresh_supplier_data"):
            load_data_from_sheet.clear()
            st.session_state['data_refreshed'] = True
    
    if st.session_state.get('data_refreshed'):
        st.success("✅ הנתונים עודכנו!")
        st.session_state['data_refreshed'] = False
    
    filtered_df = df.copy()
    
    if show_missing_docket and DOCKET_COL:
        filtered_df = filtered_df[
            (filtered_df[DOCKET_COL].isna()) | 
            (filtered_df[DOCKET_COL].astype(str).str.strip() == '') |
            (filtered_df[DOCKET_COL].astype(str).str.strip() == '-')
        ]
    
    st.markdown("---")
    
    col_metrics = st.columns(4)
    with col_metrics[0]:
        st.metric("📊 סך הזמנות מסוננות", len(filtered_df))
    
    with col_metrics[1]:
        if DOCKET_COL:
            with_docket = len(filtered_df[
                (filtered_df[DOCKET_COL].notna()) & 
                (filtered_df[DOCKET_COL].astype(str).str.strip() != '') &
                (filtered_df[DOCKET_COL].astype(str).str.strip() != '-')
            ])
        else:
            with_docket = 0
        st.metric("✅ עם דוקט", with_docket)
    
    with col_metrics[2]:
        without_docket = len(filtered_df) - with_docket
        st.metric("❌ ללא דוקט", without_docket)
    
    with col_metrics[3]:
        if len(filtered_df) > 0:
            pct_without = (without_docket / len(filtered_df)) * 100
            st.metric("⚠️ אחוז ללא דוקט", f"{pct_without:.1f}%")
        else:
            st.metric("⚠️ אחוז ללא דוקט", "0%")
    
    st.markdown("---")
    
    if len(filtered_df) == 0:
        st.warning("לא נמצאו הזמנות התואמות לסינון")
    else:
        ordered_cols = ['row_index']
        col_mapping = {'row_index': 'שורה'}
        
        ORDER_DATE_COL = find_column(df, 'order', 'date')
        if not ORDER_DATE_COL:
            for col in df.columns:
                if col.lower().strip() in ['order date', 'orderdate', 'date']:
                    ORDER_DATE_COL = col
                    break
        
        if ORDER_DATE_COL and ORDER_DATE_COL in filtered_df.columns:
            ordered_cols.append(ORDER_DATE_COL)
            col_mapping[ORDER_DATE_COL] = 'תאריך הזמנה'
        
        STATUS_COL = 'orderd' if 'orderd' in filtered_df.columns else None
        if STATUS_COL and STATUS_COL in filtered_df.columns:
            ordered_cols.append(STATUS_COL)
            col_mapping[STATUS_COL] = 'סטטוס'
        
        SOURCE_COL = find_column(df, 'source')
        TOTAL_SOLD_COL = find_column(df, 'total', 'sold')
        
        if SOURCE_COL and SOURCE_COL in filtered_df.columns:
            ordered_cols.append(SOURCE_COL)
            col_mapping[SOURCE_COL] = 'ספק/מקור'
        
        if ORDER_COL and ORDER_COL in filtered_df.columns:
            ordered_cols.append(ORDER_COL)
            col_mapping[ORDER_COL] = 'מספר הזמנה'
        
        if DOCKET_COL and DOCKET_COL in filtered_df.columns:
            ordered_cols.append(DOCKET_COL)
            col_mapping[DOCKET_COL] = 'מספר דוקט'
        
        if 'event name' in filtered_df.columns:
            ordered_cols.append('event name')
            col_mapping['event name'] = 'שם אירוע'
        
        if TOTAL_SOLD_COL and TOTAL_SOLD_COL in filtered_df.columns:
            ordered_cols.append(TOTAL_SOLD_COL)
            col_mapping[TOTAL_SOLD_COL] = 'סה"כ מחיר'
        
        SUPP_PRICE_COL = find_column(df, 'supp', 'price')
        if SUPP_PRICE_COL and SUPP_PRICE_COL in filtered_df.columns:
            ordered_cols.append(SUPP_PRICE_COL)
            col_mapping[SUPP_PRICE_COL] = 'עלות ספק'
        
        if 'Supplier NAME' in filtered_df.columns:
            ordered_cols.append('Supplier NAME')
            col_mapping['Supplier NAME'] = 'שם ספק'
        
        if 'SUPP order number' in filtered_df.columns:
            ordered_cols.append('SUPP order number')
            col_mapping['SUPP order number'] = 'מספר הזמנה ספק'
        
        if ordered_cols:
            edit_df = filtered_df[ordered_cols].copy()
            
            if 'orderd' in edit_df.columns:
                def format_status_agents(status_val):
                    if pd.isna(status_val) or str(status_val).strip() == '':
                        return ''
                    status_lower = str(status_val).lower().strip()
                    if status_lower == 'new':
                        return '\u200f🔴 חדש\u200f'
                    elif status_lower in ['ordered', 'orderd']:
                        return '\u200f📦 הוזמן\u200f'
                    elif status_lower in ['done', 'done!']:
                        return '\u200f✅ הושלם\u200f'
                    elif 'old' in status_lower or 'no data' in status_lower:
                        return '\u200f⚪ ללא נתונים\u200f'
                    elif 'נשלח ולא שולם' in str(status_val) or 'sent unpaid' in status_lower:
                        return '\u200f🟠 נשלח ולא שולם\u200f'
                    else:
                        return f'\u200f🟡 {status_val}\u200f'
                edit_df['orderd'] = edit_df['orderd'].apply(format_status_agents)
            
            st.markdown("### 🔍 פילטור טבלה")
            
            ORDER_DATE_COL_NAME = ORDER_DATE_COL if ORDER_DATE_COL else 'order date'
            if ORDER_DATE_COL_NAME in edit_df.columns:
                edit_df['_date_parsed'] = pd.to_datetime(edit_df[ORDER_DATE_COL_NAME], dayfirst=True, errors='coerce')
                valid_dates = edit_df['_date_parsed'].dropna()
                
                if len(valid_dates) > 0:
                    months_available = valid_dates.dt.to_period('M').unique()
                    month_names = {
                        1: 'ינואר', 2: 'פברואר', 3: 'מרץ', 4: 'אפריל',
                        5: 'מאי', 6: 'יוני', 7: 'יולי', 8: 'אוגוסט',
                        9: 'ספטמבר', 10: 'אוקטובר', 11: 'נובמבר', 12: 'דצמבר'
                    }
                    month_options = []
                    for m in sorted(months_available, reverse=True):
                        month_label = f"{month_names[m.month]} {m.year}"
                        month_options.append((month_label, m))
                    
                    min_date = valid_dates.min().date()
                    max_date = valid_dates.max().date()
                else:
                    month_options = []
                    min_date = datetime.now().date()
                    max_date = datetime.now().date()
            else:
                month_options = []
                min_date = datetime.now().date()
                max_date = datetime.now().date()
            
            date_filter_cols = st.columns([2, 2, 2, 1])
            
            with date_filter_cols[0]:
                date_filter_type = st.radio(
                    "📅 סינון תאריך:",
                    ["הכל", "חודש", "טווח תאריכים"],
                    horizontal=True,
                    key="date_filter_type"
                )
            
            selected_month = None
            date_range_start = None
            date_range_end = None
            
            with date_filter_cols[1]:
                if date_filter_type == "חודש" and month_options:
                    month_labels = [m[0] for m in month_options]
                    selected_month_label = st.selectbox("בחר חודש:", month_labels, key="month_select")
                    for label, period in month_options:
                        if label == selected_month_label:
                            selected_month = period
                            break
            
            with date_filter_cols[2]:
                if date_filter_type == "טווח תאריכים":
                    date_range = st.date_input(
                        "מתאריך - עד תאריך:",
                        value=(min_date, max_date),
                        min_value=min_date,
                        max_value=max_date,
                        format="DD/MM/YYYY",
                        key="date_range_input"
                    )
                    if isinstance(date_range, tuple) and len(date_range) == 2:
                        date_range_start, date_range_end = date_range
            
            with date_filter_cols[3]:
                if date_filter_type != "הכל":
                    st.info("בחר 'הכל' לניקוי")
            
            if '_date_parsed' in edit_df.columns:
                if date_filter_type == "חודש" and selected_month:
                    edit_df = edit_df[edit_df['_date_parsed'].dt.to_period('M') == selected_month]
                elif date_filter_type == "טווח תאריכים" and date_range_start and date_range_end:
                    edit_df = edit_df[
                        (edit_df['_date_parsed'].dt.date >= date_range_start) &
                        (edit_df['_date_parsed'].dt.date <= date_range_end)
                    ]
                edit_df = edit_df.drop(columns=['_date_parsed'], errors='ignore')
            
            if 'filter_token' not in st.session_state:
                st.session_state['filter_token'] = 0
            filter_token = st.session_state['filter_token']
            
            if 'applied_supplier_filters' not in st.session_state:
                st.session_state['applied_supplier_filters'] = None
            
            filter_cols = st.columns([1, 1, 1, 1, 0.5, 0.5])
            
            with filter_cols[0]:
                if SOURCE_COL and SOURCE_COL in edit_df.columns:
                    source_vals = sorted(edit_df[SOURCE_COL].dropna().unique().tolist())
                    tbl_sources = st.multiselect("ספק/מקור:", source_vals, key=f"tbl_source_filter_{filter_token}", placeholder="הכל")
                else:
                    tbl_sources = []
            
            with filter_cols[1]:
                if 'event name' in edit_df.columns:
                    event_vals = sorted(edit_df['event name'].dropna().unique().tolist())
                    tbl_event = st.selectbox("שם אירוע:", ["הכל"] + event_vals, key=f"tbl_event_filter_{filter_token}")
                else:
                    tbl_event = "הכל"
            
            with filter_cols[2]:
                if 'Supplier NAME' in edit_df.columns:
                    supp_vals = sorted([s for s in edit_df['Supplier NAME'].dropna().unique().tolist() if s])
                    tbl_supps = st.multiselect("שם ספק:", supp_vals, key=f"tbl_supp_filter_{filter_token}", placeholder="הכל")
                else:
                    tbl_supps = []
            
            with filter_cols[3]:
                tbl_docket_filter = st.selectbox("מספר דוקט:", ["הכל", "עם דוקט", "ללא דוקט"], key=f"tbl_docket_filter_{filter_token}")
            
            with filter_cols[4]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔍 בצע סינון", key="apply_supplier_filters", type="primary"):
                    st.session_state['applied_supplier_filters'] = {
                        'sources': tbl_sources,
                        'event': tbl_event,
                        'supps': tbl_supps,
                        'docket': tbl_docket_filter
                    }
            
            with filter_cols[5]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ נקה", key="clear_all_filters"):
                    st.session_state['filter_token'] = filter_token + 1
                    st.session_state['applied_supplier_filters'] = None
            
            applied = st.session_state.get('applied_supplier_filters')
            summary_df = filtered_df.copy()
            
            if applied:
                if applied.get('sources') and SOURCE_COL:
                    edit_df = edit_df[edit_df[SOURCE_COL].isin(applied['sources'])]
                    summary_df = summary_df[summary_df[SOURCE_COL].isin(applied['sources'])]
                if applied.get('event') and applied['event'] != "הכל":
                    edit_df = edit_df[edit_df['event name'] == applied['event']]
                    summary_df = summary_df[summary_df['event name'] == applied['event']]
                if applied.get('supps'):
                    edit_df = edit_df[edit_df['Supplier NAME'].isin(applied['supps'])]
                    summary_df = summary_df[summary_df['Supplier NAME'].isin(applied['supps'])]
                if applied.get('docket') == "ללא דוקט" and DOCKET_COL:
                    edit_df = edit_df[(edit_df[DOCKET_COL].isna()) | (edit_df[DOCKET_COL].astype(str).str.strip().isin(['', '-']))]
                    summary_df = summary_df[(summary_df[DOCKET_COL].isna()) | (summary_df[DOCKET_COL].astype(str).str.strip().isin(['', '-']))]
                elif applied.get('docket') == "עם דוקט" and DOCKET_COL:
                    edit_df = edit_df[(edit_df[DOCKET_COL].notna()) & (~edit_df[DOCKET_COL].astype(str).str.strip().isin(['', '-']))]
                    summary_df = summary_df[(summary_df[DOCKET_COL].notna()) & (~summary_df[DOCKET_COL].astype(str).str.strip().isin(['', '-']))]
                
                st.markdown("---")
                st.markdown("### 📊 סיכום סינון")
                
                summary_cols = st.columns(4)
                with summary_cols[0]:
                    st.metric("📦 סה״כ הזמנות", len(summary_df))
                
                with summary_cols[1]:
                    if 'orderd' in summary_df.columns:
                        new_count = len(summary_df[summary_df['orderd'].astype(str).str.lower().str.strip().isin(['', 'new', 'חדש']) | summary_df['orderd'].isna()])
                        st.metric("🔴 חדש", new_count)
                
                with summary_cols[2]:
                    if 'orderd' in summary_df.columns:
                        ordered_count = len(summary_df[summary_df['orderd'].astype(str).str.lower().str.strip().isin(['orderd', 'ordered'])])
                        st.metric("🟡 הוזמן", ordered_count)
                
                with summary_cols[3]:
                    if 'orderd' in summary_df.columns:
                        done_count = len(summary_df[summary_df['orderd'].astype(str).str.lower().str.strip().str.contains('done', na=False)])
                        st.metric("🟢 נשלח", done_count)
                
                summary_cols2 = st.columns(4)
                with summary_cols2[0]:
                    if DOCKET_COL and DOCKET_COL in summary_df.columns:
                        with_dock = len(summary_df[(summary_df[DOCKET_COL].notna()) & (~summary_df[DOCKET_COL].astype(str).str.strip().isin(['', '-']))])
                        st.metric("✅ עם דוקט", with_dock)
                
                with summary_cols2[1]:
                    if DOCKET_COL and DOCKET_COL in summary_df.columns:
                        no_dock = len(summary_df) - with_dock
                        st.metric("❌ ללא דוקט", no_dock)
                
                with summary_cols2[2]:
                    if TOTAL_SOLD_COL and TOTAL_SOLD_COL in summary_df.columns:
                        try:
                            total_revenue = summary_df[TOTAL_SOLD_COL].apply(lambda x: float(str(x).replace('€', '').replace(',', '').strip()) if pd.notna(x) and str(x).strip() else 0).sum()
                            st.metric("💰 סה״כ הכנסות", f"€{total_revenue:,.2f}")
                        except:
                            st.metric("💰 סה״כ הכנסות", "-")
                
                with summary_cols2[3]:
                    if 'Qty' in summary_df.columns:
                        try:
                            total_qty = summary_df['Qty'].apply(lambda x: int(x) if pd.notna(x) and str(x).strip().isdigit() else 0).sum()
                            st.metric("🎫 סה״כ כרטיסים", total_qty)
                        except:
                            st.metric("🎫 סה״כ כרטיסים", "-")
            
            original_dockets = edit_df[DOCKET_COL].copy() if DOCKET_COL and DOCKET_COL in edit_df.columns else None
            original_rows = edit_df['row_index'].copy() if 'row_index' in edit_df.columns else None
            
            # Initialize selected rows in session state
            if 'selected_rows_batch' not in st.session_state:
                st.session_state.selected_rows_batch = set()
            
            # Add checkbox column for batch selection
            edit_df_with_selection = edit_df.copy()
            edit_df_with_selection['בחר'] = False
            
            # Restore previous selections
            if st.session_state.selected_rows_batch:
                for idx in st.session_state.selected_rows_batch:
                    if idx < len(edit_df_with_selection):
                        edit_df_with_selection.iloc[idx, edit_df_with_selection.columns.get_loc('בחר')] = True
            
            st.markdown(f"### 📝 לחץ על תא דוקט לעריכה ({len(edit_df)} שורות)")
            
            # Batch selection controls
            batch_cols = st.columns([1, 1, 1, 2, 1])
            with batch_cols[0]:
                if st.button("✅ בחר הכל", key="select_all_batch"):
                    st.session_state.selected_rows_batch = set(range(len(edit_df)))
                    st.rerun()
            with batch_cols[1]:
                if st.button("❌ בטל הכל", key="deselect_all_batch"):
                    st.session_state.selected_rows_batch = set()
                    st.rerun()
            with batch_cols[2]:
                selected_count = len(st.session_state.selected_rows_batch)
                st.info(f"📊 נבחרו: **{selected_count}** שורות")
            with batch_cols[3]:
                batch_docket = st.text_input(
                    "🔢 עדכן דוקט לכל הנבחרים:",
                    placeholder="הזן מספר דוקט לעדכון מרובה",
                    key="batch_docket_input"
                )
            with batch_cols[4]:
                if st.button("💾 עדכן נבחרים", key="update_batch_docket", type="primary", disabled=selected_count == 0 or not batch_docket):
                    if batch_docket and batch_docket.strip() and selected_count > 0:
                        with st.spinner(f"מעדכן {selected_count} שורות..."):
                            success_count = 0
                            errors = []
                            for idx in st.session_state.selected_rows_batch:
                                if idx < len(original_rows):
                                    row_idx = int(original_rows.iloc[idx]) if pd.notna(original_rows.iloc[idx]) else None
                                    if row_idx:
                                        success, msg = update_docket_number(row_idx, batch_docket.strip())
                                        if success:
                                            success_count += 1
                                        else:
                                            errors.append(f"שורה {row_idx}: {msg}")
                            
                            if success_count > 0:
                                load_data_from_sheet.clear()
                                st.session_state.selected_rows_batch = set()  # Clear selection after update
                                st.success(f"✅ עודכנו {success_count} שורות עם דוקט: {batch_docket}")
                                st.balloons()
                                if errors:
                                    for err in errors[:5]:  # Show first 5 errors
                                        st.warning(err)
                                st.rerun()
                            elif errors:
                                for err in errors:
                                    st.error(err)
                    elif not batch_docket or not batch_docket.strip():
                        st.warning("יש להזין מספר דוקט")
                    else:
                        st.warning("לא נבחרו שורות לעדכון")
            
            st.markdown("---")
            
            st.markdown(
                """
                <style>
                [data-testid="stDataEditor"] [role="gridcell"] {
                    justify-content: center !important;
                    align-items: center !important;
                    text-align: center !important;
                }
                [data-testid="stDataEditor"] [role="gridcell"] > div {
                    justify-content: center !important;
                    align-items: center !important;
                    text-align: center !important;
                    width: 100%;
                }
                [data-testid="stDataEditor"] [role="columnheader"] {
                    justify-content: center !important;
                    text-align: center !important;
                }
                [data-testid="stDataEditor"] [data-testid^="cell-orderd"] {
                    display: flex !important;
                    justify-content: center !important;
                    align-items: center !important;
                    direction: rtl !important;
                    unicode-bidi: bidi-override !important;
                }
                [data-testid="stDataEditor"] [data-testid^="cell-orderd"] > div:first-child {
                    display: flex !important;
                    justify-content: center !important;
                    align-items: center !important;
                    direction: rtl !important;
                    unicode-bidi: bidi-override !important;
                    width: 100%;
                }
                [data-testid="stDataEditor"] [data-testid="column-header-orderd"] {
                    justify-content: center !important;
                    text-align: center !important;
                    direction: rtl !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            
            column_config = {
                'בחר': st.column_config.CheckboxColumn('בחר', default=False),
                'row_index': st.column_config.NumberColumn('שורה', disabled=True),
                'order date': st.column_config.TextColumn('תאריך הזמנה', disabled=True),
                'orderd': st.column_config.TextColumn('סטטוס', disabled=True),
                'source': st.column_config.TextColumn('ספק/מקור', disabled=True),
                'Order number': st.column_config.TextColumn('מספר הזמנה', disabled=True),
                'docket number': st.column_config.TextColumn('מספר דוקט'),
                'event name': st.column_config.TextColumn('שם אירוע', disabled=True),
                'total sold': st.column_config.TextColumn('סה"כ מחיר', disabled=True),
                'SUPP PRICE': st.column_config.TextColumn('עלות ספק', disabled=True),
                'Supplier NAME': st.column_config.TextColumn('שם ספק', disabled=True),
                'SUPP order number': st.column_config.TextColumn('מספר הזמנה ספק', disabled=True),
            }
            
            # Reorder columns to put 'בחר' first
            cols_order = ['בחר'] + [col for col in edit_df_with_selection.columns if col != 'בחר']
            edit_df_with_selection = edit_df_with_selection[cols_order]
            
            # Store previous state to detect changes
            docket_editor_key = "docket_editor"
            if docket_editor_key not in st.session_state:
                st.session_state[docket_editor_key] = None
            
            edited_df = st.data_editor(
                edit_df_with_selection,
                column_config=column_config,
                use_container_width=True,
                height=450,
                num_rows="fixed",
                hide_index=True,
                key=docket_editor_key
            )
            
            # Only process if button clicked, not on every edit
            # The button click will trigger the save logic
            
            # Update selected rows based on checkbox column
            if 'בחר' in edited_df.columns:
                selected_indices = edited_df[edited_df['בחר'] == True].index.tolist()
                st.session_state.selected_rows_batch = set(selected_indices)
            
            # Remove 'בחר' column from edited_df for further processing
            edited_df = edited_df.drop(columns=['בחר'], errors='ignore')
            
            col_save, col_info = st.columns([1, 3])
            with col_save:
                if st.button("💾 שמור שינויים", key="save_docket_changes", type="primary"):
                    if original_dockets is not None and original_rows is not None and DOCKET_COL:
                        changes_made = 0
                        errors = []
                        
                        for i in range(len(edited_df)):
                            new_val = str(edited_df.iloc[i].get(DOCKET_COL, ''))
                            old_val = str(original_dockets.iloc[i]) if i < len(original_dockets) else ''
                            row_idx = int(original_rows.iloc[i]) if i < len(original_rows) else None
                            
                            if new_val != old_val and row_idx:
                                success, msg = update_docket_number(row_idx, new_val)
                                if success:
                                    changes_made += 1
                                else:
                                    errors.append(f"שורה {row_idx}: {msg}")
                        
                        if changes_made > 0:
                            load_data_from_sheet.clear()
                            st.success(f"✅ עודכנו {changes_made} שורות!")
                            st.balloons()
                            st.info("💡 לחץ על 'רענן' לצפייה בנתונים המעודכנים")
                        elif errors:
                            for err in errors:
                                st.error(err)
                        else:
                            st.info("לא זוהו שינויים")
            
            with col_info:
                if DOCKET_COL and DOCKET_COL in edited_df.columns:
                    empty_count = len(edited_df[
                        (edited_df[DOCKET_COL].isna()) | 
                        (edited_df[DOCKET_COL].astype(str).str.strip() == '') |
                        (edited_df[DOCKET_COL].astype(str).str.strip() == '-')
                    ])
                    if empty_count > 0:
                        st.warning(f"⚠️ {empty_count} ללא דוקט")
            
            st.markdown("---")
            
            # Use the final filtered edit_df for CSV export (not filtered_df)
            # Remove any temporary columns that might exist
            csv_df = edit_df.copy()
            csv_df = csv_df.drop(columns=['_date_parsed'], errors='ignore')
            csv_df = csv_df.drop(columns=['בחר'], errors='ignore')
            
            # If edit_df was filtered further, use it; otherwise use filtered_df
            csv = csv_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 הורד כ-CSV",
                data=csv,
                file_name=f"orders_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_csv",
                help=f"מוריד {len(csv_df)} שורות מסוננות (מתוך {len(df)} סה\"כ)"
            )
        else:
            st.error("לא נמצאו עמודות להצגה")

elif selected_tab == "➕ הוספה ידנית":
    st.subheader("➕ הוספה ידנית של הזמנה")
    st.markdown("הוסף הזמנה חדשה באופן ידני - לעסקאות מחוץ לפלטפורמות")
    
    st.markdown("---")
    
    # Wrap all input fields in a form to prevent rerun on input change
    with st.form(key="agents_manual_order_form", clear_on_submit=False):
        col_form1, col_form2 = st.columns(2)
        
        with col_form1:
            st.markdown("### 📋 פרטי הזמנה")
            
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            order_date = st.text_input(
                "📅 תאריך הזמנה:",
                value=current_datetime,
                disabled=True,
                key="manual_order_date"
            )
            
            status_options = ["new", "נשלח ולא שולם"]
            selected_status = st.selectbox(
                "📊 סטטוס:",
                status_options,
                index=0,
                key="manual_status"
            )
            
            existing_sources = get_unique_sources(df)
            source_mode = st.radio(
                "🏷️ מקור:",
                ["בחר מקור קיים", "הזנה ידנית"],
                horizontal=True,
                key="source_mode"
            )
            
            if source_mode == "בחר מקור קיים":
                source_option = st.selectbox(
                    "בחר מקור:",
                    ["-- בחר --"] + existing_sources,
                    key="manual_source_select"
                )
                final_source = "" if source_option == "-- בחר --" else source_option
            else:
                final_source = st.text_input(
                    "הזן מקור:",
                    placeholder="לדוגמה: WhatsApp, Telegram",
                    key="manual_new_source"
                )
            
            auto_order_num = generate_order_number(df)
            order_number = st.text_input(
                "🔢 מספר הזמנה:",
                value=auto_order_num,
                key="manual_order_number"
            )
            
            docket_number = st.text_input(
                "📄 מספר דוקט:",
                placeholder="הזן מספר דוקט",
                key="manual_docket"
            )
        
        with col_form2:
            st.markdown("### 🎫 פרטי אירוע")
            
            events_dict = get_unique_events(df)
            event_options = ["-- בחר אירוע קיים --"] + list(events_dict.keys()) + ["➕ הזן אירוע חדש"]
            selected_event = st.selectbox(
                "🎭 שם אירוע:",
                event_options,
                key="manual_event_select"
            )
            
            if selected_event == "➕ הזן אירוע חדש":
                event_name = st.text_input(
                    "הזן שם אירוע:",
                    placeholder="לדוגמה: Real Madrid vs Barcelona",
                    key="manual_new_event"
                )
                event_date = st.text_input(
                    "📅 תאריך אירוע:",
                    placeholder="DD/MM/YYYY",
                    key="manual_event_date"
                )
            elif selected_event == "-- בחר אירוע קיים --":
                event_name = ""
                event_date = ""
            else:
                event_name = selected_event
                event_date = events_dict.get(selected_event, "")
                st.info(f"📅 תאריך אירוע: {event_date}" if event_date else "📅 תאריך אירוע: לא נמצא")
            
            category_options = ["CAT 1", "CAT 2", "CAT 3", "CAT 4", "VIP", "PREMIUM", "LONGSIDE", "TIER 1", "TIER 2"]
            category_mode = st.radio(
                "🏟️ קטגוריה / סקציה:",
                ["בחר קטגוריה", "הזנה ידנית"],
                horizontal=True,
                key="category_mode"
            )
            
            if category_mode == "בחר קטגוריה":
                category = st.selectbox(
                    "בחר קטגוריה:",
                    ["-- בחר --"] + category_options,
                    key="manual_category_select"
                )
                if category == "-- בחר --":
                    category = ""
            else:
                category = st.text_input(
                    "הזן קטגוריה:",
                    placeholder="לדוגמה: CAT 1, VIP, LONGSIDE",
                    key="manual_category"
                )
            
            quantity = st.number_input(
                "🔢 כמות כרטיסים:",
                min_value=1,
                value=1,
                step=1,
                key="manual_quantity"
            )
        
        st.markdown("---")
        st.markdown("### 💰 פרטי מחיר")
        
        price_cols = st.columns([2, 1, 2])
        
        with price_cols[0]:
            price_per_ticket = st.number_input(
                "💶 מחיר לכרטיס:",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                key="manual_price"
            )
        
        with price_cols[1]:
            currency = st.selectbox(
                "מטבע:",
                ["€", "£", "$"],
                index=0,
                key="manual_currency"
            )
        
        with price_cols[2]:
            total = quantity * price_per_ticket
            st.markdown(f"### סה\"כ: {currency}{total:.2f}")
            st.caption(f"({quantity} × {currency}{price_per_ticket:.2f})")
        
        st.markdown("---")
        
        col_submit, col_clear = st.columns([1, 1])
        
        with col_submit:
            submitted = st.form_submit_button("✅ הוסף הזמנה", type="primary", use_container_width=True)
        
        with col_clear:
            clear_clicked = st.form_submit_button("🗑️ נקה טופס", use_container_width=True)
    
    # Handle form submission
    if submitted:
        if not event_name:
            st.error("❌ יש לבחור או להזין שם אירוע")
        elif not final_source:
            st.error("❌ יש לבחור או להזין מקור")
        elif price_per_ticket <= 0:
            st.error("❌ יש להזין מחיר לכרטיס")
        else:
            order_data = {
                'order date': current_datetime,
                'orderd': selected_status,
                'source': final_source,
                'Order number': order_number,
                'docket number': docket_number,
                'event name': event_name,
                'Date of the event': event_date,
                'Category / Section': category,
                'Qty': quantity,
                'Price sold': f"{currency}{price_per_ticket:.2f}",
                'TOTAL': f"{currency}{total:.2f}",
            }
            
            with st.spinner("מוסיף הזמנה לגוגל שיטס..."):
                success, message = add_new_order_to_sheet(order_data)
                
                if success:
                    load_data_from_sheet.clear()
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.markdown(f"""
                    **פרטי ההזמנה שנוספה:**
                    - מספר הזמנה: `{order_number}`
                    - אירוע: `{event_name}`
                    - כמות: `{quantity}`
                    - מחיר לכרטיס: `{currency}{price_per_ticket:.2f}`
                    - סה"כ (יחושב בשיטס): `{currency}{total:.2f}`
                    """)
                else:
                    st.error(f"❌ {message}")
    
    # Handle clear button
    if clear_clicked:
        st.rerun()
    
    st.markdown("---")
    st.info("""
    💡 **טיפים:**
    - מספר ההזמנה נוצר אוטומטית לפי ההזמנה האחרונה
    - תאריך ההזמנה מתמלא אוטומטית
    - בחר אירוע קיים כדי למשוך את תאריך האירוע אוטומטית
    - עמודת 'סה"כ מכירה' (N) תתעדכן אוטומטית לפי הנוסחה בשיטס
    """)

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; font-size: 0.8em;'>"
    "מערכת ניהול כרטיסים | מופעל ע\"י Streamlit & Google Sheets"
    "</div>",
    unsafe_allow_html=True
)
