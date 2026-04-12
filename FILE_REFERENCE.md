# PhishGuard - Complete File Reference

## 📋 Purpose of Every File

A detailed guide to what each file does, its code functionality, and how it fits into the system.

---

## 🔧 Backend Files (`/backend`)

### Core Application Files

#### **`app.py` (48 lines)**
**Purpose:** Flask application factory and entry point  
**What it does:**
- Creates Flask app with configuration loading
- Registers blueprints (connects email_routes)
- Initializes CORS for frontend communication
- Sets up SQLAlchemy database ORM
- Defines health check endpoint (`/health`)

**Key Functions:**
```python
create_app()      # Creates and configures Flask app
```

**Dependencies:** Flask, flask_cors, flask_sqlalchemy

---

#### **`config.py`**
**Purpose:** Configuration management for different environments  
**What it does:**
- Defines configuration classes (Development, Testing, Production)
- Sets database URI
- Configures Flask settings (debug, testing mode)
- Manages environment-specific settings

**Key Settings:**
- `SQLALCHEMY_DATABASE_URI` - SQLite database path
- `SQL_TRACK_MODIFICATIONS` - Disable SQLAlchemy modification tracking
- `TESTING` - Enable/disable test mode

**Usage:** Imported by app.py to load appropriate config based on environment

---

#### **`models.py`**
**Purpose:** SQLAlchemy ORM database models  
**What it does:**
- Defines 4 database tables as Python classes
- Establishes relationships between tables
- Provides object-oriented database interface

**Tables:**

1. **User Model**
   - user_id (PK)
   - username, email, password_hash
   - role (admin/analyst/user)
   - created_at timestamp

2. **Email Model**
   - email_id (PK)
   - sender, recipient, subject, content
   - urls (text field with comma-separated URLs)
   - phishing_score, is_phishing (boolean)
   - user_id (FK to User)
   - analyzed_at timestamp

3. **ThreatAlert Model**
   - alert_id (PK)
   - email_id (FK)
   - threat_type (keyword/url/sender/etc)
   - severity (low/medium/high)
   - description

4. **AnalysisLog Model**
   - log_id (PK)
   - email_id (FK)
   - action, result, timestamp
   - Audit trail for compliance

**Relationships:**
```
User → Email (one-to-many)
Email → ThreatAlert (one-to-many)
Email → AnalysisLog (one-to-many)
```

---

#### **`requirements.txt`**
**Purpose:** Python dependency declarations  
**What it does:**
- Lists all pip packages and versions (40+ packages)
- Installed via: `pip install -r requirements.txt`

**Key Packages:**
- `flask==3.1.3` - Web framework
- `flask-sqlalchemy==3.1.1` - Database ORM
- `flask-cors==4.0.0` - Cross-origin requests
- `scikit-learn==1.8.0` - ML models
- `pandas==2.2.0` - Data manipulation
- `numpy==1.26.4` - Numerical computing
- `joblib==1.4.2` - Model serialization
- `requests==2.31.0` - HTTP requests
- `python-dotenv==1.0.1` - Environment variables

---

#### **`.env` (root level in backend)**
**Purpose:** Environment variables configuration  
**What it does:**
- Stores sensitive settings not committed to Git
- Contains API keys, database URLs, secret keys

**Example variables:**
```
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///instance/phishing_db.db
```

---

### Routes (API Endpoints)

#### **`routes/__init__.py`**
**Purpose:** Package initialization  
**What it does:**
- Imports and registers blueprints
- Makes routes module a Python package

---

#### **`routes/email_routes.py`**
**Purpose:** Email analysis API endpoints  
**What it does:**
- Defines REST API endpoints for email handling
- Validates incoming requests
- Calls phishing detector service
- Returns JSON responses

**Endpoints:**

| Method | Endpoint | Function |
|--------|----------|----------|
| POST | `/api/email/analyze` | `analyze_email()` - Analyze single email |
| GET | `/health` | `health_check()` - Service status |

**Request Example:**
```json
{
  "sender": "user@example.com",
  "recipient": "target@company.com",
  "subject": "Urgent Account Update",
  "content": "Click here to verify your account",
  "urls": ["http://suspicious-site.com"]
}
```

**Response Example:**
```json
{
  "phishing_score": 78,
  "is_phishing": true,
  "confidence": 0.89,
  "analysis": {
    "sender_score": 0.45,
    "url_score": 0.92,
    "content_score": 0.65
  }
}
```

**Processing Flow:**
1. Validate JSON input
2. Create Email record in database
3. Call phishing_detector service
4. Return scored results

