import React, { useState } from 'react';
import { emailService } from '../services/api';
import '../styles/EmailAnalyzer.css';

const EmailAnalyzer = () => {
  const [formData, setFormData] = useState({
    sender: '',
    recipient: '',
    subject: '',
    body: '',
  });

  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    
    if (!formData.sender || !formData.recipient || !formData.subject || !formData.body) {
      setError('Please fill in all fields');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await emailService.analyzeEmail(formData);
      setAnalysis(result);
    } catch (err) {
      setError('Failed to analyze email. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (score) => {
    if (score > 0.7) return '#ff4444';
    if (score > 0.5) return '#ffaa00';
    if (score > 0.3) return '#ffdd00';
    return '#00aa00';
  };

  const getRiskLevel = (score) => {
    if (score > 0.7) return 'CRITICAL';
    if (score > 0.5) return 'HIGH';
    if (score > 0.3) return 'MEDIUM';
    return 'LOW';
  };

  const getVerdict = () => {
    if (!analysis?.analysis) {
      return 'safe';
    }

    return analysis.analysis.verdict || (analysis.analysis.is_phishing ? 'phishing' : 'safe');
  };

  const getVerdictClass = (verdict) => {
    if (verdict === 'phishing') return 'status-danger';
    if (verdict === 'suspicious') return 'status-warning';
    return 'status-safe';
  };

  const getVerdictLabel = (verdict) => {
    if (verdict === 'phishing') return 'PHISHING DETECTED';
    if (verdict === 'suspicious') return 'SUSPICIOUS - REVIEW REQUIRED';
    return 'EMAIL APPEARS SAFE';
  };

  const mlScores = analysis?.analysis?.ml_scores || {};
  const phase2Enabled = analysis?.analysis?.phase2_models_enabled;

  const handleReset = () => {
    setFormData({
      sender: '',
      recipient: '',
      subject: '',
      body: '',
    });
    setAnalysis(null);
    setError(null);
  };

  return (
    <div className="email-analyzer">
      <h1>Email Analyzer</h1>

      <form onSubmit={handleAnalyze} className="analyzer-form">
        <div className="form-section">
          <h2>Email Details</h2>
          
          <div className="form-group">
            <label htmlFor="sender">From (Sender Email)</label>
            <input
              type="email"
              id="sender"
              name="sender"
              value={formData.sender}
              onChange={handleInputChange}
              placeholder="sender@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="recipient">To (Recipient Email)</label>
            <input
              type="email"
              id="recipient"
              name="recipient"
              value={formData.recipient}
              onChange={handleInputChange}
              placeholder="recipient@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="subject">Subject Line</label>
            <input
              type="text"
              id="subject"
              name="subject"
              value={formData.subject}
              onChange={handleInputChange}
              placeholder="Enter email subject"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="body">Email Body</label>
            <textarea
              id="body"
              name="body"
              value={formData.body}
              onChange={handleInputChange}
              placeholder="Enter email body content"
              rows="8"
              required
            />
          </div>

          <div className="form-buttons">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Analyzing...' : '🔍 Analyze Email'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={handleReset}>
              Clear Form
            </button>
          </div>
        </div>
      </form>

      {error && <div className="error-message">{error}</div>}

      {analysis && (
        <div className="analysis-results">
          <h2>Analysis Results</h2>

          {(() => {
            const verdict = getVerdict();
            return (
              <>

          <div className="risk-summary">
            <div className="risk-score-box" style={{ borderColor: getRiskColor(analysis.analysis.overall_risk_score) }}>
              <div className="risk-label">Risk Score</div>
              <div className="risk-score">{(analysis.analysis.overall_risk_score * 100).toFixed(1)}%</div>
              <div className="risk-level" style={{ color: getRiskColor(analysis.analysis.overall_risk_score) }}>
                {getRiskLevel(analysis.analysis.overall_risk_score)}
              </div>
            </div>

            <div className="threat-info">
              <div className="threat-status">
                <span className={getVerdictClass(verdict)}>
                  {verdict === 'phishing' ? '🚨 ' : verdict === 'suspicious' ? '⚠ ' : '✓ '}
                  {getVerdictLabel(verdict)}
                </span>
              </div>
              <div className="confidence">
                <p>Confidence: <strong>{analysis.analysis.confidence.toUpperCase()}</strong></p>
                <p>Verdict: <strong>{verdict.toUpperCase()}</strong></p>
              </div>
            </div>
          </div>

          <div className="component-scores">
            <h3>Component Analysis</h3>
            <div className="scores-grid">
              {Object.entries(analysis.analysis.component_scores).map(([component, score]) => (
                <div key={component} className="score-item">
                  <span className="component-name">
                    {component.replace('_', ' ').toUpperCase()}
                  </span>
                  <div className="score-bar">
                    <div
                      className="score-fill"
                      style={{
                        width: `${score * 100}%`,
                        backgroundColor: getRiskColor(score),
                      }}
                    />
                  </div>
                  <span className="score-value">{(score * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="ml-results">
            <h3>Phase 2 Model Signals</h3>
            <div className="ml-grid">
              <div className="ml-card">
                <span className="ml-label">Content Model Score</span>
                <strong>{((mlScores.content_score || 0) * 100).toFixed(1)}%</strong>
              </div>
              <div className="ml-card">
                <span className="ml-label">URL Model Score</span>
                <strong>{((mlScores.url_score || 0) * 100).toFixed(1)}%</strong>
              </div>
              <div className="ml-card">
                <span className="ml-label">Phase 2 Enabled</span>
                <strong>{phase2Enabled ? 'Yes' : 'No'}</strong>
              </div>
            </div>
          </div>

          <div className="threats-recommendations">
            <div className="threats-section">
              <h3>🎯 Detected Threats</h3>
              <ul className="threat-list">
                {analysis.analysis.threats.map((threat, idx) => (
                  <li key={idx} className="threat-item">
                    {threat}
                  </li>
                ))}
              </ul>
            </div>

            <div className="recommendations-section">
              <h3>💡 Recommendations</h3>
              <ul className="recommendations-list">
                {analysis.analysis.recommendations.map((rec, idx) => (
                  <li key={idx} className="recommendation-item">
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {analysis.email_id && (
            <div className="email-id">
              <p>Email ID: <code>{analysis.email_id}</code></p>
            </div>
          )}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
};

export default EmailAnalyzer;
