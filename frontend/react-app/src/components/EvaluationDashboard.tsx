import type { BenchmarkEvaluationResult } from '../types';

type Props = {
  result: BenchmarkEvaluationResult | null;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  onRunEvaluation: () => void;
  loading: boolean;
};

const KPI_META: Array<{ key: keyof BenchmarkEvaluationResult['summary']['kpis']; label: string }> = [
  { key: 'review_time_reduction_percent', label: 'Review Time Reduction %' },
  { key: 'reviewer_confidence_percent', label: 'Reviewer Confidence %' },
  { key: 'anti_pattern_catch_rate_percent', label: 'Anti-pattern Catch %' },
  { key: 'critical_issue_recall_percent', label: 'Critical Issue Recall %' },
  { key: 'unsupported_claim_rate_percent', label: 'Unsupported Claim %' },
  { key: 'oracle_grounding_pass_rate_percent', label: 'Oracle Grounding Pass %' },
  { key: 'time_to_first_useful_output_seconds', label: 'TTFUO (s)' },
  { key: 'manual_judge_score', label: 'Manual Judge Score' },
];

export function EvaluationDashboard({ result, selectedCaseId, onSelectCase, onRunEvaluation, loading }: Props) {
  if (!result) {
    return (
      <div className="panel evaluation-panel">
        <div className="panel-header">
          <div className="panel-title">
            <div className="dot" />
            EVALUATION DASHBOARD
          </div>
        </div>
        <div style={{ padding: 24 }}>
          <div className="empty-state">
            <div className="icon">KPI</div>
            <p>
              Run the seeded benchmark suite to generate
              <br />
              KPI evidence, exports, and sample-level proof
            </p>
          </div>
          <button type="button" className={`analyze-btn ${loading ? 'loading' : ''}`} onClick={onRunEvaluation} disabled={loading}>
            <div className="spinner" />
            <span className="btn-text">{loading ? 'Running benchmark...' : 'Run KPI Benchmark'}</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="panel evaluation-panel">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" />
          EVALUATION DASHBOARD
        </div>
        <button type="button" className="secondary-btn" onClick={onRunEvaluation} disabled={loading}>
          {loading ? 'Running…' : 'Re-run Benchmark'}
        </button>
      </div>
      <div className="evaluation-body">
        <div className="metrics-row">
          {KPI_META.map(({ key, label }) => (
            <div key={String(key)} className="metric-chip cyan">
              <div className="value">{result.summary.kpis[key] as number | string}</div>
              <div className="label">{label}</div>
            </div>
          ))}
        </div>

        <div className="evaluation-grid">
          <div className="section-card">
            <h3>Benchmark Snapshot</h3>
            <p>Run ID: {result.runId}</p>
            <p>Generated: {new Date(result.generatedAt).toLocaleString()}</p>
            <p>Approved: {result.summary.approved}</p>
            <p>Flagged: {result.summary.flagged}</p>
            <p>Rejected: {result.summary.rejected}</p>
          </div>

          <div className="section-card">
            <h3>Exports</h3>
            <p>JSON: {result.exports.json_report}</p>
            <p>CSV: {result.exports.csv_report}</p>
            <p>Manifest: {result.exports.manifest}</p>
          </div>

          <div className="section-card">
            <h3>Artifact Breakdown</h3>
            <ul>
              {Object.entries(result.summary.artifact_type_breakdown).map(([artifact, data]) => (
                <li key={artifact}>
                  {artifact}: {data.approved}/{data.count} approved, avg time reduction {data.avg_review_time_reduction}%
                </li>
              ))}
            </ul>
          </div>

          <div className="section-card">
            <h3>Oracle Product Breakdown</h3>
            <ul>
              {Object.entries(result.summary.oracle_product_breakdown).map(([product, data]) => (
                <li key={product}>
                  {product}: {data.approved}/{data.count} approved, avg grounding {data.avg_grounding}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="section-card">
          <h3>Sample Evidence</h3>
          <div className="evaluation-sample-grid">
            {result.sampleResults.map((sample) => (
              <button
                key={sample.caseId}
                type="button"
                className={`batch-result-card ${selectedCaseId === sample.caseId ? 'active' : ''}`}
                onClick={() => onSelectCase(sample.caseId)}
              >
                <div className="batch-result-card-header">
                  <strong>{sample.analysisItem.label}</strong>
                  <span className={`status-pill ${sample.finalStatus}`}>{sample.finalStatus}</span>
                </div>
                <div className="batch-result-meta">
                  <span>{sample.artifactType}</span>
                  <span>{sample.oracleProduct}</span>
                </div>
                <div className="score-row">
                  <span>C {sample.judgeEvaluation.scores.completeness}</span>
                  <span>R {sample.judgeEvaluation.scores.correctness}</span>
                  <span>H {sample.judgeEvaluation.scores.hallucination}</span>
                  <span>G {sample.judgeEvaluation.validation.oracle_grounding}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