---

### Services (Business Logic)

#### **`services/__init__.py`**
**Purpose:** Package initialization  
**What it does:**
- Makes services module a Python package
- May contain shared imports/utilities

---

#### **`services/phishing_detector.py` (500+ lines)**
**Purpose:** Main phishing detection engine  
**What it does:**
- Combines heuristic and ML-based detection
- Scores emails on multiple dimensions
- Returns comprehensive threat analysis

**Core Components:**

**1. Heuristic Scoring (Rule-based)**
- `score_sender()` - Checks email format, domain spoofing
- `score_subject()` - Detects phishing keywords
- `score_body()` - Analyzes email content patterns
- `score_urls()` - Examines URL structure
- `score_urgency()` - Detects social engineering language

**Heuristic Rules Include:**
- Suspecious keywords: "verify", "confirm", "urgent", "act now"
- Sender validation: "@" presence, domain legitimacy
- URL analysis: IP detection, shortener detection
- Domain reputation: Known malicious domains

**2. ML-Based Scoring**
- `score_with_ml()` - Uses trained models
- Combines Random Forest (URLs) + Logistic Regression (content)

**3. Composite Scoring**
- Weighted combination of all scores
- Final score: 0-100 (0=safe, 100=phishing)
- Confidence level calculation

**Weight Distribution:**
- Sender analysis: 18%
- Subject analysis: 12%
- Body content: 25%
- URL analysis: 15%
- Urgency indicators: 10%
- Impersonation patterns: 10%
- Other factors: 10%

**Main Method:**
```python
def detect_phishing(sender, recipient, subject, content, urls):
    """
    Analyze email and return phishing assessment
    Returns: {phishing_score, is_phishing, confidence, details}
    """
```

**Output Example:**
```python
{
    "phishing_score": 82,
    "is_phishing": True,
    "confidence": 0.91,
    "details": {
        "sender_score": 0.45,
        "subject_score": 0.65,
        "body_score": 0.80,
        "url_score": 0.95,
        "urgency_score": 0.70
    }
}
```

---

#### **`services/phase2_models.py` (300+ lines)**
**Purpose:** ML model utilities and feature extraction  
**What it does:**
- Loads trained ML models from disk
- Extracts features from URLs and text
- Provides model interface for predictions

**Key Class: `Phase2ModelBundle`**

**Initialization:**
```python
bundle = Phase2ModelBundle()
bundle.load_models()  # Load from artifacts/phase2/
```

**Methods:**

1. **`load_models()`**
   - Loads joblib files from disk
   - Loads RF model (url_model.joblib)
   - Loads LR model (content_model.joblib)
   - Loads known-phishing database (url_intel.joblib)

2. **`score_url(url)`**
   - Extracts 30+ features from URL
   - Runs through Random Forest model
   - Returns probability (0-1)

3. **`score_content(text)`**
   - Converts text to TF-IDF features
   - Runs through Logistic Regression model
   - Returns probability (0-1)

**URL Feature Extraction (30 features):**
- URL length
- Domain age
- SSL certificate validity
- IP vs domain notation
- Suspicious TLDs
- URL entropy
- Special characters count
- Known phishing domain match
- And more...

**Text Feature Extraction:**
- Term frequency-inverse document frequency (TF-IDF)
- Extracted from training data vocabulary
- Vectorized into dense array

**Models Artifacts:**
- `url_model.joblib` (5 MB) - Random Forest 300 trees
- `content_model.joblib` (2 MB) - Logistic Regression + TF-IDF
- `url_intel.joblib` (500 KB) - Known malicious URLs database
- `metadata.json` - Model training metadata

---

### Training Scripts

#### **`train_phase2.py` (480 lines)**
**Purpose:** Original ML model training pipeline  
**What it does:**
- Loads training dataset (Nigerian_Fraud.csv)
- Preprocesses data
- Trains Random Forest (URLs) + Logistic Regression (content)
- Saves models to artifacts/

**Training Process:**
1. Load CSV dataset
2. Split into train/test (80/20)
3. Feature engineering:
   - Extract 30 URL features
   - TF-IDF vectorization of text
4. Train models:
   - Random Forest: 300 trees, max_depth=15
   - Logistic Regression: max_iter=1000
5. Evaluate:
   - Accuracy, Precision, Recall, F1 Score
   - Print metrics to console
6. Save to artifacts/phase2/

**Output Files:**
```
artifacts/phase2/
├── content_model.joblib
├── url_model.joblib
├── url_intel.joblib
└── metadata.json
```

