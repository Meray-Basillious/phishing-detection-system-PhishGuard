# PhishGuard Project Structure

## 📁 Directory Overview

### `/backend` - Flask API Server & ML Models
Core application logic, API routes, and machine learning models for phishing detection.

**Key Files:**
- `app.py` - Flask application factory, CORS setup, blueprint registration
- `config.py` - Configuration management for different environments
- `models.py` - SQLAlchemy ORM models (User, Email, ThreatAlert, AnalysisLog)
- `requirements.txt` - Python dependencies

**Subdirectories:**
- `routes/` - API endpoint handlers
  - `email_routes.py` - Email analysis endpoints
- `services/` - Business logic and utilities
  - `phishing_detector.py` - Main detection engine (heuristics + ML scoring)
  - `phase2_models.py` - ML model utilities and feature extraction
- `artifacts/phase2/` - Trained ML models
  - `content_model.joblib` - Logistic Regression model for email content
  - `url_model.joblib` - Random Forest model for URL analysis
  - `url_intel.joblib` - Known phishing domains/URLs database
  - `metadata.json` - Model metadata and training statistics
- `instance/` - Runtime data
  - `phishing_db.db` - SQLite database (auto-generated on first run)

**Training Scripts:**
- `train_phase2.py` - Original training pipeline (RF + LR models)
- `train_phase2_model_comparison.py` - Comparison framework for 14 ML models

### `/frontend` - React Web UI
User interface for phishing detection and email analysis.

**Configuration:**
- `package.json` - Dependencies and build scripts
- `public/index.html` - HTML entry point

**Application:**
- `src/index.js` - React app entry point
- `src/App.jsx` - Main app component
- `src/services/api.js` - Axios HTTP client for backend API calls
- `src/components/` - React functional components
  - `Dashboard.jsx` - Main dashboard/home view
  - `EmailAnalyzer.jsx` - Email submission and analysis interface
  - `EmailHistory.jsx` - View previously analyzed emails
  - `ReportsAnalytics.jsx` - Threat analytics and reports
- `src/styles/` - Component-specific CSS
  - `App.css`, `Dashboard.css`, `EmailAnalyzer.css`, `EmailHistory.css`, `ReportsAnalytics.css`, `index.css`

### `/docs` - Documentation
Consolidated documentation for the project.

- `INDEX.md` - Complete roadmap and navigation guide
- `QUICK_REFERENCE.md` - TL;DR version (3 pages)
- `EXECUTIVE_SUMMARY.md` - High-level overview (5 pages)
- `IMPLEMENTATION_SUMMARY.md` - Implementation details (8 pages)
- `MODEL_COMPARISON_FRAMEWORK.md` - How the comparison framework works (6 pages)
- `MODEL_COMPARISON_GUIDE.md` - Detailed model comparison analysis (30+ pages)
- `README_MODEL_COMPARISON.md` - Visual model comparison summary

### `/tests` - Test Scripts
Automated test suites and health checks.

- `simple_test.ps1` - Basic API endpoint tests
- `test_api.ps1` - Comprehensive API testing suite

### `/test_data` - Training Data
Training datasets for model development.

- `Nigerian_Fraud.csv` - Phishing email dataset for model training

### Root Level Files

- `README.md` - Main project overview and quick start guide
- `PROJECT_STRUCTURE.md` - This file

## 🚀 Quick Start

### Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python app.py
```

Backend runs on: `http://127.0.0.1:5000`

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

Frontend runs on: `http://localhost:3000`

## 🤖 Phishing Detection Engine

The detection system combines two approaches:

1. **Heuristic Analysis** - Rule-based scoring:
   - Sender spoofing detection
   - Suspicious keywords
   - Domain analysis
   - Urgency detection
   - Impersonation patterns

2. **ML Models** - Statistical classification:
   - **URL Model**: Random Forest (300 trees) for URL analysis
   - **Content Model**: Logistic Regression for email content
   - Features: domain reputation, SSL info, URL structure, text patterns

## 📊 API Endpoints

### Health Check
`GET /health` - Service status

### Email Analysis
`POST /api/email/analyze` - Submit email for phishing detection
- Request body: `{ subject, sender, content, urls }`
- Returns: Phishing score (0-100) and detailed analysis

## 🗄️ Database Schema

**Users** - User account information
**Emails** - Submitted emails and analysis results
**ThreatAlerts** - Detected threats and warnings
**AnalysisLogs** - History of all analyses performed

## 📚 Model Comparison

14 ML models are included for comparison:
- Random Forest (Chosen for URLs)
- Logistic Regression (Chosen for content)
- Gradient Boosting, SVM, Neural Networks, KNeighbors
- AdaBoost, Extra Trees, Naive Bayes, and others

See `/docs/MODEL_COMPARISON_GUIDE.md` for detailed metrics and analysis.

## 🔧 Configuration

Backend environment variables (create `backend/.env`):
```env
FLASK_ENV=development
FLASK_DEBUG=True
DATABASE_URL=sqlite:///instance/phishing_db.db
SECRET_KEY=your-secret-key
```

## 📋 File Size Summary

- **Total Python files**: 12
- **Total React components**: 5
- **ML models**: 3 joblib files (~50 MB combined)
- **Documentation**: 7 consolidated files
- **Test scripts**: 2

## ✅ What Each File Does

| File | Purpose |
|------|---------|
| `app.py` | Flask application setup and blog routing |
| `config.py` | Configuration for dev, test, prod environments |
| `models.py` | Database model definitions |
| `phishing_detector.py` | Main detection logic combining heuristics + ML |
| `phase2_models.py` | ML model loading and feature extraction |
| `email_routes.py` | REST API endpoints for email analysis |
| `App.jsx` | Main React component wrapper |
| `Dashboard.jsx` | Home/main view with statistics |
| `EmailAnalyzer.jsx` | Email submission form and results |
| `api.js` | HTTP client for backend communication |

---

**Last Updated**: 2026-04-12
**Cleanup Status**: ✓ Organized and minimized
- ✓ Documentation consolidated to `/docs`
- ✓ Duplicate databases removed
- ✓ Test scripts organized in `/tests`
- ✓ Lock files cleaned up
- ✓ Redundant directories removed
