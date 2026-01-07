# Ticket Agency Management System - Export Documentation
# מערכת ניהול סוכנות כרטיסים - תיעוד לייצוא

---

## English Documentation

### Project Overview

**Name:** Ticket Agency Management System (מערכת הזמנות - קוד יהודה)  
**Type:** Web Application  
**Framework:** Python Streamlit  
**Purpose:** Manage ticket orders, track purchasing status, monitor profitability, and send automated email reports

### Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend | Python | 3.11+ |
| Web Framework | Streamlit | 1.52+ |
| Database | Google Sheets (via gspread) | - |
| Email Service | Resend | 2.19+ |
| Scheduler | APScheduler | 3.11+ |
| Data Processing | Pandas | 2.3+ |
| Charts | Plotly | 6.5+ |
| Authentication | Google Service Account | - |

### Project Structure

```
project/
├── app.py                      # Main Streamlit application (6185 lines)
├── email_scheduler.py          # Background email scheduler
├── daily_reminder.py           # Unpaid orders reminder (10:00 AM)
├── daily_sales_report.py       # Daily sales report (10:05 AM)
├── daily_new_orders_report.py  # New orders report (20:00)
├── weekly_sales_report.py      # Weekly sales summary (Sunday 09:00)
├── pyproject.toml              # Python dependencies
├── main.py                     # Alternative entry point
├── pages/
│   └── agents.py               # Additional pages
└── .streamlit/
    └── config.toml             # Streamlit configuration
```

### Dependencies (requirements.txt equivalent)

Create a `requirements.txt` file with:

```
apscheduler>=3.11.2
gspread>=6.2.1
oauth2client>=4.1.3
pandas>=2.3.3
plotly>=6.5.0
pytz>=2025.2
requests>=2.32.5
resend>=2.19.0
streamlit>=1.52.2
streamlit-autorefresh>=1.0.1
```

### Environment Variables Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_CREDENTIALS` | Google Service Account JSON credentials | `{"type": "service_account", "project_id": "...", ...}` |
| `SESSION_SECRET` | Secret key for email link verification | Random string (32+ chars) |
| `RESEND_API_KEY` | Resend email service API key | `re_xxx...` |
| `RESEND_FROM_EMAIL` | Sender email address | `noreply@yourdomain.com` |

### Google Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Google Sheets API and Google Drive API
4. Create Service Account credentials
5. Download JSON key file
6. Share your Google Sheet with the service account email

### Google Sheet Requirements

**Sheet Name:** `מערכת הזמנות - קוד יהודה  ` (with trailing spaces)

**Required Columns:**
- `order date` - Order creation date
- `event name` - Event name
- `Date of the event` - Event date
- `Category / Section` - Ticket category
- `Seating Arrangements` - Seat details
- `Order number` - Unique order ID
- `SUPP order number` - Supplier order number
- `docket number` - Docket reference
- `Status` - Order status
- `orderd` - Order workflow status (new, orderd, sent_not_paid, Done!)
- `TOTAL` - Total sale amount
- `SUPP PRICE` - Supplier/cost price
- `source` - Sales source
- `Supplier NAME` - Supplier name
- `Qty` - Ticket quantity
- `Price sold` - Price per ticket

### Running the Application

**Development:**
```bash
pip install -r requirements.txt
streamlit run app.py --server.port 5000
```

**Email Scheduler (separate process):**
```bash
python email_scheduler.py
```

### Replit-Specific Code Changes Required

The following code uses Replit's internal connector API and needs modification:

#### 1. `get_resend_credentials()` function

**Current (Replit):**
```python
def get_resend_credentials():
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    x_replit_token = 'repl ' + os.environ.get('REPL_IDENTITY')
    response = requests.get(
        f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=resend',
        headers={'X_REPLIT_TOKEN': x_replit_token}
    )
    # ... parse response
```

