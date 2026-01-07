# Migration Guide - Ticket Agency Management System
# מדריך מעבר - מערכת ניהול סוכנות כרטיסים

---

## 1. Project Overview / סקירת הפרויקט

### What Does This App Do? / מה האפליקציה עושה?

This is a **Ticket Agency Management System** for managing event ticket orders. It connects to a Google Sheet where all your orders are stored, and provides a beautiful dashboard to:

זוהי **מערכת ניהול סוכנות כרטיסים** לניהול הזמנות כרטיסים לאירועים. היא מתחברת לגיליון Google שבו מאוחסנות כל ההזמנות, ומספקת לוח בקרה יפה ל:

### Main Features / תכונות עיקריות

| Feature | Description | תיאור |
|---------|-------------|-------|
| **Order Management** | View, filter, and update ticket orders | צפייה, סינון ועדכון הזמנות כרטיסים |
| **Purchasing Center** | Mark orders as purchased with one click | סימון הזמנות כנרכשו בלחיצה אחת |
| **Profit Analytics** | See revenue, costs, and profit charts | צפייה בגרפי הכנסות, עלויות ורווח |
| **Operational View** | See events happening in the next 7 days | ראה אירועים שמתרחשים ב-7 הימים הקרובים |
| **Sales Tracking** | Daily, weekly, and monthly sales reports | דוחות מכירות יומיים, שבועיים וחודשיים |
| **Source Comparison** | Compare performance across sales channels | השוואת ביצועים בין ערוצי מכירה |
| **Automated Emails** | Daily and weekly reports sent automatically | דוחות יומיים ושבועיים נשלחים אוטומטית |

### Automated Email Reports / דוחות מייל אוטומטיים

The system sends 4 automatic email reports:

| Report | Time | What It Contains |
|--------|------|------------------|
| Unpaid Orders Reminder | 10:00 AM daily | Orders that were sent but not paid |
| Daily Sales Report | 10:05 AM daily | Summary of today's sales |
| New Orders Report | 8:00 PM daily | Orders waiting to be processed |
| Weekly Summary | Sunday 9:00 AM | Full week performance overview |

---

## 2. Technical Stack / סטאק טכנולוגי

### Frontend (What Users See) / צד לקוח

- **Framework:** Streamlit (Python)
- **What it is:** Streamlit is a tool that turns Python code into a web application
- **Design:** Dark theme with Hebrew (RTL) support, mobile-friendly

### Backend (Server Logic) / צד שרת

- **Language:** Python 3.11+
- **What it does:** Handles all the data processing, calculations, and email sending
- **Scheduler:** APScheduler runs in the background to send emails at scheduled times

### Database (Data Storage) / מסד נתונים

- **Type:** Google Sheets (not a traditional database)
- **Sheet Name:** `מערכת הזמנות - קוד יהודה  ` (with 2 trailing spaces)
- **Access Method:** Google Service Account with API access

### External Services / שירותים חיצוניים

| Service | What It Does | How to Get It |
|---------|--------------|---------------|
| **Google Sheets API** | Reads and writes order data | Google Cloud Console |
| **Google Drive API** | Allows access to the spreadsheet | Google Cloud Console |
| **Resend** | Sends email reports | resend.com |
| **Exchange Rate API** | Currency conversion (optional) | exchangerate-api.com |

---

## 3. File Structure Explanation / הסבר מבנה הקבצים

### Main Files / קבצים ראשיים

```
project/
│
├── app.py                    [MOST IMPORTANT - Main Application]
│   The main application file. Contains all the dashboard code,
│   tabs, charts, and user interface. This is the heart of the system.
│   הקובץ הראשי. מכיל את כל קוד הלוח בקרה, לשוניות, גרפים וממשק משתמש.
│
├── email_scheduler.py        [Email Timer]
│   Runs in the background and triggers email reports at specific times.
│   This file runs continuously and doesn't stop.
│   רץ ברקע ומפעיל דוחות מייל בזמנים קבועים.
│
├── daily_reminder.py         [Unpaid Orders Email]
│   Sends reminder for orders with "sent - not paid" status.
│   Runs at 10:00 AM Israel time.
│   שולח תזכורת להזמנות בסטטוס "נשלח ולא שולם".
│
├── daily_sales_report.py     [Sales Email]
│   Sends summary of today's sales.
│   Runs at 10:05 AM Israel time.
│   שולח סיכום מכירות היום.
│
├── daily_new_orders_report.py [New Orders Email]
│   Sends list of orders with "new" status.
│   Runs at 8:00 PM Israel time.
│   שולח רשימת הזמנות בסטטוס "new".
│
├── weekly_sales_report.py    [Weekly Email]
│   Sends weekly performance summary.
│   Runs every Sunday at 9:00 AM Israel time.
│   שולח סיכום ביצועים שבועי.
│
├── pyproject.toml            [Dependencies List]
│   Lists all the Python packages needed to run the app.
│   רשימת כל חבילות Python הנדרשות להרצת האפליקציה.
│
├── main.py                   [Alternative Entry Point]
│   Simple file that can start the app.
│   קובץ פשוט שיכול להפעיל את האפליקציה.
│
├── pages/
│   └── agents.py             [Additional Pages]
│       Extra pages for the Streamlit app.
│       דפים נוספים לאפליקציה.
│
└── .streamlit/
    └── config.toml           [App Settings]
        Configuration for how Streamlit runs.
        הגדרות לאופן הרצת Streamlit.
```

