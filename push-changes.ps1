# Script לשמירה ושידור שינויים ל-GitHub
# Usage: .\push-changes.ps1 "תיאור השינוי"

param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

Write-Host "🔄 מוסיף שינויים..." -ForegroundColor Cyan
git add .

Write-Host "💾 שומר שינויים..." -ForegroundColor Cyan
git commit -m $Message

Write-Host "📤 שולח ל-GitHub..." -ForegroundColor Cyan
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ הצליח! השינויים נשמרו ב-GitHub" -ForegroundColor Green
} else {
    Write-Host "❌ שגיאה! בדוק את ההודעות למעלה" -ForegroundColor Red
}