**Replace with (Standard):**
```python
def get_resend_credentials():
    api_key = os.environ.get('RESEND_API_KEY')
    from_email = os.environ.get('RESEND_FROM_EMAIL')
    return api_key, from_email
```

This change is needed in:
- `app.py`
- `daily_reminder.py`
- `daily_sales_report.py`
- `daily_new_orders_report.py`
- `weekly_sales_report.py`

#### 2. Published App URL

In `daily_reminder.py`, update:
```python
def get_app_base_url():
    return "https://your-new-domain.com"  # Update to your new hosting URL
```

### Email Schedule Configuration

| Report | Time (Israel) | Description |
|--------|---------------|-------------|
| Unpaid Orders Reminder | 10:00 AM daily | Orders with status "sent - not paid" |
| Daily Sales Report | 10:05 AM daily | Today's sales summary |
| New Orders Report | 20:00 daily | Orders with status "new" |
| Weekly Sales Summary | Sunday 09:00 | Weekly performance overview |

### Application Tabs

1. **מרכז קניות (Purchasing Center)** - Mark orders as purchased
2. **אנליטיקות רווח (Profit Analytics)** - Revenue and profit charts
3. **תצוגה תפעולית (Operational View)** - 7-day event lookahead
4. **הזמנות חדשות (New Orders)** - Process new orders
5. **מכירות (Sales)** - Daily/weekly/monthly sales tracking
6. **השוואת מקורות (Source Comparison)** - Revenue by sales source
7. **מיילים אוטומטיים (Auto Emails)** - Email scheduler management

### Deployment Options

1. **Heroku**: Use `Procfile` with `web: streamlit run app.py --server.port=$PORT`
2. **Railway**: Direct Python buildpack support
3. **Render**: Use `render.yaml` configuration
4. **AWS/GCP**: Use Docker containerization
5. **VPS**: Use systemd service for background scheduler

---

## תיעוד בעברית

### סקירת הפרויקט

**שם:** מערכת ניהול סוכנות כרטיסים (קוד יהודה)  
**סוג:** אפליקציית ווב  
**מסגרת:** Python Streamlit  
**מטרה:** ניהול הזמנות כרטיסים, מעקב סטטוס רכישה, ניטור רווחיות ושליחת דוחות מייל אוטומטיים

### סטאק טכנולוגי

| רכיב | טכנולוגיה | גרסה |
|------|-----------|-------|
| צד שרת | Python | 3.11+ |
| מסגרת ווב | Streamlit | 1.52+ |
| מסד נתונים | Google Sheets (דרך gspread) | - |
| שירות מיילים | Resend | 2.19+ |
| מתזמן | APScheduler | 3.11+ |
| עיבוד נתונים | Pandas | 2.3+ |
| גרפים | Plotly | 6.5+ |
| אימות | Google Service Account | - |

### מבנה הפרויקט

```
project/
├── app.py                      # אפליקציית Streamlit ראשית (6185 שורות)
├── email_scheduler.py          # מתזמן מיילים ברקע
├── daily_reminder.py           # תזכורת הזמנות לא שולמו (10:00)
├── daily_sales_report.py       # דוח מכירות יומי (10:05)
├── daily_new_orders_report.py  # דוח הזמנות חדשות (20:00)
├── weekly_sales_report.py      # סיכום מכירות שבועי (יום ראשון 09:00)
├── pyproject.toml              # תלויות Python
├── main.py                     # נקודת כניסה חלופית
├── pages/
│   └── agents.py               # דפים נוספים
└── .streamlit/
    └── config.toml             # הגדרות Streamlit
```

### משתני סביבה נדרשים

| משתנה | תיאור | דוגמה |
|-------|-------|-------|
| `GOOGLE_CREDENTIALS` | פרטי חשבון שירות Google בפורמט JSON | `{"type": "service_account", ...}` |
| `SESSION_SECRET` | מפתח סודי לאימות קישורי מייל | מחרוזת אקראית (32+ תווים) |
| `RESEND_API_KEY` | מפתח API של שירות Resend | `re_xxx...` |
| `RESEND_FROM_EMAIL` | כתובת מייל שולח | `noreply@yourdomain.com` |