**Metrics Generated:**
- Accuracy: ~85-90%
- Precision: ~0.84-0.88
- Recall: ~0.82-0.87
- F1 Score: ~0.83-0.88

---

#### **`train_phase2_model_comparison.py` (500+ lines)**
**Purpose:** Comprehensive 14-model comparison framework  
**What it does:**
- Trains multiple ML algorithms on same dataset
- Generates detailed metrics for each model
- Creates comparison table and analysis
- Helps validate Random Forest choice

**Models Tested:**
1. Random Forest (300 trees)
2. Logistic Regression
3. Gradient Boosting
4. Support Vector Machine (SVM)
5. Neural Network (MLPClassifier)
6. K-Nearest Neighbors
7. AdaBoost
8. Extra Trees
9. Decision Tree
10. Naive Bayes
11. Gaussian Naive Bayes
12. Linear SVM
13. Ridge Regression
14. SGD Classifier

**Metrics Calculated for Each:**
- Accuracy
- Precision
- Recall
- F1 Score
- ROC-AUC Score
- Training time
- Prediction time

**Output:**
- Console table with all metrics
- Rankings (best to worst)
- Selected model recommendations

**Run Command:**
```bash
python train_phase2_model_comparison.py --url-only --skip-download
```

**Flags:**
- `--url-only` - Test only URL models (faster)
- `--skip-download` - Use existing dataset

---

### Database & Artifacts

#### **`instance/phishing_db.db`**
**Purpose:** SQLite database file (auto-generated)  
**What it does:**
- Stores User, Email, ThreatAlert, AnalysisLog tables
- Created automatically on first app run
- Persists all analysis data

**File Size:** ~1 MB (grows with usage)

---

#### **`artifacts/phase2/` folder**

**`content_model.joblib` (2 MB)**
- Serialized Logistic Regression model
- TF-IDF vectorizer for text
- Used for email content scoring

**`url_model.joblib` (5 MB)**
- Serialized Random Forest model (300 trees)
- Used for URL scoring (highest priority)

**`url_intel.joblib` (500 KB)**
- Dictionary/set of known phishing URLs/domains
- Used for reputation-based matching

**`metadata.json`**
```json
{
  "models": {
    "url_model": {
      "algorithm": "RandomForest",
      "trees": 300,
      "accuracy": 0.89,
      "f1_score": 0.87
    },
    "content_model": {
      "algorithm": "LogisticRegression", 
      "accuracy": 0.84,
      "f1_score": 0.81
    }
  },
  "training_data": "Nigerian_Fraud.csv",
  "features_extracted": 30,
  "trained_date": "2026-04-12",
  "version": "1.0"
}
```

---

## 🎨 Frontend Files (`/frontend`)

### Configuration & Entry Point

#### **`package.json`**
**Purpose:** Node.js project configuration and dependencies  
**What it does:**
- Declares npm scripts (start, build, test)
- Lists JavaScript/React dependencies
- Configures build tools and dev server

**Key Scripts:**
```json
{
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test"
  }
}
```

**Key Dependencies:**
- `react@18.2.0` - React library
- `axios@1.6.2` - HTTP client
- `chart.js@4.4.0` - Charting library (for analytics)
- `react-router-dom@6.20.1` - Client-side routing

---

#### **`public/index.html`**
**Purpose:** Main HTML entry point  
**What it does:**
- Basic HTML structure
- Root `<div id="root">` where React mounts
- Links stylesheet, scripts
- Meta tags and favicon

```html
<!DOCTYPE html>
<html>
  <head>
    <title>PhishGuard - Email Security</title>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
```

---

### React Application

#### **`src/index.js`**
**Purpose:** React app initialization  
**What it does:**
- Imports React and ReactDOM
- Renders App component into root div
- Sets up React application entry point

```javascript
import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';
import './styles/index.css';

ReactDOM.render(<App />, document.getElementById('root'));
```

---

#### **`src/App.jsx` (Main Component)**
**Purpose:** Root component wrapper  
**What it does:**
- Wraps entire application
- Sets up routing with React Router
- Provides state for globally shared data
- Handles authentication state (if implemented)

**Component Structure:**
```jsx
<BrowserRouter>
  <div className="App">
    <Navigation />
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/analyze" element={<EmailAnalyzer />} />
      <Route path="/history" element={<EmailHistory />} />
      <Route path="/reports" element={<ReportsAnalytics />} />
    </Routes>
  </div>
</BrowserRouter>
```

