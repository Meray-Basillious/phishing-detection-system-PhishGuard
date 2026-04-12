# PhishGuard - Email Phishing Detection System

An AI-powered email security solution combining machine learning and heuristic analysis to detect and prevent phishing attacks in real-time.

## 🎯 Quick Navigation

📁 **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Detailed file organization  
📚 **[docs/](docs/)** - Complete documentation and guides  
🚀 **Quick Start** - See below

## ⚡ Quick Start

### Backend (Flask API)
```bash
cd backend
python app.py
# Runs on http://127.0.0.1:5000
```

### Frontend (React UI)
```bash
cd frontend
npm install
npm start
# Runs on http://localhost:3000
```

## 📂 Directory Overview

- **`backend/`** - Flask API, ML models, detection engine
- **`frontend/`** - React web interface
- **`docs/`** - Consolidated documentation (7 files)
- **`tests/`** - Test scripts
- **`test_data/`** - Training dataset

👉 See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for complete details of every file and folder.

## 🔬 How It Works

**Detection combines:**
- Heuristic analysis (sender, keywords, domains, SSL)
- Machine learning (Random Forest for URLs, Logistic Regression for content)
- Risk scoring (0-100 scale with detailed breakdown)

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md#-phishing-detection-engine) for details.

## 📡 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/email/analyze` | Analyze email for phishing |
| GET | `/health` | Service health check |

See [docs/](docs/) for full API documentation.

## 🤖 ML Models

**In Use:**
- Random Forest (300 trees) - URL analysis
- Logistic Regression - Content analysis

**14 comparison models available** - See [docs/MODEL_COMPARISON_GUIDE.md](docs/MODEL_COMPARISON_GUIDE.md)

## 🛠️ Setup

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows: .\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Frontend
```bash
cd frontend
npm install
npm start
```

**See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** for complete setup instructions.

## 📊 Project Files

**Total Managed Files:** ~50 core project files

✅ **Organized for Clarity:**
- Backend logic and models
- React components
- Consolidated documentation (7 files in `/docs`)
- Test scripts (in `/tests`)
- Training data

**See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** for what each file does.

## 📚 Documentation

All documentation consolidated in `/docs/`:
- **INDEX.md** - Navigation guide
- **QUICK_REFERENCE.md** - 3-page quick guide
- **EXECUTIVE_SUMMARY.md** - Project overview
- **MODEL_COMPARISON_GUIDE.md** - 30+ page model analysis
- Plus implementation and framework guides

## 🔐 Configuration

Create `backend/.env`:
```env
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key
```

## 📝 License

MIT License

## 👥 Support

- 📖 Read [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- 📚 Check `/docs` for detailed guides
- 🔍 Review code comments in backend/services/