### הגדרת חשבון שירות Google

1. היכנס ל-[Google Cloud Console](https://console.cloud.google.com)
2. צור פרויקט חדש או בחר קיים
3. הפעל את Google Sheets API ו-Google Drive API
4. צור פרטי חשבון שירות (Service Account)
5. הורד קובץ מפתח JSON
6. שתף את הגיליון עם כתובת המייל של חשבון השירות

### עמודות נדרשות בגיליון

- `order date` - תאריך יצירת ההזמנה
- `event name` - שם האירוע
- `Date of the event` - תאריך האירוע
- `Category / Section` - קטגוריית כרטיס
- `Seating Arrangements` - פרטי מושב
- `Order number` - מספר הזמנה ייחודי
- `SUPP order number` - מספר הזמנת ספק
- `docket number` - מספר דוקט
- `Status` - סטטוס הזמנה
- `orderd` - סטטוס תהליך (new, orderd, sent_not_paid, Done!)
- `TOTAL` - סכום מכירה כולל
- `SUPP PRICE` - מחיר ספק/עלות
- `source` - מקור מכירה
- `Supplier NAME` - שם ספק
- `Qty` - כמות כרטיסים
- `Price sold` - מחיר לכרטיס

### הרצת האפליקציה

**פיתוח:**
```bash
pip install -r requirements.txt
streamlit run app.py --server.port 5000
```

**מתזמן מיילים (תהליך נפרד):**
```bash
python email_scheduler.py
```

### שינויים נדרשים בקוד (ספציפי ל-Replit)

הפונקציה `get_resend_credentials()` משתמשת ב-API פנימי של Replit וצריך לשנות אותה:

**החלף ב:**
```python
def get_resend_credentials():
    api_key = os.environ.get('RESEND_API_KEY')
    from_email = os.environ.get('RESEND_FROM_EMAIL')
    return api_key, from_email
```

שינוי זה נדרש בקבצים:
- `app.py`
- `daily_reminder.py`
- `daily_sales_report.py`
- `daily_new_orders_report.py`
- `weekly_sales_report.py`

### לוח זמנים דוחות מייל

| דוח | שעה (ישראל) | תיאור |
|-----|-------------|-------|
| תזכורת לא שולם | 10:00 יומי | הזמנות בסטטוס "נשלח ולא שולם" |
| דוח מכירות יומי | 10:05 יומי | סיכום מכירות היום |
| דוח הזמנות חדשות | 20:00 יומי | הזמנות בסטטוס "new" |
| סיכום שבועי | יום ראשון 09:00 | סקירת ביצועים שבועית |

### לשוניות האפליקציה

1. **מרכז קניות** - סימון הזמנות כנרכשו
2. **אנליטיקות רווח** - גרפי הכנסות ורווח
3. **תצוגה תפעולית** - מבט 7 ימים קדימה
4. **הזמנות חדשות** - עיבוד הזמנות חדשות
5. **מכירות** - מעקב מכירות יומי/שבועי/חודשי
6. **השוואת מקורות** - הכנסות לפי מקור מכירה
7. **מיילים אוטומטיים** - ניהול מתזמן מיילים

### אפשרויות פריסה

1. **Heroku**: השתמש ב-`Procfile` עם `web: streamlit run app.py --server.port=$PORT`
2. **Railway**: תמיכה ישירה ב-Python buildpack
3. **Render**: הגדרת `render.yaml`
4. **AWS/GCP**: שימוש ב-Docker
5. **VPS**: שימוש ב-systemd service למתזמן ברקע

---

## Contact / יצירת קשר

For questions about this project, please contact the original developer.

לשאלות על הפרויקט, אנא פנו למפתח המקורי.