**Key Features:**
- Global error boundary
- API base URL configuration
- Theme/style context (if applicable)

---

### Components (`/src/components`)

#### **`Dashboard.jsx`**
**Purpose:** Main home/dashboard view  
**What it does:**
- Displays statistics and overview
- Shows recent emails analyzed
- Displays phishing trends
- Links to other views

**Display Elements:**
- Total emails analyzed (count)
- Phishing detected (count)
- Detection rate (percentage)
- Recent analysis results (table)
- Phishing score distribution (chart)

**State Variables:**
```javascript
const [stats, setStats] = useState({});
const [recentEmails, setRecentEmails] = useState([]);
const [loading, setLoading] = useState(true);
```

**On Mount:**
- Fetches statistics from `/api/email/statistics`
- Fetches recent email history
- Renders charts with Chart.js

---

#### **`EmailAnalyzer.jsx`**
**Purpose:** Email submission and analysis interface  
**What it does:**
- Form for user to submit email details
- Sends to backend for analysis
- Displays real-time analysis results
- Shows phishing score visualization

**Form Fields:**
- Sender (email address)
- Recipient (email address)
- Subject (text input)
- Content (textarea)
- URLs (comma-separated input)

**Analysis Display:**
```
┌─ Phishing Score: 78/100 ──────────┐
│ [████████░░] (78%)                 │
│ Status: LIKELY PHISHING ⚠️          │
│ Confidence: 89%                    │
│                                    │
│ Breakdown:                         │
│ • Sender:    45/100                │
│ • Subject:   65/100                │
│ • Content:   80/100                │
│ • URLs:      92/100                │
│ • Urgency:   70/100                │
└────────────────────────────────────┘
```

**Functionality:**
- Form validation
- POST to `/api/email/analyze`
- Loading spinner during analysis
- Error handling and display
- Save to database on analysis

---

#### **`EmailHistory.jsx`**
**Purpose:** View previously analyzed emails  
**What it does:**
- Lists all submitted emails
- Shows analysis results in table
- Provides filtering/sorting
- Links to detailed view

**Table Columns:**
- Date Analyzed
- Sender
- Subject
- Phishing Score
- Status (Phishing/Safe)
- Action buttons (View, Re-analyze, Mark)

**Features:**
- Pagination (10-20 per page)
- Sort by date, score, status
- Search by sender/subject
- Filter by date range
- Delete old records

**API Call:**
```javascript
GET /api/emails/history?page=1&limit=20&sort=date
```

---

#### **`ReportsAnalytics.jsx`**
**Purpose:** Threat analytics and reporting dashboard  
**What it does:**
- Visualizes phishing statistics
- Shows trends over time
- Displays threat categories
- Generates exportable reports

**Charts/Graphs:**
- Phishing detection rate (line chart)
- Score distribution (histogram)
- Threat types (pie chart)
- Top phishing senders (bar chart)
- Daily average score (line chart)

**Metrics Displayed:**
- Total emails analyzed
- Phishing detected count
- Safe emails count
- Detection accuracy
- Most common threat type
- Average phishing score

**Export Functionality:**
- Download as CSV
- Download as PDF (if implemented)
- Print report

---

### Services

#### **`src/services/api.js`**
**Purpose:** HTTP client for backend API communication  
**What it does:**
- Configures Axios instance
- Provides methods for API calls
- Handles errors and responses
- Manages authentication headers

**Configuration:**
```javascript
const API_BASE_URL = 'http://127.0.0.1:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 5000,
  headers: {
    'Content-Type': 'application/json'
  }
});
```

**Exported Methods:**

| Method | Endpoint | Usage |
|--------|----------|-------|
| `analyzeEmail()` | `POST /api/email/analyze` | Submit email for analysis |
| `getEmailHistory()` | `GET /api/emails/history` | Fetch analyzed emails |
| `getStatistics()` | `GET /api/emails/statistics` | Fetch dashboard stats |
| `getHealthStatus()` | `GET /health` | Check API status |

**Example Method:**
```javascript
export const analyzeEmail = async (emailData) => {
  try {
    const response = await api.post('/api/email/analyze', emailData);
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};
```

**Error Handling:**
- Network errors
- API validation errors
- Server (500) errors
- Timeout handling

---

### Styles (`/src/styles`)

#### **`index.css` (Global Styles)**
**Purpose:** Global CSS for entire application  
**What it does:**
- Resets browser defaults
- Defines color variables/theme
- Sets typography
- Global layout styles

