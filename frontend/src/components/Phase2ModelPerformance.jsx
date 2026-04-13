import React, { useEffect, useMemo, useState } from 'react';
import { emailService } from '../services/api';
import '../styles/Phase2ModelPerformance.css';

const CURRENT_MODEL_HINTS = {
  url: ['random forest', 'random forest (original - 300 trees)'],
  content: ['logistic regression', 'logistic regression (saga)'],
};

const formatPercent = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${(Number(value) * 100).toFixed(2)}%`;
};

const formatSeconds = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toFixed(2)}s`;
};

const safeArray = (value) => (Array.isArray(value) ? value : []);

const normalizeMetrics = (list) =>
  safeArray(list)
    .filter((item) => item && item.status !== 'failed')
    .map((item) => ({
      model_name: item.model_name || 'Unknown Model',
      accuracy: Number(item.accuracy || 0),
      precision: Number(item.precision || 0),
      recall: Number(item.recall || 0),
      f1: Number(item.f1 || 0),
      roc_auc: Number(item.roc_auc || 0),
      training_time_seconds: Number(item.training_time_seconds || 0),
    }));

const matchesCurrentModel = (name, family) => {
  const normalized = String(name || '').toLowerCase();
  return (CURRENT_MODEL_HINTS[family] || []).some((hint) => normalized.includes(hint));
};

const buildFallbackCurrentModel = (family, metrics) => {
  const names = {
    url: 'Random Forest',
    content: 'Logistic Regression',
  };

  return {
    model_name: names[family],
    accuracy: Number(metrics?.accuracy || 0),
    precision: Number(metrics?.precision || 0),
    recall: Number(metrics?.recall || 0),
    f1: Number(metrics?.f1 || 0),
    roc_auc: Number(metrics?.roc_auc || 0),
    training_time_seconds: Number(metrics?.training_time_seconds || 0),
  };
};

const getCurrentModel = (models, family, fallbackMetrics) => {
  return (
    models.find((model) => matchesCurrentModel(model.model_name, family)) ||
    buildFallbackCurrentModel(family, fallbackMetrics)
  );
};

const getBestAlternative = (models, currentName) => {
  const alternatives = models.filter((m) => m.model_name !== currentName);
  if (!alternatives.length) return null;
  return [...alternatives].sort((a, b) => b.f1 - a.f1)[0];
};

const MetricBadge = ({ label, value }) => (
  <div className="p2-badge">
    <span className="p2-badge-label">{label}</span>
    <span className="p2-badge-value">{value}</span>
  </div>
);

