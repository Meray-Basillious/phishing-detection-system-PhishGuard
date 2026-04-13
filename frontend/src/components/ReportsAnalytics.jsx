import React, { useEffect, useMemo, useState } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
import { emailService } from '../services/api';
import '../styles/ReportsAnalytics.css';

ChartJS.register(ArcElement, Tooltip, Legend);

const ReportsAnalytics = () => {
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        setLoading(true);
        const data = await emailService.getStatistics();
        setStatistics(data);
        setError(null);
      } catch (err) {
        setError('Failed to load reports');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchReports();
  }, []);

  const threatEntries = Object.entries(statistics?.threat_distribution || {});
  const totalThreats = threatEntries.reduce((sum, [, value]) => sum + value, 0);

  const threatChartData = useMemo(() => {
    const hasThreats = threatEntries.length > 0;

    return {
      labels: hasThreats ? threatEntries.map(([label]) => label) : ['No threats'],
      datasets: [
        {
          data: hasThreats ? threatEntries.map(([, value]) => value) : [1],
          backgroundColor: hasThreats
            ? ['#2563eb', '#dc2626', '#ea580c', '#16a34a', '#0f766e', '#7c3aed']
            : ['#cbd5e1'],
          borderWidth: 0,
          hoverOffset: 8,
        },
      ],
    };
  }, [threatEntries]);

  const threatChartOptions = useMemo(() => {
    return {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '58%',
      layout: {
        padding: 8,
      },
      plugins: {
        legend: {
          position: 'right',
          align: 'center',
          labels: {
            usePointStyle: true,
            pointStyle: 'circle',
            boxWidth: 10,
            boxHeight: 10,
            padding: 18,
            font: {
              size: 12,
            },
          },
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              const label = context.label || '';
              const value = context.parsed || 0;
              const total = context.dataset.data.reduce((sum, item) => sum + item, 0);
              const percentage = total ? ((value / total) * 100).toFixed(1) : '0.0';
              return `${label}: ${value} (${percentage}%)`;
            },
          },
        },
      },
    };
  }, []);

  if (loading) {
    return <div className="reports-loading">Loading reports...</div>;
  }

  if (error) {
    return <div className="reports-error">{error}</div>;
  }

  return (
    <div className="reports-page">
      <div className="reports-header">
        <h1>Reports & Analytics</h1>
        <p>Operational view of detection trends and threat distribution.</p>
      </div>

      <div className="reports-stats-grid">
        <div className="reports-stat-card">
          <span className="reports-stat-label">Total Emails</span>
          <strong>{statistics?.total_emails || 0}</strong>
        </div>

        <div className="reports-stat-card">
          <span className="reports-stat-label">Phishing</span>
          <strong>{statistics?.phishing_detected || 0}</strong>
        </div>

        <div className="reports-stat-card">
          <span className="reports-stat-label">Average Risk</span>
          <strong>{(statistics?.average_risk_score || 0).toFixed(3)}</strong>
        </div>

        <div className="reports-stat-card">
          <span className="reports-stat-label">Detection Rate</span>
          <strong>{statistics?.phishing_percentage || 0}%</strong>
        </div>
      </div>

      <section className="reports-threat-panel">
        <div className="reports-threat-header">
          <div>
            <h2>Threat Distribution</h2>
            <p>Breakdown of detected threat categories across analyzed emails.</p>
          </div>
          <div className="reports-threat-total">
            <span>Total Threat Alerts</span>
            <strong>{totalThreats}</strong>
          </div>
        </div>

        <div className="reports-threat-chart-wrap">
          <div className="reports-threat-chart">
            <Doughnut data={threatChartData} options={threatChartOptions} />
          </div>
        </div>
      </section>
    </div>
  );
};

export default ReportsAnalytics;