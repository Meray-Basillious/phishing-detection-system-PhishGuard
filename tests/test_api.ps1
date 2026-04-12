# Test Email Phishing Detection API

$baseUrl = "http://localhost:5000"

Write-Host ("=" * 60)
Write-Host "Email Phishing Detection API - Test Suite"
Write-Host ("=" * 60)

# Test 1: Health Check
Write-Host "`n[TEST 1] Health Check"
Write-Host ("-" * 40)
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/health" -Method Get
    Write-Host "✓ Status: $($response.StatusCode)"
    Write-Host "Response: $($response.Content)"
}
catch {
    Write-Host "✗ Error: $_"
}

# Test 2: Analyze Phishing Email
Write-Host "`n[TEST 2] Analyze Phishing Email"
Write-Host ("-" * 40)
$phishingEmail = @{
    sender = "verify-account@secure-paypal.com"
    recipient = "john.doe@gmail.com"
    subject = "URGENT: Verify Your PayPal Account Immediately!"
    body = "Dear Customer, Your account has been suspended. Click here immediately to verify your identity and reactivate your account. Confirm your password and credit card information now."
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri "$baseUrl/api/emails/analyze" -Method Post -ContentType "application/json" -Body $phishingEmail -ErrorAction Stop
    Write-Host "✓ Status: $($response.StatusCode)"
    $content = $response.Content | ConvertFrom-Json
    Write-Host "Email ID: $($content.email_id)"
    Write-Host "Risk Score: $($content.analysis.overall_risk_score)"
    Write-Host "Is Phishing: $($content.analysis.is_phishing)"
    Write-Host "Threats Detected: $($content.analysis.threats -join ', ')"
    Write-Host "Full Response:`n$($response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 3)"
}
catch {
    Write-Host "✗ Error: $_"
}

# Test 3: Analyze Legitimate Email
Write-Host "`n[TEST 3] Analyze Legitimate Email"
Write-Host ("-" * 40)
$legitimateEmail = @{
    sender = "support@github.com"
    recipient = "user@example.com"
    subject = "Repository Update Notification"
    body = "Hello, This is a notification that your repository has been updated. You can view the changes at your dashboard."
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri "$baseUrl/api/emails/analyze" -Method Post -ContentType "application/json" -Body $legitimateEmail -ErrorAction Stop
    Write-Host "✓ Status: $($response.StatusCode)"
    $content = $response.Content | ConvertFrom-Json
    Write-Host "Risk Score: $($content.analysis.overall_risk_score)"
    Write-Host "Is Phishing: $($content.analysis.is_phishing)"
    Write-Host "Threats: $($content.analysis.threats -join ', ')"
}
catch {
    Write-Host "✗ Error: $_"
}

# Test 4: Get Email History
Write-Host "`n[TEST 4] Get Email History"
Write-Host ("-" * 40)
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/api/emails/history?limit=10" -Method Get
    Write-Host "✓ Status: $($response.StatusCode)"
    $content = $response.Content | ConvertFrom-Json
    Write-Host "Total Emails: $($content.total)"
    Write-Host "Emails Retrieved: $($content.emails.Count)"
    foreach ($email in $content.emails) {
        Write-Host "  - $($email.subject) | Risk: $($email.risk_score) | Phishing: $($email.is_phishing)"
    }
}
catch {
    Write-Host "✗ Error: $_"
}

# Test 5: Get Statistics
Write-Host "`n[TEST 5] Get Statistics"
Write-Host ("-" * 40)
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/api/emails/statistics" -Method Get
    Write-Host "✓ Status: $($response.StatusCode)"
    $content = $response.Content | ConvertFrom-Json
    Write-Host "Total Emails Analyzed: $($content.total_emails)"
    Write-Host "Phishing Detected: $($content.phishing_detected)"
    Write-Host "Safe Emails: $($content.safe_emails)"
    Write-Host "Average Risk Score: $($content.average_risk_score)"
    Write-Host "Phishing Percentage: $($content.phishing_percentage)%"
}
catch {
    Write-Host "✗ Error: $_"
}

Write-Host ("`n" + ("=" * 60))
Write-Host "Tests Complete!"
Write-Host ("=" * 60)