**Contains:**
```css
:root {
  --primary-color: #2c3e50;
  --success-color: #27ae60;
  --danger-color: #e74c3c;
  --warning-color: #f39c12;
}

body {
  font-family: 'Segoe UI', Tahoma, sans-serif;
  margin: 0;
  padding: 0;
}
```

---

#### **`App.css` (App Component)**
**Purpose:** Styles for App wrapper component  
**What it does:**
- Layout structure (flexbox/grid)
- Navigation styling
- Container styling
- Responsive breakpoints

---

#### **`Dashboard.css`**
**Purpose:** Dashboard view styles  
**What it does:**
- Stats card styling
- Chart container layout
- Typography for titles/numbers
- Card hover effects

**Classes:**
- `.stats-container` - Grid of stat cards
- `.stat-card` - Individual stat display
- `.chart-container` - Chart wrapper
- `.metric-number` - Large stat number

---

#### **`EmailAnalyzer.css`**
**Purpose:** Email analyzer form styles  
**What it does:**
- Form styling
- Input field styling
- Button styling
- Score visualization CSS

**Key Elements:**
- `.analyzer-form` - Form container
- `.input-group` - Form field wrapper
- `.score-display` - Phishing score visualization
- `.score-bar` - Progress bar for score

---

#### **`EmailHistory.css`**
**Purpose:** Email history table styles  
**What it does:**
- Table styling
- Row hover effects
- Status badge styling
- Pagination styling

**Classes:**
- `.email-table` - Main table
- `.status-badge` - Phishing/Safe badge
- `.date-cell` - Date formatting
- `.pagination` - Page navigation

---

#### **`ReportsAnalytics.css`**
**Purpose:** Reports dashboard styles  
**What it does:**
- Chart container styling
- Metric display styling
- Filter controls styling
- Export button styling

**Classes:**
- `.analytics-dashboard` - Main container
- `.chart-wrapper` - Individual chart container
- `.metrics-grid` - Key metrics display
- `.filter-controls` - Filter UI

---

## 📚 Documentation Files (`/docs`)

#### **`INDEX.md`**
Complete navigation guide to all documentation

#### **`QUICK_REFERENCE.md`**
3-page quick reference guide: setup, usage, troubleshooting

#### **`EXECUTIVE_SUMMARY.md`**
5-page project overview for stakeholders

#### **`IMPLEMENTATION_SUMMARY.md`**
8 pages of technical implementation details

#### **`MODEL_COMPARISON_FRAMEWORK.md`**
6 pages explaining the 14-model comparison framework

#### **`MODEL_COMPARISON_GUIDE.md`**
30+ pages of detailed model analysis and comparison metrics

#### **`README_MODEL_COMPARISON.md`**
Visual summary and quick lookup for model metrics

---

## 📋 Root Level Files

#### **`README.md`**
Main project overview with quick start, API endpoints, structure overview

#### **`PROJECT_STRUCTURE.md`**
Detailed file organization guide with purpose of each directory

#### **`FILE_REFERENCE.md` (this file)**
Complete reference of every file's code and functionality

---

## 🧪 Test Files (`/tests`)

#### **`simple_test.ps1`**
PowerShell script for basic API health checks

#### **`test_api.ps1`**
Comprehensive PowerShell API testing suite

---

## 📊 Test Data

#### **`test_data/Nigerian_Fraud.csv`**
Training dataset with ~1000 phishing email samples

---

## Summary Statistics

| Category | Count | Purpose |
|----------|-------|---------|
| Backend Python Files | 12 | Core API, models, services |
| Frontend React Files | 12 | UI components and styling |
| Documentation Files | 7 | Guides and references |
| Test Files | 2 | API testing |
| Config Files | 3 | package.json, requirements.txt, .env |
| **Total Core Project Files** | **44** | Clean, organized, minimal |

---

## 🔄 Data Flow Summary

```
User Email Input (EmailAnalyzer.jsx)
        ↓
POST /api/email/analyze (api.js)
        ↓
Flask Route Handler (email_routes.py)
        ↓
PhishingDetector Service (phishing_detector.py)
        ├─→ Heuristic Scoring
        └─→ ML Scoring (phase2_models.py)
              ├─→ URL Analysis (Random Forest)
              └─→ Content Analysis (Logistic Regression)
        ↓
Composite Score Calculation
        ↓
Database Storage (models.py → phishing_db.db)
        ↓
JSON Response
        ↓
Dashboard Display (Dashboard.jsx)
History Storage (EmailHistory.jsx)
```

---

**Last Updated:** 2026-04-12  
**Project Status:** ✅ Clean, organized, production-ready