const ModelComparisonCard = ({ title, currentModel, allModels }) => {
  const sortedModels = useMemo(() => [...allModels].sort((a, b) => b.f1 - a.f1), [allModels]);
  const bestAlternative = useMemo(
    () => getBestAlternative(sortedModels, currentModel?.model_name),
    [sortedModels, currentModel]
  );

  return (
    <section className="p2-card">
      <div className="p2-card-header">
        <div>
          <h3>{title}</h3>
          <p>
            Current model: <strong>{currentModel?.model_name || 'Unknown'}</strong>
          </p>
        </div>
        {bestAlternative && (
          <div className="p2-highlight">
            <span className="p2-highlight-label">Best alternative</span>
            <strong>{bestAlternative.model_name}</strong>
            <small>F1: {formatPercent(bestAlternative.f1)}</small>
          </div>
        )}
      </div>

      <div className="p2-current-grid">
        <MetricBadge label="Accuracy" value={formatPercent(currentModel?.accuracy)} />
        <MetricBadge label="Precision" value={formatPercent(currentModel?.precision)} />
        <MetricBadge label="Recall" value={formatPercent(currentModel?.recall)} />
        <MetricBadge label="F1 Score" value={formatPercent(currentModel?.f1)} />
        <MetricBadge label="ROC AUC" value={formatPercent(currentModel?.roc_auc)} />
        <MetricBadge label="Train Time" value={formatSeconds(currentModel?.training_time_seconds)} />
      </div>

      <div className="p2-table-wrap">
        <table className="p2-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Used</th>
              <th>Accuracy</th>
              <th>Precision</th>
              <th>Recall</th>
              <th>F1</th>
              <th>ROC AUC</th>
              <th>Train Time</th>
            </tr>
          </thead>
          <tbody>
            {sortedModels.map((model) => {
              const isCurrent = model.model_name === currentModel?.model_name;
              return (
                <tr key={`${title}-${model.model_name}`} className={isCurrent ? 'is-current' : ''}>
                  <td>{model.model_name}</td>
                  <td>
                    <span className={`p2-pill ${isCurrent ? 'active' : ''}`}>
                      {isCurrent ? 'Current' : 'Alt'}
                    </span>
                  </td>
                  <td>{formatPercent(model.accuracy)}</td>
                  <td>{formatPercent(model.precision)}</td>
                  <td>{formatPercent(model.recall)}</td>
                  <td>{formatPercent(model.f1)}</td>
                  <td>{formatPercent(model.roc_auc)}</td>
                  <td>{formatSeconds(model.training_time_seconds)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
};

const Phase2ModelPerformance = ({ phase2Metrics = {} }) => {
  const [comparisonData, setComparisonData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadComparison = async () => {
      try {
        const response = await emailService.getPhase2ModelComparison();
        setComparisonData(response);
      } catch (error) {
        console.error('Failed to load Phase 2 comparison', error);
      } finally {
        setLoading(false);
      }
    };

    loadComparison();
  }, []);

  const urlMetrics = phase2Metrics?.url_metrics || comparisonData?.url_metrics || {};
  const contentMetrics = phase2Metrics?.content_metrics || comparisonData?.content_metrics || {};

  const urlModels = normalizeMetrics(comparisonData?.comparison?.report?.url_models?.metrics || []);
  const contentModels = normalizeMetrics(comparisonData?.comparison?.report?.content_models?.metrics || []);

  const currentUrlModel = getCurrentModel(urlModels, 'url', urlMetrics);
  const currentContentModel = getCurrentModel(contentModels, 'content', contentMetrics);

  const trainedAt = comparisonData?.trained_at || phase2Metrics?.trained_at;
  const dataSources = phase2Metrics?.data_sources || [];

  return (
    <section className="p2-shell">
      <div className="p2-topbar">
        <div>
          <h2>Phase 2 Model Performance</h2>
          <p>
            Production models, benchmark metrics, and comparison against alternative models.
          </p>
        </div>
        {trainedAt && (
          <div className="p2-trained-at">
            <span>Last trained</span>
            <strong>{new Date(trainedAt).toLocaleString()}</strong>
          </div>
        )}
      </div>

      <div className="p2-summary">
        <div className="p2-summary-card">
          <span className="p2-summary-label">Production URL model</span>
          <strong>Random Forest</strong>
        </div>
        <div className="p2-summary-card">
          <span className="p2-summary-label">Production content model</span>
          <strong>Logistic Regression</strong>
        </div>
      </div>

      {loading ? (
        <div className="p2-loading">Loading model comparison…</div>
      ) : (
        <>
          <ModelComparisonCard
            title="URL Detection Models"
            currentModel={currentUrlModel}
            allModels={urlModels.length ? urlModels : [currentUrlModel]}
          />

          <ModelComparisonCard
            title="Content Detection Models"
            currentModel={currentContentModel}
            allModels={contentModels.length ? contentModels : [currentContentModel]}
          />
        </>
      )}

      {dataSources.length > 0 && (
        <div className="p2-sources">
          <h3>Training Sources</h3>
          <div className="p2-source-list">
            {dataSources.map((source) => (
              <div className="p2-source-item" key={`${source.name}-${source.source}`}>
                <strong>{source.name}</strong>
                <span>{source.purpose}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};

export default Phase2ModelPerformance;