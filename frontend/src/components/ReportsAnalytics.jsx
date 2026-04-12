import React, { useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';
import { emailService } from '../services/api';
import '../styles/ReportsAnalytics.css';

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const ReportsAnalytics = () => {
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      setLoading(true);
      const [statistics, phase2Metrics] = await Promise.all([
        emailService.getStatistics(),
        emailService.getPhase2Metrics(),
      ]);

      setReportData({
        statistics,
        phase2Metrics,
      });
      setError(null);
    } catch (err) {
      setError('Failed to load reports');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="reports-page loading">Loading reports...</div>;
  }

  if (error) {
    return <div className="reports-page error-message">{error}</div>;
  }

  const statistics = reportData?.statistics || {};
  const phase2Metrics = reportData?.phase2Metrics || {};
  const contentMetrics = phase2Metrics?.content_metrics || {};
  const urlMetrics = phase2Metrics?.url_metrics || {};
  const threatEntries = Object.entries(statistics.threat_distribution || {});

  const threatChartData = {
    labels: threatEntries.length > 0 ? threatEntries.map(([label]) => label) : ['No threats'],
    datasets: [{
      data: threatEntries.length > 0 ? threatEntries.map(([, value]) => value) : [1],
      backgroundColor: ['#2563eb', '#dc2626', '#ea580c', '#16a34a', '#0f766e', '#7c3aed'],
      borderWidth: 0,
    }],
  };

  const modelChartData = {
    labels: ['Accuracy', 'Precision', 'Recall', 'F1', 'ROC AUC'],
    datasets: [
      {
        label: 'Content Model',
        data: [
          contentMetrics.accuracy || 0,
          contentMetrics.precision || 0,
          contentMetrics.recall || 0,
          contentMetrics.f1 || 0,
          contentMetrics.roc_auc || 0,
        ],
        backgroundColor: 'rgba(37, 99, 235, 0.75)',
      },
      {
        label: 'URL Model',
        data: [
          urlMetrics.accuracy || 0,
          urlMetrics.precision || 0,
          urlMetrics.recall || 0,
          urlMetrics.f1 || 0,
          urlMetrics.roc_auc || 0,
        ],
        backgroundColor: 'rgba(234, 88, 12, 0.75)',
      },
    ],
  };

  const sourceCards = phase2Metrics?.data_sources || [];

  return (
    <div className="reports-page">
      <div className="reports-hero">
        <h1>Reports & Analytics</h1>
        <p>Operational view of detection trends, model quality, and training provenance.</p>
      </div>

      <div className="reports-layout">
        <div className="report-card summary-card">
          <h2>Detection Summary</h2>
          <div className="report-stats">
            <div>
              <span>Total Emails</span>
              <strong>{statistics.total_emails || 0}</strong>
            </div>
            <div>
              <span>Phishing</span>
              <strong>{statistics.phishing_detected || 0}</strong>
            </div>
            <div>
              <span>Average Risk</span>
              <strong>{(statistics.average_risk_score || 0).toFixed(3)}</strong>
            </div>
            <div>
              <span>Detection Rate</span>
              <strong>{statistics.phishing_percentage || 0}%</strong>
            </div>
          </div>
        </div>

        <div className="reports-grid reports-grid-two">
          <div className="report-card chart-card">
            <h2>Threat Distribution</h2>
            <div className="chart-shell chart-shell-sm">
              <Doughnut
                data={threatChartData}
                options={{ responsive: true, maintainAspectRatio: false, cutout: '64%' }}
              />
            </div>
          </div>

          <div className="report-card chart-card">
            <h2>Phase 2 Metrics</h2>
            <div className="metric-list compact-metrics">
              <div className="metric-row"><span>Content F1</span><strong>{(contentMetrics.f1 || 0).toFixed(4)}</strong></div>
              <div className="metric-row"><span>Content ROC AUC</span><strong>{(contentMetrics.roc_auc || 0).toFixed(4)}</strong></div>
              <div className="metric-row"><span>URL F1</span><strong>{(urlMetrics.f1 || 0).toFixed(4)}</strong></div>
              <div className="metric-row"><span>URL ROC AUC</span><strong>{(urlMetrics.roc_auc || 0).toFixed(4)}</strong></div>
              <div className="metric-row"><span>Trained At</span><strong>{phase2Metrics.trained_at ? new Date(phase2Metrics.trained_at).toLocaleString() : 'Unknown'}</strong></div>
            </div>
          </div>

          <div className="report-card chart-card wide-card">
            <h2>Phase 2 Model Quality</h2>
            <div className="chart-shell chart-shell-lg">
              <Bar
                data={modelChartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  scales: { y: { min: 0, max: 1 } },
                }}
              />
            </div>
          </div>

          <div className="report-card wide-card source-card-panel">
            <h2>Training Sources</h2>
            <div className="source-grid">
              {sourceCards.map((source) => (
                <div className="source-card" key={source.name}>
                  <strong>{source.name}</strong>
                  <span>{source.purpose}</span>
                  <small>{source.source}</small>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportsAnalytics;