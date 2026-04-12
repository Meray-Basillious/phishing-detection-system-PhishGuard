import React, { useEffect, useState } from 'react';
import { emailService } from '../services/api';
import '../styles/Dashboard.css';

const StatCard = ({ title, value, type, icon }) => {
  return (
    <div className={`stat-card stat-${type}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-content">
        <h3>{title}</h3>
        <p className="stat-value">{value}</p>
      </div>
    </div>
  );
};

const Dashboard = () => {
  const [stats, setStats] = useState({
    total_emails: 0,
    phishing_detected: 0,
    safe_emails: 0,
    average_risk_score: 0,
    phishing_percentage: 0,
    threat_distribution: {},
    phase2_metrics: {},
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStatistics();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchStatistics, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatistics = async () => {
    try {
      setLoading(true);
      const data = await emailService.getStatistics();
      setStats(data);
      setError(null);
    } catch (err) {
      setError('Failed to load statistics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !stats.total_emails) {
    return <div className="dashboard loading">Loading dashboard...</div>;
  }

  return (
    <div className="dashboard">
      <h1>Security Dashboard</h1>

      <div className="stats-grid">
        <StatCard
          title="Total Emails"
          value={stats.total_emails}
          type="info"
          icon="📧"
        />
        <StatCard
          title="Phishing Detected"
          value={stats.phishing_detected}
          type="danger"
          icon="⚠️"
        />
        <StatCard
          title="Safe Emails"
          value={stats.safe_emails}
          type="success"
          icon="✓"
        />
        <StatCard
          title="Avg Risk Score"
          value={stats.average_risk_score.toFixed(3)}
          type="warning"
          icon="📊"
        />
      </div>

      <div className="stats-container">
        <div className="stats-box">
          <h2>Threat Detection Rate</h2>
          <div className="score-display">
            <span className="percentage">{stats.phishing_percentage}%</span>
            <p>of emails identified as phishing</p>
          </div>
        </div>

        <div className="stats-box">
          <h2>Threat Types Distribution</h2>
          {Object.keys(stats.threat_distribution || {}).length > 0 ? (
            <div className="threat-list">
              {Object.entries(stats.threat_distribution).map(([threat, count]) => (
                <div key={threat} className="threat-item">
                  <span className="threat-name">{threat}</span>
                  <span className="threat-count">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="no-data">No threats detected yet</p>
          )}
        </div>
      </div>

      {stats.phase2_metrics?.content_metrics && stats.phase2_metrics?.url_metrics && (
        <div className="phase2-panel">
          <div className="phase2-header">
            <div>
              <h2>Phase 2 Model Performance</h2>
              <p>Public corpora and runtime model training results.</p>
            </div>
            <div className="phase2-status">Enabled</div>
          </div>

          <div className="stats-grid phase2-grid">
            <StatCard
              title="Content Model F1"
              value={stats.phase2_metrics.content_metrics.f1?.toFixed(4) ?? '0.0000'}
              type="info"
              icon="📝"
            />
            <StatCard
              title="URL Model F1"
              value={stats.phase2_metrics.url_metrics.f1?.toFixed(4) ?? '0.0000'}
              type="warning"
              icon="🔗"
            />
            <StatCard
              title="Content ROC AUC"
              value={stats.phase2_metrics.content_metrics.roc_auc?.toFixed(4) ?? '0.0000'}
              type="success"
              icon="📚"
            />
            <StatCard
              title="URL ROC AUC"
              value={stats.phase2_metrics.url_metrics.roc_auc?.toFixed(4) ?? '0.0000'}
              type="danger"
              icon="🧭"
            />
          </div>

          <div className="phase2-sources">
            <h3>Training Sources</h3>
            <div className="source-list">
              {(stats.phase2_metrics.data_sources || []).map((source) => (
                <div key={source.name} className="source-card">
                  <strong>{source.name}</strong>
                  <span>{source.purpose}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default Dashboard;
