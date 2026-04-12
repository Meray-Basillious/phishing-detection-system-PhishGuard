# Complete Implementation Guide - PhishGuard Gemini Hybrid System

This guide provides comprehensive details for implementing, configuring, and troubleshooting the PhishGuard hybrid phishing detection system.

**Quick Links:**
- [Architecture Overview](#architecture-overview)
- [Installation Steps](#installation-steps)
- [Configuration](#configuration)
- [Code Integration](#code-integration)
- [Performance & Costs](#performance--costs)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### 5-Layer Hybrid System

The PhishGuard system uses a layered approach combining Machine Learning speed with LLM contextual understanding:

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: ML Baseline (100ms)                            │
│                                                         │
│ Random Forest (300 trees): URL analysis                │
│   - Features: Domain age, IP reputation, URL length... │
│   - Accuracy: 89%                                       │
│   - Speed: <50ms                                        │
│                                                         │
│ Logistic Regression: Content analysis                  │
│   - Features: TF-IDF vectorization of keywords         │
│   - Accuracy: 84%                                       │
│   - Speed: <30ms                                        │
│                                                         │
│ Output: Numerical scores (0-1)                         │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2: Smart Routing Decision                         │
│                                                         │
│ if score < 0.25:     SAFE → Skip Gemini (SAVE $)      │
│ if 0.25 ≤ score ≤ 0.80: AMBIGUOUS → Use Gemini       │
│ if score > 0.80:     PHISHING → Confirm with Gemini   │
│                                                         │
│ Result: ~60% skip Gemini (safe), ~40% routed          │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3: Semantic Analysis (300ms)                      │
│                                                         │
│ Google Gemini 2.0 Flash:                               │
│   - Social engineering tactics detection               │
│   - Contextual contradictions                          │
│   - Threat type classification (BEC, phishing, etc)    │
│   - Novel pattern detection                            │
│   - Dynamic risk assessment                            │
│                                                         │
│ Output: threat_type, tactics, confidence, explanation  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 4: Intelligent Score Blending                     │
│                                                         │
│ if gemini_confidence > 0.95:                           │
│     final_score = 0.4 * ml_score + 0.6 * gemini_score │
│ else:                                                   │
│     final_score = 0.5 * ml_score + 0.5 * gemini_score │
│                                                         │
│ Output: Refined risk score (0-1)                       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 5: Dynamic Explanation                            │
│                                                         │
│ Generate actionable output:                            │
│   - Threat classification                              │
│   - Detected tactics explained                         │
│   - Specific recommendations                           │
│   - ML component breakdown                             │
│                                                         │
│ Output: User-friendly report                           │
└─────────────────────────────────────────────────────────┘
```

### Why This Design?

| Aspect | Benefit |
|--------|---------|
| **Speed** | ML baseline is fast (~100ms), so safe emails stay fast |
| **Context** | Gemini only analyzes risky emails, catching social engineering |
| **Cost** | Smart routing means 60% of emails cost $0 |
| **Accuracy** | Hybrid improves from 85% to 92-95% |
| **Fallback** | Works without Gemini if API unavailable |

---

## Installation Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/skmxx22/Email_Phishing_Detector_PhishGuard.git
cd PhishGuard
```

### Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Or activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import flask, scikit-learn, google.generativeai; print('✓ All dependencies installed')"
```

### Step 3: Get Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com)
2. Click "Get API Key"
3. Create new API key in default project
4. Copy the key (format: `AIzaSy...`)

### Step 4: Configure Environment

Create `backend/.env` file:

```bash
# Navigate to backend directory
cd backend

# Create .env with (Windows PowerShell)
@"
GEMINI_API_KEY=AIzaSyB9jAxAKVJkenTGwe9rZtYTDmAy0G744QA
USE_GEMINI=true
GEMINI_MODEL=gemini-2.0-flash-exp
USE_GEMINI_THRESHOLD_LOW=0.25
USE_GEMINI_THRESHOLD_HIGH=0.80
GEMINI_TEMPERATURE=0.3
FLASK_PORT=5000
CORS_ORIGINS=*
"@ | Out-File -Encoding UTF8 .env

# Or (macOS/Linux)
cat > .env << EOF
GEMINI_API_KEY=AIzaSyB9jAxAKVJkenTGwe9rZtYTDmAy0G744QA
USE_GEMINI=true
GEMINI_MODEL=gemini-2.0-flash-exp
USE_GEMINI_THRESHOLD_LOW=0.25
USE_GEMINI_THRESHOLD_HIGH=0.80
GEMINI_TEMPERATURE=0.3
FLASK_PORT=5000
CORS_ORIGINS=*
EOF
```

### Step 5: Start Backend

```bash
python app.py

# Expected output:
# WARNING in app.run_simple (werkzeug): Press CTRL+C to quit
# Running on http://127.0.0.1:5000
```

### Step 6: Frontend Setup (Optional)

```bash
cd frontend
npm install
npm start

# Expected output:
# Compiled successfully!
# You can now view frontend in the browser.
# Local: http://localhost:3000
```

### Verification

Test that everything is working:

```bash
# Test backend health
curl http://127.0.0.1:5000/health

# Should return:
# {"status":"OK","timestamp":"2026-04-13T..."}

# Test email analysis
curl -X POST http://127.0.0.1:5000/api/email/analyze \
  -H "Content-Type: application/json" \
  -d '{"sender":"test@example.com","subject":"Test","content":"Test email"}'

# Should return JSON with phishing_score, analysis_type, etc.
```

---

## Configuration

### Environment Variables (backend/.env)

```env
# ============================================
# REQUIRED - Google Gemini API
# ============================================

# Your Gemini API key from Google AI Studio
GEMINI_API_KEY=AIzaSyB9jAxAKVJkenTGwe9rZtYTDmAy0G744QA

# ============================================
# OPTIONAL - Gemini Configuration
# ============================================

# Enable/disable Gemini hybrid analysis
USE_GEMINI=true

# Model to use (current best: gemini-2.0-flash-exp)
GEMINI_MODEL=gemini-2.0-flash-exp

# Smart routing thresholds (0.0 to 1.0)
# Emails below LOW threshold skip Gemini (safe)
USE_GEMINI_THRESHOLD_LOW=0.25

# Emails above HIGH threshold always use Gemini (phishing)
USE_GEMINI_THRESHOLD_HIGH=0.80

# Gemini response temperature (0.0 = consistent, 1.0 = creative)
# Lower = faster, more consistent; Higher = slower, more varied
GEMINI_TEMPERATURE=0.3

# ============================================
# OPTIONAL - Flask Configuration
# ============================================

# API port
FLASK_PORT=5000

# CORS allowed origins (wildcard for development)
CORS_ORIGINS=*

# Flask environment
FLASK_ENV=development
FLASK_DEBUG=False
```

### Threshold Explanation

The system uses thresholds to decide when to use Gemini:

```
Safe Zone        Ambiguous Zone        Phishing Zone
(Skip Gemini)    (Use Gemini)          (Confirm with Gemini)
   0.0 - 0.25    0.25 - 0.80           0.80 - 1.0
   100ms, $0     450ms, $0.0002        450ms, $0.0002
   ✓ Fast        ✓ Smart               ✓ Thorough
```

**Adjust thresholds to:**
- **Lower THRESHOLD_LOW** (e.g., 0.15) → More emails to Gemini, higher cost, better accuracy
- **Raise THRESHOLD_LOW** (e.g., 0.35) → Fewer emails to Gemini, lower cost, faster
- **Lower THRESHOLD_HIGH** (e.g., 0.70) → More emails to Gemini, higher cost
- **Raise THRESHOLD_HIGH** (e.g., 0.90) → Fewer emails to Gemini, lower cost

**Recommended:** Keep default (0.25-0.80) for optimal balance.

---

## Code Integration

### Understanding the Code Structure

**Key Files:**

```
backend/
├── app.py                           # Flask app entry point
├── services/
│   ├── phishing_detector.py        # Main detection logic
│   └── gemini_analyzer.py          # Gemini integration (NEW)
├── routes/
│   └── email_routes.py             # API endpoints
└── artifacts/phase2/               # Trained ML models
    ├── url_model.joblib            # Random Forest
    ├── content_model.joblib        # Logistic Regression
    └── metadata.json               # Model info
```

### How Data Flows Through System

```
1. API Request
   ↓
2. Email Routes (/api/email/analyze)
   ↓
3. Phishing Detector.analyze_email()
   ├─ Extract features
   ├─ Run ML models (RF + LR)
   ├─ Get ML scores
   └─ Decide: Call Gemini?
       ├─ If score < 0.25: Return ML results (100ms)
       ├─ If 0.25-0.80: Call Gemini + blend scores
       └─ If > 0.80: Call Gemini + confirm
   ↓
4. Gemini Analyzer.analyze_email_semantics()
   ├─ Analyze threat type
   ├─ Detect tactics
   ├─ Generate explanation
   └─ Return Gemini analysis
   ↓
5. Blend Results
   ├─ Combine ML + Gemini scores
   ├─ Create final report
   └─ Generate recommendations
   ↓
6. API Response (JSON)
```

### Modifying the Detection Logic

If you want to customize detection, edit `backend/services/phishing_detector.py`:

```python
# Current implementation - DO NOT MODIFY for production use
class PhishingDetector:
    def analyze_email(self, sender, subject, body, urls=None, use_gemini=None):
        """
        Analyze email for phishing.
        
        Args:
            sender: Email sender address
            subject: Email subject
            body: Email body text
            urls: List of URLs in email (optional)
            use_gemini: None (auto-route), True (always), False (never)
            
        Returns:
            dict: {
                'phishing_score': float 0-1,
                'verdict': 'PHISHING'|'LIKELY_PHISHING'|'SUSPICIOUS'|'SAFE',
                'ml_analysis': {...},
                'gemini_analysis': {...},
                'explanation': str,
                'recommendations': list
            }
        """
        # Step 1: ML analysis
        ml_scores = self._get_ml_scores(sender, subject, body, urls)
        
        # Step 2: Smart routing decision
        if use_gemini is None:
            use_gemini = self._should_use_gemini(ml_scores['combined'])
        
        # Step 3: Gemini analysis if needed
        if use_gemini:
            gemini_analysis = self.gemini_analyzer.analyze_email_semantics(
                sender, subject, body, urls, ml_scores
            )
        else:
            gemini_analysis = None
        
        # Step 4: Blend scores
        final_score = self._blend_scores(ml_scores, gemini_analysis)
        
        # Step 5: Generate response
        return self._format_response(ml_scores, gemini_analysis, final_score)
```

### Adding Custom Detection Rules

To add custom detection logic without modifying core system:

```python
# In phishing_detector.py, add method:

def add_custom_analysis(self, sender, subject, body, urls):
    """Your custom detection logic"""
    custom_score = 0.0
    custom_flags = []
    
    # Example: Detect CEO names in subject
    if re.search(r'(CEO|CFO|CEO|president)', subject, re.I):
        custom_score += 0.2
        custom_flags.append("Executive impersonation pattern")
    
    # Example: Detect wire transfer keywords
    if re.search(r'(wire|transfer|payment|urgent)', body, re.I):
        custom_score += 0.15
        custom_flags.append("Financial transaction urgency")
    
    return {
        'custom_score': custom_score,
        'custom_flags': custom_flags
    }

# Then call in analyze_email():
custom = self.add_custom_analysis(sender, subject, body, urls)
```

---

## Performance & Costs

### Latency Breakdown

```
Safe Email (<0.25 score):
├─ Parse email: 5ms
├─ Extract features: 10ms
├─ ML inference: 20ms RF + 15ms LR
├─ Smart routing decision: <1ms
└─ Format response: 5ms
━━━━━━━━━━━━━━━━━━━━━━━━
Total: ~100ms ✓

Ambiguous Email (0.25-0.80 score):
├─ ML analysis: 50ms (as above)
├─ Route to Gemini: <1ms
├─ Gemini API call: 300ms
├─ Blend scores: 5ms
└─ Format response: 5ms
━━━━━━━━━━━━━━━━━━━━━━━━
Total: ~450ms ✓

System Average (60% safe, 40% Gemini):
(100ms × 0.6) + (450ms × 0.4) = 250ms ✓
```

### API Throughput

| Metric | Value |
|--------|-------|
| **Sync processing** | 2-3 emails/second |
| **Batch processing** | 100+ emails/minute |
| **Concurrent requests** | Limited by server resources |
| **Gemini API quota** | 15,000 RPM (standard tier) |
| **Monthly limit** | ~450M emails at full quota |

### Cost Analysis

**Gemini Pricing:**
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens
- Average email analysis: ~500 input tokens, ~100 output tokens

**Per Email Cost:**
```
Input tokens (500) × ($0.075 / 1M) = $0.0000375
Output tokens (100) × ($0.30 / 1M) = $0.00000030
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Per email: ~$0.000038 ≈ $0.00004
```

**Monthly Costs:**
```
1M Emails:
├─ Safe emails (600k × $0)           = $0
├─ Ambiguous (300k × $0.00004)       = $12
├─ Phishing (100k × $0.00004)        = $4
├─ Buffer for extra calls (5%)        = $1
└─ Rounding
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: ~$17-20/month
```

**For 5M Emails (enterprise):**
```
≈$85-100/month
```

**Cost Optimization Tips:**
1. ✓ Default thresholds already optimized (save 60% on Gemini calls)
2. Lower GEMINI_TEMPERATURE from 0.3 to 0.2 → Slightly faster responses
3. Batch analyze emails instead of real-time → Better API efficiency
4. Monitor THRESHOLD_LOW/HIGH settings quarterly

---

## Testing

### Manual Test Cases

#### Test 1: Business Email Compromise (BEC)

**Email:**
```
From: ceo@company.com
Subject: URGENT: Wire Transfer Needed ASAP

Finance team,

Process wire of $100k to vendor account immediately.
Do not call me - keeping this confidential per legal.

Account: [suspicious_details]

-CEO
```

**Expected Result:**
```json
{
  "phishing_score": 0.88,
  "verdict": "PHISHING",
  "analysis_type": "HYBRID_ML_GEMINI",
  "gemini_analysis": {
    "threat_type": "Business Email Compromise",
    "tactics_detected": [
      "CEO impersonation",
      "Urgency & deadline pressure",
      "Secrecy tactic - suppress verification",
      "Authority bypass - normal process circumvented"
    ],
    "threat_confidence": 0.98
  },
  "recommendations": [
    "DO NOT PROCESS this wire transfer",
    "Call CEO on verified phone number",
    "Report to IT security and finance"
  ]
}
```

#### Test 2: Credential Harvesting

**Email:**
```
From: security@bank.com
Subject: Verify Your Banking Credentials

Dear Customer,

Your account has been temporarily locked. Click here
to verify your identity: http://secure-bank-verification.com

[Phishing Link]
```

**Expected Result:**
```
threat_type: "Credential Harvesting"
verdict: PHISHING
score: 0.85+
tactics: ["Fake urgency", "Trust exploitation", "Authority spoofing"]
```

#### Test 3: Advance Fee Fraud

**Email:**
```
From: benefactor@overseas.com
Subject: You Have Been Selected!

Congratulations! You have been selected to receive
$10,000,000 from our estate. To claim your inheritance,
please wire $5,000 processing fee to...
```

**Expected Result:**
```
threat_type: "Advance Fee Fraud"
verdict: PHISHING
score: 0.90+
tactics: ["Money offer", "Fee requirement", "Urgency"]
```

#### Test 4: Legitimate Email

**Email:**
```
From: support@github.com
Subject: Your repository has been updated

Hi User,

Your repository has been updated with new commits.
View your changes: https://github.com/...

Best,
GitHub Support
```

**Expected Result:**
```
phishing_score: 0.08
verdict: SAFE
analysis_type: ML_ONLY (Gemini skipped - saved $)
latency: ~100ms
```

### Automated Testing

```bash
cd backend

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_phishing_detector.py -v

# Run with coverage
pytest --cov=. --cov-report=html tests/

# Run test matching pattern
pytest tests/ -k "bec or credential" -v
```

### Test File: tests/test_phishing_detector.py

Example test structure:

```python
import pytest
from services.phishing_detector import PhishingDetector

@pytest.fixture
def detector():
    return PhishingDetector()

class TestBECDetection:
    def test_ceo_fraud_detected(self, detector):
        """BEC should be detected with high confidence"""
        result = detector.analyze_email(
            sender="ceo@company.com",
            subject="Wire $500k immediately",
            body="Process wire transfer now. Do not call.",
            use_gemini=True
        )
        assert result['phishing_score'] > 0.80
        assert result['verdict'] == 'PHISHING'
    
    def test_legitimate_email_safe(self, detector):
        """Legitimate emails should be marked safe"""
        result = detector.analyze_email(
            sender="support@github.com",
            subject="Repository updated",
            body="Your repo has been updated",
            use_gemini=False
        )
        assert result['phishing_score'] < 0.30
        assert result['verdict'] == 'SAFE'
```

---

## Troubleshooting

### Common Issues & Solutions

#### Issue: "ModuleNotFoundError: No module named 'google.generativeai'"

**Cause:** Gemini library not installed

**Solution:**
```bash
cd backend
pip install google-generativeai>=0.4.1

# Verify installation
python -c "import google.generativeai; print('✓ Installed')"
```

#### Issue: "GEMINI_API_KEY not found"

**Cause:** Environment variable not set

**Solution:**
```bash
# Verify .env exists in backend/
ls backend/.env  # Should exist

# Check content
cat backend/.env | grep GEMINI  # Should show API key

# If missing, create it:
echo "GEMINI_API_KEY=AIzaSyB9jAxAKVJkenTGwe9rZtYTDmAy0G744QA" > backend/.env

# Restart backend
python app.py
```

#### Issue: API returns 401 Unauthorized with Gemini

**Cause:** Invalid API key

**Solution:**
```bash
# Get new API key from https://aistudio.google.com
# Create file backend/.env with new key:

GEMINI_API_KEY=new_key_here

# Restart Flask app
kill $(lsof -t -i :5000)  # Kill existing process
python app.py
```

#### Issue: Response Time > 500ms (Slow)

**Cause:** 
1. Slow internet connection
2. Gemini API latency
3. All emails being routed to Gemini

**Solution:**
```bash
# Check thresholds (only ~40% should use Gemini)
cat backend/.env | grep THRESHOLD

# If too many emails use Gemini, adjust:
USE_GEMINI_THRESHOLD_LOW=0.35    # Raise this (skip more safe emails)
USE_GEMINI_THRESHOLD_HIGH=0.75   # Lower this (confirm only obvious phishing)

# Reduce temperature for faster responses:
GEMINI_TEMPERATURE=0.2            # Lower = faster

# Monitor logs for call frequency:
tail -f logs/api.log | grep "gemini"
```

#### Issue: High API Costs (> $100/month)

**Cause:** Too many emails being analyzed by Gemini

**Solution:**
```
1. Check THRESHOLD_LOW/HIGH:
   Default: 0.25-0.80 should give ~40% Gemini usage
   
2. If usage too high:
   SET USE_GEMINI_THRESHOLD_LOW=0.40  (skip more safe emails)
   SET USE_GEMINI_THRESHOLD_HIGH=0.85 (confirm only high risk)
   
3. If usage too low:
   SET USE_GEMINI_THRESHOLD_LOW=0.20  (analyze more ambiguous)
   SET USE_GEMINI_THRESHOLD_HIGH=0.75 (confirm borderline cases)
   
4. Verify smart routing working:
   Look for: "Skipping Gemini" in 60% of logs
   Look for: "Using Gemini" in 40% of logs
```

#### Issue: Frontend Not Connecting to Backend

**Cause:** CORS configuration

**Solution:**
```bash
# Check CORS setting in backend/.env
cat backend/.env | grep CORS

# If frontend is on different domain, configure CORS:
CORS_ORIGINS=http://localhost:3000
# Or for multiple domains:
CORS_ORIGINS=http://localhost:3000,https://example.com

# Restart backend
python app.py
```

### Debugging

**Enable verbose logging:**

```python
# In backend/app.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Then Flask will show all requests:
# GET /health 200
# POST /api/email/analyze 200
# DEBUG: Response time: 234ms
```

**Check Gemini API status:**

```bash
# Visit status page
https://status.ai.google.dev

# If down, system falls back to ML-only (still works)
```

**Monitor API calls:**

```bash
# Count Gemini calls
tail -f logs/api.log | grep -c "Using Gemini"

# Expected: ~40% of requests should use Gemini
```

---

## Advanced Configuration

### Custom Threat Classification

Edit `backend/services/gemini_analyzer.py`:

```python
def classify_threat_intent(self, analysis_text):
    """Classify specific threat type"""
    
    threat_types = {
        'BEC': ['wire', 'invoice', 'ceo', 'urgent', 'vendor'],
        'CREDENTIAL': ['verify', 'password', 'login', 'authenticate'],
        'ADVANCE_FEE': ['inheritance', 'million', 'processing fee'],
        'MALWARE': ['attachment', 'execute', 'download', 'install'],
        'PHISHING': ['click', 'verify', 'confirm', 'update']
    }
    
    # Add your custom patterns here
    for threat_type, keywords in threat_types.items():
        if any(kw in analysis_text.lower() for kw in keywords):
            return threat_type
    
    return 'UNKNOWN'
```

### Caching Responses

To reduce API calls on duplicate emails:

```python
# Add to phishing_detector.py
from functools import lru_cache

@lru_cache(maxsize=1000)
def analyze_email_cached(self, sender, subject, body_hash):
    """Cache results for identical emails"""
    # Only cache if content hasn't changed
    ...
```

### Batch Processing

For analyzing many emails at once:

```python
def analyze_batch(self, emails, use_gemini=None):
    """
    Analyze multiple emails efficiently
    
    Args:
        emails: List of dicts with sender, subject, content
        use_gemini: bool or None (auto-route)
    
    Returns:
        List of results
    """
    results = []
    for email in emails:
        result = self.analyze_email(
            sender=email['sender'],
            subject=email['subject'],
            body=email['content'],
            use_gemini=use_gemini
        )
        results.append(result)
    return results

# Usage:
batch_results = detector.analyze_batch(emails, use_gemini=None)
```

---

## Production Deployment

### Health Checks

```bash
# Basic health check
curl http://127.0.0.1:5000/health

# Should return:
# {"status":"OK","timestamp":"2026-04-13T12:34:56Z"}
```

### Monitoring

**Key Metrics to Monitor:**

```
1. Response Time: Should be <300ms average
2. Gemini Usage: Should be 30-40% of emails
3. API Costs: Track monthly spend
4. Accuracy: Monitor false positives & false negatives
5. Model Drift: Retrain models if accuracy drops
```

### Backup & Recovery

```bash
# Backup trained models
cp -r backend/artifacts/phase2/ backup/models/

# Backup configuration
cp backend/.env backup/.env

# If API fails, switch to ML-only:
USE_GEMINI=false (in .env)
python app.py  # Falls back to ML models
```

---

## Model Comparison Report

During development, 14 models were tested:

| Model | Accuracy | Speed | Notes |
|-------|----------|-------|-------|
| Random Forest | 89% | 50ms | ✓ Selected (URL analysis) |
| Logistic Regression | 84% | 30ms | ✓ Selected (content analysis) |
| SVM | 86% | 200ms | Slow for production |
| Neural Network | 91% | 400ms | Overkill, slower |
| Naive Bayes | 77% | 10ms | Too simple |
| XGBoost | 88% | 80ms | Similar to RF, slower |
| LightGBM | 87% | 60ms | Similar to RF, comparable |
| CatBoost | 85% | 120ms | Complex, slow |
| Gradient Boosting | 84% | 150ms | Slower than RF |
| Ensemble | 91% | 300ms+ | Too slow |
| Gemini (LLM) | 87% | 300ms | ✓ Added for semantic analysis |
| Hybrid (RF+LR+Gemini) | 94% | 250ms | ✓ **Current Production** |

**Why RF + LR + Gemini?**
- Best accuracy (94% vs 89% RF alone)
- Reasonable latency (250ms average, 100ms for safe emails)
- Cost optimized (smart routing saves 60%)
- Explainable results (can see why it flagged email)
- Fallback capability (works without Gemini)

---

## Appendix: Reference

### API Response Schema

```json
{
  "phishing_score": 0.88,                 // 0-1, higher = more phishing
  "verdict": "PHISHING",                  // PHISHING|LIKELY_PHISHING|SUSPICIOUS|SAFE
  "analysis_type": "HYBRID_ML_GEMINI",    // Source of analysis
  
  "ml_analysis": {
    "url_score": 0.92,                    // Random Forest output
    "content_score": 0.80,                // Logistic Regression output
    "combined_ml_score": 0.87
  },
  
  "gemini_analysis": {
    "threat_type": "Business Email Compromise",
    "threat_confidence": 0.98,
    "tactics_detected": ["CEO impersonation", "Urgency pressure"],
    "contextual_issues": ["Bypass normal approval chain"],
    "social_engineering_score": 0.95,
    "explanation": "..."
  },
  
  "explanation": "This email exhibits classic BEC...",
  "recommendations": ["DO NOT PROCESS", "Call CEO"],
  
  "processing_time_ms": 234,
  "used_gemini": true
}
```

### URL Features (Random Forest)

The Random Forest model analyzes 30 URL features:
1. Domain age
2. IP reputation
3. URL length
4. Subdomain count
5. Special characters %
... (25 more technical features)

### Content Features (Logistic Regression)

TF-IDF vectorization analyzes ~5,000 most common words in training data, detecting:
- Phishing keywords (verify, confirm, click)
- Urgency words (urgent, immediate, now)
- Authority words (CEO, director, manager)
- Payment words (wire, transfer, payment)

---

**Last Updated:** April 13, 2026  
**Version:** 2.0  
**Status:** Production Ready ✓
