import React, { useMemo, useState } from 'react';
import { emailService } from '../services/api';
import '../styles/EmailAnalyzer.css';

const VISIBLE_COMPONENTS = [
  { key: 'sender_score', label: 'Sender Trust' },
  { key: 'subject_score', label: 'Subject Risk' },
  { key: 'body_score', label: 'Message Content' },
  { key: 'url_score', label: 'Links & URLs' },
  { key: 'urgency_score', label: 'Urgency Pressure' },
  { key: 'impersonation_score', label: 'Impersonation Risk' },
];

const hasRealScores = (obj) => {
  if (!obj || typeof obj !== 'object') return false;
  const keys = Object.keys(obj);
  if (!keys.length) return false;
  return keys.some((key) => {
    const value = Number(obj[key]);
    return !Number.isNaN(value) && value > 0;
  });
};

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
    setFormData((prev) => ({
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
      console.log('Analyzer response:', result);
      setAnalysis(result);
    } catch (err) {
      setError('Failed to analyze email. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

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

  const analysisData = analysis?.analysis || {};
  const geminiAnalysis = analysisData?.gemini_analysis || {};

  const geminiScores =
    geminiAnalysis?.available && hasRealScores(geminiAnalysis?.final_component_scores)
      ? geminiAnalysis.final_component_scores
      : null;

  const backendFinalScores =
    hasRealScores(analysisData?.component_scores)
      ? analysisData.component_scores
      : null;

  const finalComponentScores = geminiScores || backendFinalScores || {};

  const finalRiskScore =
    typeof analysisData?.overall_risk_score === 'number'
      ? analysisData.overall_risk_score
      : typeof analysisData?.hybrid_score === 'number'
        ? analysisData.hybrid_score
        : typeof geminiAnalysis?.final_overall_risk_score === 'number'
          ? geminiAnalysis.final_overall_risk_score
          : 0;

  const finalVerdict =
    analysisData?.verdict ||
    analysisData?.hybrid_verdict ||
    geminiAnalysis?.final_verdict ||
    (analysisData?.is_phishing ? 'phishing' : 'safe');

  const finalConfidence =
    analysisData?.confidence ||
    geminiAnalysis?.confidence ||
    'low';

  const displayedScores = useMemo(() => {
    return VISIBLE_COMPONENTS.map((item) => ({
      ...item,
      value: Number(finalComponentScores?.[item.key] ?? 0),
    }));
  }, [finalComponentScores]);

  const geminiReasoning =
    geminiAnalysis?.reasoning_summary ||
    analysisData?.hybrid_explanation ||
    '';

  const recommendedAction =
    geminiAnalysis?.recommended_action ||
    (Array.isArray(analysisData?.recommendations)
      ? analysisData.recommendations.join(' ')
      : '');

  const threatTypes =
    geminiAnalysis?.threat_types?.length
      ? geminiAnalysis.threat_types
      : analysisData?.threats || [];

  const socialTactics =
    geminiAnalysis?.social_engineering_tactics || [];

  const getRiskColor = (score) => {
    if (score > 0.75) return '#dc2626';
    if (score > 0.5) return '#ea580c';
    if (score > 0.3) return '#ca8a04';
    return '#16a34a';
  };

  const getRiskLevel = (score) => {
    if (score > 0.75) return 'CRITICAL';
    if (score > 0.5) return 'HIGH';
    if (score > 0.3) return 'MEDIUM';
    return 'LOW';
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

  const scoreSourceLabel = geminiScores
    ? 'Gemini final judgement'
    : backendFinalScores
      ? 'Backend final scores'
      : 'No score source available';

  return (
    <div className="email-analyzer">
      <h1>Email Analyzer</h1>

      <form className="analyzer-form" onSubmit={handleAnalyze}>
        <div className="form-section">
          <h2>Email Details</h2>

          <div className="form-group">
            <label htmlFor="sender">From (Sender Email)</label>
            <input
              id="sender"
              name="sender"
              type="email"
              value={formData.sender}
              onChange={handleInputChange}
              placeholder="sender@example.com"
            />
          </div>

          <div className="form-group">
            <label htmlFor="recipient">To (Recipient Email)</label>
            <input
              id="recipient"
              name="recipient"
              type="email"
              value={formData.recipient}
              onChange={handleInputChange}
              placeholder="recipient@example.com"
            />
          </div>

          <div className="form-group">
            <label htmlFor="subject">Subject Line</label>
            <input
              id="subject"
              name="subject"
              type="text"
              value={formData.subject}
              onChange={handleInputChange}
              placeholder="Enter the email subject"
            />
          </div>

          <div className="form-group">
            <label htmlFor="body">Email Body</label>
            <textarea
              id="body"
              name="body"
              rows="10"
              value={formData.body}
              onChange={handleInputChange}
              placeholder="Paste the email body here"
            />
          </div>

          <div className="form-buttons">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Analyzing...' : 'Analyze Email'}
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

          <div className="risk-summary">
            <div
              className="risk-score-box"
              style={{ borderColor: getRiskColor(finalRiskScore) }}
            >
              <div className="risk-label">Final Risk Score</div>
              <div className="risk-score">{(finalRiskScore * 100).toFixed(1)}%</div>
              <div
                className="risk-level"
                style={{ color: getRiskColor(finalRiskScore) }}
              >
                {getRiskLevel(finalRiskScore)}
              </div>
              <div className="risk-source">
                Score source: <strong>{scoreSourceLabel}</strong>
              </div>
            </div>

            <div className="threat-info">
              <div className="threat-status">
                <span className={getVerdictClass(finalVerdict)}>
                  {finalVerdict === 'phishing'
                    ? '🚨 '
                    : finalVerdict === 'suspicious'
                      ? '⚠️ '
                      : '✅ '}
                  {getVerdictLabel(finalVerdict)}
                </span>
              </div>
              <div className="confidence">
                <p>
                  Confidence: <strong>{String(finalConfidence).toUpperCase()}</strong>
                </p>
                <p>
                  Verdict: <strong>{String(finalVerdict).toUpperCase()}</strong>
                </p>
                <p>
                  Gemini Used:{' '}
                  <strong>{analysisData?.gemini_used ? 'Yes' : 'No'}</strong>
                </p>
              </div>
            </div>
          </div>

          <div className="component-scores">
            <div className="section-header">
              <div>
                <h3>Final Component Analysis</h3>
                <p>
                  Showing only the unique final decision factors.
                </p>
              </div>
            </div>

            <div className="scores-grid compact">
              {displayedScores.map(({ key, label, value }) => (
                <div key={key} className="score-item clean">
                  <div className="score-topline">
                    <span className="component-name">{label}</span>
                    <span className="score-value">{(value * 100).toFixed(1)}%</span>
                  </div>
                  <div className="score-bar">
                    <div
                      className="score-fill"
                      style={{
                        width: `${Math.max(0, Math.min(100, value * 100))}%`,
                        backgroundColor: getRiskColor(value),
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {(geminiReasoning || recommendedAction || socialTactics.length > 0) && (
            <div className="gemini-judgement-panel">
              <h3>Gemini Final Judgement</h3>

              {geminiReasoning && (
                <div className="judgement-block">
                  <span className="judgement-label">Why Gemini decided this</span>
                  <p>{geminiReasoning}</p>
                </div>
              )}

              {socialTactics.length > 0 && (
                <div className="judgement-block">
                  <span className="judgement-label">Detected Tactics</span>
                  <div className="tag-list">
                    {socialTactics.map((tactic, idx) => (
                      <span className="tag" key={`${tactic}-${idx}`}>
                        {tactic}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {recommendedAction && (
                <div className="judgement-block">
                  <span className="judgement-label">Recommended Action</span>
                  <p>{recommendedAction}</p>
                </div>
              )}

              {analysisData?.gemini_analysis?.error && (
                <div className="judgement-block">
                  <span className="judgement-label">Gemini Error</span>
                  <p>{analysisData.gemini_analysis.error}</p>
                </div>
              )}
            </div>
          )}

          <div className="threats-recommendations single-column">
            <div className="threats-section">
              <h3>Detected Threat Types</h3>
              <ul className="threat-list">
                {threatTypes.length > 0 ? (
                  threatTypes.map((threat, idx) => (
                    <li key={idx} className="threat-item">
                      {threat}
                    </li>
                  ))
                ) : (
                  <li className="threat-item">No immediate threats detected</li>
                )}
              </ul>
            </div>
          </div>

          {analysis.email_id && (
            <div className="email-id">
              <p>
                Email ID: <code>{analysis.email_id}</code>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EmailAnalyzer;