# Email Phishing Detection & Prevention System

An AI-powered email security solution that detects and prevents phishing attacks with real-time analysis and user-friendly interfaces.

## Project Structure

```
phishing-detection-system/
├── backend/
│   ├── services/
│   │   └── phishing_detector.py       # AI detection engine
│   ├── routes/
│   │   └── email_routes.py             # API endpoints
│   ├── models.py                       # Database models
│   ├── config.py                       # Configuration management
│   ├── app.py                          # Flask application
│   ├── requirements.txt                # Python dependencies
│   └── .env                            # Environment variables
├── frontend/
│   └── src/
│       └── components/                 # React components
└── README.md                          # This file
```

## Backend Setup

### Prerequisites
- Python 3.8+
- pip or conda

### Installation

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Train the Phase 2 models once:**
   ```bash
   python train_phase2.py
   ```
   This downloads the public corpora, trains the URL/content models, and saves artifacts under `backend/artifacts/phase2/`.

5. **Run the application:**
   ```bash
   python app.py
   ```

The API will be available at `http://localhost:5000`

## API Endpoints

### Email Analysis
- **POST** `/api/emails/analyze` - Analyze email for phishing
- **GET** `/api/emails/history` - Get email analysis history
- **GET** `/api/emails/<email_id>` - Get email details
- **GET** `/api/emails/statistics` - Get phishing detection statistics
- **POST** `/api/emails/<email_id>/mark-phishing` - Mark email as phishing
- **POST** `/api/emails/<email_id>/mark-safe` - Mark email as safe

### Health Check
- **GET** `/health` - API health status

## Example API Usage

### Analyze an Email
```bash
curl -X POST http://localhost:5000/api/emails/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "suspicious@example.com",
    "recipient": "user@company.com",
    "subject": "Urgent: Verify Your Account",
    "body": "Click here immediately to verify your account information..."
  }'
```

### Get Email History
```bash
curl http://localhost:5000/api/emails/history?limit=10&offset=0
```

### Get Statistics
```bash
curl http://localhost:5000/api/emails/statistics
```

## Features

### Phase 1: Completed ✓
- [x] Project setup and backend foundation
- [x] Database schema with SQLAlchemy
- [x] AI-powered phishing detection engine
- [x] Email analysis API endpoints
- [x] Basic threat identification

### Phase 2: Completed ✓
- [x] Advanced URL analysis
- [x] Content pattern recognition
- [x] Machine learning model training
- [x] Public training corpora integrated

### Phase 3: Completed ✓
- [x] React frontend dashboard
- [x] Email analyzer UI
- [x] Reports and analytics

## Detection Methods

The AI engine analyzes emails based on:

1. **Sender Analysis**
   - Email format validation
   - Domain spoofing detection
   - Suspicious pattern matching

2. **Subject Line Analysis**
   - Phishing keywords detection
   - Urgency indicators
   - Account-related threats

3. **Email Body Analysis**
   - Credential harvesting attempts
   - Suspicious phrases
   - Malware indicators

4. **URL Analysis**
   - IP address detection
   - URL shortener detection
   - Encoded characters

5. **Urgency Detection**
   - Social engineering tactics
   - Time-sensitive requests
   - Fake alerts

## Risk Score Calculation

The system calculates a composite risk score (0.0 - 1.0) by weighting multiple components:
- Sender score: 25%
- Subject score: 15%
- Body score: 25%
- URL score: 25%
- Urgency score: 10%

**Risk Categories:**
- **Low** (0.0 - 0.3): Email appears safe
- **Medium** (0.3 - 0.6): Caution recommended
- **High** (0.6 - 1.0): Likely phishing

## Database Models

### User
- Stores user account information
- Supports multiple roles (admin, analyst, user)

### Email
- Stores analyzed emails
- Risk scores and phishing flags
- Analysis details and audit trail

### ThreatAlert
- Documents identified threats
- Severity levels and descriptions

### AnalysisLog
- Audit trail of analyses and user actions

## Configuration

Edit `.env` file to configure:
```
FLASK_ENV=development
DATABASE_URL=sqlite:///phishing_db.db
SECRET_KEY=your-secret-key
DEBUG=True
```

For production, change:
```
FLASK_ENV=production
DEBUG=False
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues or questions, please open an issue on the project repository.