### Most Important Files / הקבצים החשובים ביותר

1. **app.py** - If something is wrong with the dashboard, look here
2. **email_scheduler.py** - If emails aren't sending, check this file
3. **daily_reminder.py** - The unpaid orders reminder logic

---

## 4. Database Setup / הגדרת מסד נתונים

### Google Sheet Structure / מבנה גיליון Google

Your Google Sheet needs these columns (in this exact order):

| Column | Name | Description | דוגמה |
|--------|------|-------------|-------|
| A | order date | When order was created | 01/07/2026 10:30 |
| B | event name | Name of the event | Real Madrid vs Barcelona |
| C | Date of the event | When event happens | 15/01/2026 21:00 |
| D | Category / Section | Ticket category | CAT 1, VIP, LONGSIDE |
| E | Seating Arrangements | Seat details | Row 5, Seats 10-12 |
| F | Order number | Unique order ID | 631428051 |
| G | SUPP order number | Supplier's order number | FXWZF3NN687V |
| H | docket number | Docket reference | 12345 |
| I | Status | General status | Confirmed |
| J | orderd | Workflow status | new, orderd, sent_not_paid, Done! |
| K | TOTAL | Sale price (with currency) | €625.00 |
| L | SUPP PRICE | Cost/supplier price | €450.00 |
| M | source | Where sale came from | Goldenseat, Viagogo |
| N | Supplier NAME | Supplier name | TicketOne |
| O | Qty | Number of tickets | 2 |
| P | Price sold | Price per ticket | €312.50 |

### Order Status Values / ערכי סטטוס הזמנה

The `orderd` column uses these values:

| Status | Meaning | Hebrew |
|--------|---------|--------|
| `new` | New order, needs processing | הזמנה חדשה |
| `orderd` | Tickets purchased from supplier | נרכש מספק |
| `sent_not_paid` | Tickets sent, payment pending | נשלח, לא שולם |
| `Done!` | Completed and paid | הושלם ושולם |

### Creating the Google Sheet / יצירת גיליון Google

1. Create a new Google Sheet
2. Name it: `מערכת הזמנות - קוד יהודה  ` (include 2 spaces at the end!)
3. Create the columns listed above in the first row
4. Share the sheet with your Service Account email

---

## 5. Environment Variables / משתני סביבה

### Required Variables / משתנים נדרשים

Create a file called `.env` with these values:

```env
# Google Credentials (JSON format, all in one line)
GOOGLE_CREDENTIALS={"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"your-service@project.iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}

# Security (generate a random string, at least 32 characters)
SESSION_SECRET=your-random-secret-string-at-least-32-characters-long

# Email Service (from resend.com)
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxx
RESEND_FROM_EMAIL=noreply@yourdomain.com
```

### How to Get Each Value / איך להשיג כל ערך

#### GOOGLE_CREDENTIALS
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable "Google Sheets API" and "Google Drive API"
4. Go to "Credentials" > "Create Credentials" > "Service Account"
5. Download the JSON key file
6. Copy the entire JSON content (remove line breaks to make it one line)

#### SESSION_SECRET
- Generate a random string (32+ characters)
- Use a password generator or type random characters
- Example: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

