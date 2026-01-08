@echo off
REM Script לשמירה ושידור שינויים ל-GitHub
REM Usage: push-changes.bat "תיאור השינוי"

if "%~1"=="" (
    echo ❌ שגיאה: צריך לספק תיאור לשינוי
    echo שימוש: push-changes.bat "תיאור השינוי"
    exit /b 1
)

echo 🔄 מוסיף שינויים...
git add .

echo 💾 שומר שינויים...
git commit -m "%~1"

echo 📤 שולח ל-GitHub...
git push origin main

if %ERRORLEVEL% EQU 0 (
    echo ✅ הצליח! השינויים נשמרו ב-GitHub
) else (
    echo ❌ שגיאה! בדוק את ההודעות למעלה
)
