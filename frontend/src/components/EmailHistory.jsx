import React, { useState, useEffect, useCallback } from 'react';
import { emailService } from '../services/api';
import '../styles/EmailHistory.css';

const EmailHistory = () => {
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [selectedEmail, setSelectedEmail] = useState(null);

  const fetchEmailHistory = useCallback(async () => {
    try {
      setLoading(true);
      const isPhishing = filter === 'all' ? null : filter === 'phishing';
      const data = await emailService.getEmailHistory(50, 0, isPhishing);
      setEmails(data.emails || []);
      setError(null);
    } catch (err) {
      setError('Failed to load email history');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchEmailHistory();
  }, [fetchEmailHistory]);

  const handleViewDetails = async (emailId) => {
    try {
      const details = await emailService.getEmailDetails(emailId);
      setSelectedEmail(details);
    } catch (err) {
      setError('Failed to load email details');
    }
  };

  const handleMarkPhishing = async (emailId) => {
    try {
      await emailService.markAsPhishing(emailId);
      fetchEmailHistory();
    } catch (err) {
      setError('Failed to update email');
    }
  };

  const handleMarkSafe = async (emailId) => {
    try {
      await emailService.markAsSafe(emailId);
      fetchEmailHistory();
    } catch (err) {
      setError('Failed to update email');
    }
  };

  const getRiskColor = (score) => {
    if (score > 0.7) return '#ff4444';
    if (score > 0.5) return '#ffaa00';
    if (score > 0.3) return '#ffdd00';
    return '#00aa00';
  };

  if (selectedEmail) {
    return (
      <div className="email-history">
        <button className="btn btn-back" onClick={() => setSelectedEmail(null)}>
          ← Back to History
        </button>

        <div className="email-details">
          <h2>Email Details</h2>
          
          <div className="detail-section">
            <h3>Email Information</h3>
            <div className="detail-row">
              <span className="label">From:</span>
              <span className="value">{selectedEmail.sender}</span>
            </div>
            <div className="detail-row">
              <span className="label">To:</span>
              <span className="value">{selectedEmail.recipient}</span>
            </div>
            <div className="detail-row">
              <span className="label">Subject:</span>
              <span className="value">{selectedEmail.subject}</span>
            </div>
          </div>

          <div className="detail-section">
            <h3>Analysis Results</h3>
            <div className="detail-row">
              <span className="label">Risk Score:</span>
              <span
                className="value"
                style={{ color: getRiskColor(selectedEmail.risk_score) }}
              >
                {(selectedEmail.risk_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="detail-row">
              <span className="label">Status:</span>
              <span className={`status ${selectedEmail.is_phishing ? 'danger' : 'success'}`}>
                {selectedEmail.is_phishing ? '⚠️ PHISHING' : '✓ SAFE'}
              </span>
            </div>
          </div>

          {selectedEmail.threats && selectedEmail.threats.length > 0 && (
            <div className="detail-section">
              <h3>Detected Threats</h3>
              <ul className="threat-list">
                {selectedEmail.threats.map((threat, idx) => (
                  <li key={idx} className="threat-item">
                    <strong>{threat.type}</strong> - {threat.severity}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="detail-section">
            <h3>Email Body</h3>
            <div className="email-body">{selectedEmail.body}</div>
          </div>

          <div className="action-buttons">
            <button
              className="btn btn-warning"
              onClick={() => handleMarkPhishing(selectedEmail.id)}
            >
              Mark as Phishing
            </button>
            <button
              className="btn btn-success"
              onClick={() => handleMarkSafe(selectedEmail.id)}
            >
              Mark as Safe
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="email-history">
      <h1>Email Analysis History</h1>

      <div className="filter-section">
        <label htmlFor="filter">Filter:</label>
        <select
          id="filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All Emails</option>
          <option value="phishing">Phishing Only</option>
          <option value="safe">Safe Only</option>
        </select>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="loading">Loading email history...</div>
      ) : emails.length === 0 ? (
        <div className="no-data">No emails found</div>
      ) : (
        <div className="email-table">
          <div className="table-header">
            <div className="col col-status">Status</div>
            <div className="col col-from">From</div>
            <div className="col col-subject">Subject</div>
            <div className="col col-risk">Risk Score</div>
            <div className="col col-threats">Threats</div>
            <div className="col col-actions">Actions</div>
          </div>

          {emails.map((email) => (
            <div key={email.id} className="table-row">
              <div className="col col-status">
                <span className={email.is_phishing ? 'badge-danger' : 'badge-success'}>
                  {email.is_phishing ? '⚠️' : '✓'}
                </span>
              </div>
              <div className="col col-from">{email.sender}</div>
              <div className="col col-subject">{email.subject}</div>
              <div className="col col-risk">
                <span style={{ color: getRiskColor(email.risk_score) }}>
                  {(email.risk_score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="col col-threats">{email.threat_count}</div>
              <div className="col col-actions">
                <button
                  className="btn btn-small"
                  onClick={() => handleViewDetails(email.id)}
                >
                  View Details
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EmailHistory;
