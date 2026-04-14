import type { BenchmarkEvaluationResult } from '../types';

type Props = {
  result: BenchmarkEvaluationResult | null;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  onRunEvaluation: () => void;
  loading: boolean;
};

type ScoreCard = {
  label: string;
  value: string;
  tone: 'cyan' | 'purple' | 'green' | 'orange' | 'red';
  note: string;
};

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function formatSeconds(value: number): string {
  return `${value.toFixed(1)}s`;
}

function buildMetricCards(result: BenchmarkEvaluationResult): ScoreCard[] {
  const { kpis } = result.summary;
  return [
    {
      label: 'Grounded Accuracy',
      value: formatPercent(kpis.grounded_accuracy_percent),
      tone: 'green',
      note: 'Composite of support rate, unsupported rate, citation precision, and retrieval recall',
    },
    {
      label: 'Claim Support',
      value: formatPercent(kpis.claim_support_rate_percent ?? 0),
      tone: 'cyan',
      note: 'Expected claims recovered from evaluated outputs',
    },
    {
      label: 'Unsupported Rate',
      value: formatPercent(kpis.unsupported_claim_rate_percent),
      tone: 'red',
      note: 'Claims marked unsupported or forbidden by the benchmark rules',
    },
    {
      label: 'Recall@K',
      value: formatPercent(kpis.recall_at_k_percent ?? 0),
      tone: 'purple',
      note: 'Retrieval coverage against gold qrels',
    },
    {
      label: 'MRR',
      value: formatPercent(kpis.mrr_percent ?? 0),
      tone: 'orange',
      note: 'Rank quality for the first relevant supporting chunk',
    },
    {
      label: 'Workflow Success',
      value: formatPercent(kpis.workflow_success_rate_percent),
      tone: 'green',
      note: 'Cases that completed without degrading to a rejected output',
    },
  ];
}

export function EvaluationDashboard({ result, onRunEvaluation, loading }: Props) {
  if (!result) {
    return (
      <div className="panel evaluation-panel">
        <div className="panel-header">
          <div className="panel-title">
            <div className="dot" />
            KPI SCORECARD
          </div>
        </div>
        <div style={{ padding: 24 }}>
          <div className="empty-state">
            <div className="icon">📊</div>
            <p>
              Run the benchmark suite to generate
              <br />
              grounded benchmark metrics
            </p>
          </div>
          <button type="button" className={`analyze-btn ${loading ? 'loading' : ''}`} onClick={onRunEvaluation} disabled={loading}>
            <div className="spinner" />
            <span className="btn-text">{loading ? 'Running benchmark...' : 'Generate KPI Scorecard'}</span>
          </button>
        </div>
      </div>
    );
  }

  const metricCards = buildMetricCards(result);

  return (
    <div className="panel evaluation-panel">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" />
          KPI SCORECARD
        </div>
        <button type="button" className="secondary-btn" onClick={onRunEvaluation} disabled={loading}>
          {loading ? 'Running...' : 'Re run Benchmark'}
        </button>
      </div>
      <div className="evaluation-body">
        <div className="section-card benchmark-hero-card">
          <div className="benchmark-hero-topline">Benchmark Truth View</div>
          <h3>Only backend-computed metrics are shown here</h3>
          <p>This dashboard reports retrieval, grounding, unsupported-claim rate, and workflow outcomes directly from the benchmark runner.</p>
        </div>

        <div className="section-card">
          <h3>Run Metrics</h3>
          <div className="metrics-row">
            {metricCards.map((card) => (
              <div key={card.label} className={`metric-chip ${card.tone}`}>
                <div className="value">{card.value}</div>
                <div className="label">{card.label}</div>
                <div className="metric-note">{card.note}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="evaluation-grid">
          <div className="section-card">
            <h3>Benchmark Snapshot</h3>
            <p>Run ID: {result.runId}</p>
            <p>Generated: {new Date(result.generatedAt).toLocaleString()}</p>
            <p>Total samples: {result.summary.total_cases}</p>
            <p>Approved: {result.summary.approved}</p>
            <p>Flagged: {result.summary.flagged}</p>
            <p>Rejected: {result.summary.rejected}</p>
            <p>p95 latency: {formatSeconds(result.summary.kpis.p95_latency_seconds)}</p>
          </div>

          <div className="section-card">
            <h3>Exports</h3>
            <p>JSON: {result.exports.json_report}</p>
            <p>CSV: {result.exports.csv_report}</p>
            <p>Manifest: {result.exports.manifest}</p>
          </div>

          <div className="section-card">
            <h3>Artifact Coverage</h3>
            <ul>
              {Object.entries(result.summary.artifact_type_breakdown).map(([artifact, data]) => (
                <li key={artifact}>
                  {artifact}: {data.count} sample{data.count === 1 ? '' : 's'} with {data.avg_grounded_accuracy}% average grounded accuracy
                </li>
              ))}
            </ul>
          </div>

          <div className="section-card">
            <h3>Oracle Coverage</h3>
            <ul>
              {Object.entries(result.summary.oracle_product_breakdown).map(([product, data]) => (
                <li key={product}>
                  {product}: {data.count} sample{data.count === 1 ? '' : 's'} with {data.avg_grounded_accuracy}% average grounded accuracy
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
