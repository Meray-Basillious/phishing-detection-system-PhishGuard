# Email Phishing Detection System - Frontend

A modern React-based dashboard for analyzing and managing phishing email threats.

## Features

### 🎯 Dashboard
- Real-time statistics on email analysis
- Phishing detection rates
- Threat distribution overview
- Average risk score tracking

### 🔍 Email Analyzer
- Input email details (from, to, subject, body)
- AI-powered phishing detection
- Risk score calculation
- Component-wise analysis
- Detailed threat identification
- Security recommendations

### 📈 Email History
- View all analyzed emails
- Filter by phishing status
- Detailed email inspection
- Mark emails as phishing or safe (user feedback)
- Threat information display

### 📋 Reports & Analytics
- Threat distribution charts
- Phase 2 model performance metrics
- Training source provenance
- Operational summary cards

## Installation

### Prerequisites
- Node.js (v14 or higher)
- npm or yarn
- Backend API running on `http://localhost:5000`

### Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start development server:
   ```bash
   npm start
   ```

The frontend will open at `http://localhost:3000`

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── Dashboard.jsx
│   │   ├── EmailAnalyzer.jsx
   │   ├── EmailHistory.jsx
   │   └── ReportsAnalytics.jsx
│   ├── services/
│   │   └── api.js
│   ├── styles/
│   │   ├── index.css
│   │   ├── App.css
│   │   ├── Dashboard.css
│   │   ├── EmailAnalyzer.css
   │   ├── EmailHistory.css
   │   └── ReportsAnalytics.css
│   ├── App.jsx
│   ├── index.js
│   └── ...
├── package.json
└── README.md
```

## API Integration

The frontend communicates with the backend API at:
- Base URL: `http://localhost:5000/api`

### Available API Endpoints

**Email Analysis**
- `POST /emails/analyze` - Analyze email
- `GET /emails/history` - Get email history
- `GET /emails/<id>` - Get email details
- `GET /emails/statistics` - Get statistics
- `GET /emails/phase2-metrics` - Get Phase 2 model metrics and training sources
- `POST /emails/<id>/mark-phishing` - Mark as phishing
- `POST /emails/<id>/mark-safe` - Mark as safe

## Styling

The application uses CSS Grid and Flexbox for responsive design with:
- Modern color scheme
- Smooth animations
- Mobile-optimized layouts
- Accessibility considerations

### Color Scheme
- Primary: `#2563eb` (Blue)
- Danger: `#dc2626` (Red)
- Success: `#16a34a` (Green)
- Warning: `#ea580c` (Orange)
- Info: `#0891b2` (Cyan)

## Building for Production

```bash
npm run build
```

This creates a production-ready build in the `build/` directory.

## Available Scripts

- `npm start` - Run development server
- `npm build` - Build for production
- `npm test` - Run tests
- `npm eject` - Eject configuration

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Performance Optimization

- Component lazy loading
- Chart optimization
- Smart API caching
- Request debouncing

## Security Features

- CORS-enabled API communication
- Secure headers
- Input validation
- XSS protection

## Contributing

Please follow the established code style and submit pull requests for any improvements.

## License

MIT - See LICENSE file for details
