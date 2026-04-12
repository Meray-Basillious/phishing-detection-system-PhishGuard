Write-Host "Testing Email Phishing Detection API" -ForegroundColor Green

Write-Host "`nTest 1: Health Check" -ForegroundColor Cyan
$health = Invoke-WebRequest -Uri "http://localhost:5000/health"
Write-Host $health.Content

Write-Host "`nTest 2: Analyze Phishing Email" -ForegroundColor Cyan
$phishing = @{
    sender = "verify-paypal@secure.com"
    recipient = "user@gmail.com"
    subject = "URGENT: Verify Your Account NOW"
    body = "Click here immediately to verify account. Account suspended due to unusual activity."
} | ConvertTo-Json

$result = Invoke-WebRequest -Uri "http://localhost:5000/api/emails/analyze" -Method Post -ContentType "application/json" -Body $phishing
$resultJson = $result.Content | ConvertFrom-Json
Write-Host "Risk Score: $($resultJson.analysis.overall_risk_score)"
Write-Host "Is Phishing: $($resultJson.analysis.is_phishing)"  
Write-Host "Threats: $($resultJson.analysis.threats)"

Write-Host "`nTest 3: Get Statistics" -ForegroundColor Cyan
$stats = Invoke-WebRequest -Uri "http://localhost:5000/api/emails/statistics"
$statsJson = $stats.Content | ConvertFrom-Json
Write-Host "Total Emails: $($statsJson.total_emails)"
Write-Host "Phishing Detected: $($statsJson.phishing_detected)"

Write-Host "`nDone!" -ForegroundColor Green
