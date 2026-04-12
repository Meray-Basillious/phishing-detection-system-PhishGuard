import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import EmailAnalyzer from './components/EmailAnalyzer';
import EmailHistory from './components/EmailHistory';
import ReportsAnalytics from './components/ReportsAnalytics';
import './styles/App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <header className="app-header">
          <div className="header-content">
            <div className="logo">
              <h1>🛡️ PhishGuard</h1>
              <p>Email Phishing Detection & Prevention System</p>
            </div>
            <nav className="nav-menu">
              <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📊 Dashboard
              </NavLink>
              <NavLink to="/analyzer" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                🔍 Analyze Email
              </NavLink>
              <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📈 History
              </NavLink>
              <NavLink to="/reports" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📋 Reports
              </NavLink>
            </nav>
          </div>
        </header>

        <main className="app-main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/analyzer" element={<EmailAnalyzer />} />
            <Route path="/history" element={<EmailHistory />} />
            <Route path="/reports" element={<ReportsAnalytics />} />
          </Routes>
        </main>

        <footer className="app-footer">
          <p>&copy; 2026 Email Phishing Detection System. All rights reserved.</p>
          <p>Powered by Advanced AI Detection Engine</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