#### RESEND_API_KEY & RESEND_FROM_EMAIL
1. Sign up at [resend.com](https://resend.com)
2. Go to API Keys and create a new key
3. Add and verify your domain
4. Use your verified domain email address

---

## 6. Deployment Checklist / רשימת פריסה

### Before You Start / לפני שמתחילים

- [ ] Have access to your Google Sheet with all order data
- [ ] Have a Google Cloud account with billing enabled
- [ ] Have a Resend account with verified domain
- [ ] Have a hosting platform account (Heroku, Railway, Render, etc.)

### Step-by-Step Deployment / פריסה צעד אחר צעד

#### Step 1: Prepare the Code / הכנת הקוד

- [ ] Download all project files
- [ ] **IMPORTANT:** Update `get_resend_credentials()` function in ALL email files:

```python
# REPLACE the existing function with this:
def get_resend_credentials():
    api_key = os.environ.get('RESEND_API_KEY')
    from_email = os.environ.get('RESEND_FROM_EMAIL')
    return api_key, from_email
```

Files to update:
- [ ] app.py
- [ ] daily_reminder.py
- [ ] daily_sales_report.py
- [ ] daily_new_orders_report.py
- [ ] weekly_sales_report.py

#### Step 2: Update App URL / עדכון כתובת האפליקציה

In `daily_reminder.py`, update the URL:
```python
def get_app_base_url():
    return "https://your-new-domain.com"  # <-- Change this!
```

#### Step 3: Set Up Google Access / הגדרת גישה לגוגל

- [ ] Create Google Cloud project
- [ ] Enable Google Sheets API
- [ ] Enable Google Drive API
- [ ] Create Service Account
- [ ] Download JSON credentials
- [ ] Share your Google Sheet with the service account email

#### Step 4: Set Up Email Service / הגדרת שירות מייל

- [ ] Create Resend account
- [ ] Verify your domain
- [ ] Create API key
- [ ] Note the verified email address

#### Step 5: Deploy to Platform / פריסה לפלטפורמה

For **Heroku**:
```bash
# Create Procfile with:
web: streamlit run app.py --server.port=$PORT
worker: python email_scheduler.py
```

For **Railway/Render**:
- Connect your GitHub repository
- Set environment variables in dashboard
- Deploy main branch

#### Step 6: Set Environment Variables / הגדרת משתני סביבה

Add these in your hosting platform's dashboard:
- [ ] `GOOGLE_CREDENTIALS`
- [ ] `SESSION_SECRET`
- [ ] `RESEND_API_KEY`
- [ ] `RESEND_FROM_EMAIL`

#### Step 7: Start Both Processes / הפעלת שני התהליכים

You need to run TWO things:
1. **Main App:** `streamlit run app.py --server.port 5000`
2. **Email Scheduler:** `python email_scheduler.py` (runs continuously)

### Testing Checklist / רשימת בדיקות

- [ ] App loads without errors
- [ ] Can see orders from Google Sheet
- [ ] Filters work (by date, source, event)
- [ ] Can change order status
- [ ] Profit calculations are correct
- [ ] Charts display properly
- [ ] Test email sending (use manual send button)
- [ ] "Mark as Paid" button in email works

### Common Issues / בעיות נפוצות

| Problem | Solution |
|---------|----------|
| "Not Found" error when clicking email button | Republish the app and update the URL in `daily_reminder.py` |
| Google Sheet not loading | Check if service account email has access to the sheet |
| Emails not sending | Verify Resend API key and domain are correct |
| Scheduler not running | Make sure `email_scheduler.py` is running as a separate process |
| Wrong timezone | App uses Israel timezone (Asia/Jerusalem) |
| Sheet name error | Make sure the sheet name has exactly 2 trailing spaces |

### Platform-Specific Notes / הערות לפי פלטפורמה

**Heroku:**
- Use two dynos (web + worker) or use Heroku Scheduler for emails
- Free tier may sleep after 30 minutes of inactivity

**Railway:**
- Supports multiple services easily
- Set up two services from same repo

**Render:**
- Use "Web Service" for app and "Background Worker" for scheduler
- Free tier has limitations

**VPS (DigitalOcean, etc.):**
- Use systemd to manage both processes
- Consider using supervisor or pm2

---

## Quick Reference / התייחסות מהירה

### Commands to Run / פקודות להרצה

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main app
streamlit run app.py --server.port 5000

# Run email scheduler (in separate terminal)
python email_scheduler.py

# Test email manually
python daily_reminder.py
```

### Important URLs / כתובות חשובות

- Google Cloud Console: https://console.cloud.google.com
- Resend Dashboard: https://resend.com/dashboard
- Your Google Sheet: [Add your sheet URL here]

### Support Emails in the App / כתובות מייל במערכת

Update these in the code if needed:
- `operations@tiktik.co.il` - Receives unpaid order reminders
- `info@tiktik.co.il` - Receives sales reports

---

*This guide was created for migrating the Ticket Agency Management System to a new platform.*

*מדריך זה נוצר לצורך העברת מערכת ניהול סוכנות הכרטיסים לפלטפורמה חדשה.*
