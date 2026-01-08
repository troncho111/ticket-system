# מדריך הפעלת מתזמן מיילים אוטומטיים
## Email Scheduler Setup Guide

---

## 🔴 הבעיה

המיילים האוטומטיים לא נשלחים כי ה-`email_scheduler.py` צריך לרוץ כתהליך נפרד ברקע, והוא לא רץ אוטומטית.

---

## ✅ פתרונות

יש לך **3 אפשרויות** להפעיל את המתזמן:

### אפשרות 1: GitHub Actions (מומלץ - חינם ואוטומטי) ⭐

GitHub Actions יכול להריץ את המיילים אוטומטית לפי לוח זמנים.

#### איך להפעיל:

1. **הוסף Secrets ל-GitHub:**
   - לך ל-GitHub repository שלך
   - Settings → Secrets and variables → Actions
   - הוסף את ה-Secrets הבאים:
     - `GOOGLE_CREDENTIALS` - ה-JSON המלא
     - `RESEND_API_KEY` - מפתח API של Resend
     - `RESEND_FROM_EMAIL` - כתובת המייל

2. **ה-workflow כבר מוכן!**
   - הקובץ `.github/workflows/email-scheduler.yml` כבר קיים
   - הוא ירוץ אוטומטית לפי הלוח זמנים

3. **בדוק שהכל עובד:**
   - לך ל-Actions tab ב-GitHub
   - תראה את ה-workflow רץ
   - אם יש שגיאות, תראה אותן שם

#### יתרונות:
- ✅ חינם
- ✅ אוטומטי לחלוטין
- ✅ לא צריך שרת משלך
- ✅ עובד 24/7

---

### אפשרות 2: הרצה מקומית / VPS

אם יש לך שרת משלך או מחשב שפועל 24/7:

#### Windows:
```powershell
# פתח PowerShell או Command Prompt
cd C:\Users\User\Dropbox\PC\Desktop\ticket-system\ticket-system
python email_scheduler.py
```

#### Linux/Mac:
```bash
# הרץ בטרמינל
cd /path/to/ticket-system
python email_scheduler.py
```

#### עם systemd (Linux):
צור קובץ `/etc/systemd/system/email-scheduler.service`:
```ini
[Unit]
Description=Email Scheduler for Ticket System
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ticket-system
ExecStart=/usr/bin/python3 /path/to/ticket-system/email_scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

הפעל:
```bash
sudo systemctl start email-scheduler
sudo systemctl enable email-scheduler
```

---

### אפשרות 3: פלטפורמות אירוח (Streamlit Cloud, Heroku, Railway, Render)

#### Streamlit Cloud:
Streamlit Cloud **לא תומך** בהרצת תהליכים ברקע. צריך להשתמש ב-GitHub Actions (אפשרות 1).

#### Heroku:
1. צור `Procfile`:
```
web: streamlit run app.py --server.port=$PORT
worker: python email_scheduler.py
```

2. הפעל שני dynos:
   - Web dyno (לאפליקציה)
   - Worker dyno (למתזמן)

#### Railway:
1. צור שני services:
   - Web Service: `streamlit run app.py`
   - Background Worker: `python email_scheduler.py`

#### Render:
1. צור שני services:
   - Web Service: `streamlit run app.py`
   - Background Worker: `python email_scheduler.py`

---

## 📅 לוח זמנים

המיילים נשלחים אוטומטית ב:

| דוח | זמן | יום |
|-----|-----|-----|
| 🔴 הזמנות לא שולמו | 10:00 | כל יום |
| 💰 דוח מכירות יומי | 10:05 | כל יום |
| 📦 הזמנות חדשות | 20:00 | כל יום |
| 📊 דוח שבועי | 09:00 | יום ראשון |

**כל הזמנים לפי שעון ישראל!**

---

## 🧪 בדיקה

### לבדוק שהכל עובד:

1. **בדוק ידנית:**
   - לך לדף "מיילים אוטומטיים" ב-Streamlit
   - לחץ על כפתורי "שלח עכשיו"
   - אם זה עובד, המיילים האוטומטיים יעבדו גם

2. **בדוק GitHub Actions:**
   - לך ל-Actions tab ב-GitHub
   - תראה את ה-workflows רצים
   - בדוק את הלוגים

3. **בדוק מיילים:**
   - ודא שאתה מקבל מיילים בזמנים הנכונים
   - אם לא, בדוק את הלוגים

---

## 🔧 פתרון בעיות

### בעיה: GitHub Actions לא רץ
**פתרון:**
- ודא שה-Secrets מוגדרים נכון
- בדוק שה-workflow file קיים ב-`.github/workflows/`
- ודא שהקוד ב-main branch

### בעיה: מיילים לא נשלחים
**פתרון:**
- בדוק את `RESEND_API_KEY` ו-`RESEND_FROM_EMAIL`
- בדוק את הלוגים ב-GitHub Actions
- נסה לשלוח ידנית מהדף

### בעיה: זמנים לא נכונים
**פתרון:**
- GitHub Actions משתמש ב-UTC
- 10:00 ישראל = 08:00 UTC
- 20:00 ישראל = 18:00 UTC
- ה-workflow כבר מוגדר נכון!

---

## 📝 סיכום

**הפתרון המומלץ:** GitHub Actions (אפשרות 1)
- חינם
- אוטומטי
- לא צריך שרת משלך
- עובד 24/7

**מה לעשות:**
1. הוסף Secrets ל-GitHub
2. ה-workflow כבר מוכן וירוץ אוטומטית
3. בדוק ב-Actions tab שהכל עובד

---

**נוצר ב:** 2026-01-08  
**עודכן:** אחרי תיקון בעיית המתזמן
