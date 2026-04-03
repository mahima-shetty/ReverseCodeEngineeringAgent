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

function average(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function buildOutcomeCards(result: BenchmarkEvaluationResult): ScoreCard[] {
  const { kpis } = result.summary;
  const trustScore = average([
    kpis.reviewer_confidence_percent,
    kpis.oracle_grounding_pass_rate_percent,
    Math.max(0, 100 - kpis.unsupported_claim_rate_percent),
  ]);

  return [
    {
      label: 'Review Speed Gain',
      value: formatPercent(kpis.review_time_reduction_percent),
      tone: 'cyan',
      note: 'How much manual review time the system saves',
    },
    {
      label: 'First Useful Answer',
      value: formatSeconds(kpis.time_to_first_useful_output_seconds),
      tone: 'purple',
      note: 'Time until the first actionable output appears',
    },
    {
      label: 'Review Quality',
      value: formatPercent(kpis.critical_issue_recall_percent),
      tone: 'orange',
      note: 'How often important issues are caught in benchmark cases',
    },
    {
      label: 'Trust Score',
      value: formatPercent(trustScore),
      tone: trustScore >= 70 ? 'green' : trustScore >= 45 ? 'orange' : 'red',
      note: 'Combines judge confidence grounding and low unsupported claims',
    },
  ];
}

function buildProofCards(result: BenchmarkEvaluationResult): ScoreCard[] {
  const artifactCoverage = Object.keys(result.summary.artifact_type_breakdown).length;
  const oracleCoverage = Object.keys(result.summary.oracle_product_breakdown).length;
  const judgedOutputs = result.sampleResults.length;
  const citedOutputs = result.sampleResults.filter((sample) => sample.grounding.citationSources.length > 0).length;

  return [
    {
      label: 'Artifact Coverage',
      value: `${artifactCoverage}`,
      tone: 'green',
      note: 'Different artifact types covered by the benchmark suite',
    },
    {
      label: 'Oracle Coverage',
      value: `${oracleCoverage}`,
      tone: 'cyan',
      note: 'Oracle product families evaluated in benchmark cases',
    },
    {
      label: 'Judge Validated',
      value: `${judgedOutputs}`,
      tone: 'purple',
      note: 'Benchmark samples independently reviewed by the judge engine',
    },
    {
      label: 'Evidence Traced',
      value: `${citedOutputs}`,
      tone: citedOutputs === judgedOutputs ? 'green' : 'orange',
      note: 'Samples with citation evidence attached to the output',
    },
  ];
}

export function EvaluationDashboard({ result, selectedCaseId, onSelectCase, onRunEvaluation, loading }: Props) {
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
              judge friendly KPI proof and evidence
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

  const outcomeCards = buildOutcomeCards(result);
  const proofCards = buildProofCards(result);
  const exports = result.exports ?? {
    json_report: 'Not available',
    csv_report: 'Not available',
    manifest: 'Not available',
  };

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
          <div className="benchmark-hero-topline">Executive Benchmark View</div>
          <h3>What judges can understand in one scan</h3>
          <p>
            This scorecard separates business outcome metrics from engineering proof so the benchmark reads like a product story,
            not a raw evaluation dump.
          </p>
        </div>

        <div className="section-card">
          <h3>Outcome Metrics</h3>
          <div className="metrics-row">
            {outcomeCards.map((card) => (
              <div key={card.label} className={`metric-chip ${card.tone}`}>
                <div className="value">{card.value}</div>
                <div className="label">{card.label}</div>
                <div className="metric-note">{card.note}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="section-card">
          <h3>Platform Proof</h3>
          <div className="metrics-row">
            {proofCards.map((card) => (
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
          </div>

          <div className="section-card">
            <h3>Exports</h3>
            <p>JSON: {exports.json_report}</p>
            <p>CSV: {exports.csv_report}</p>
            <p>Manifest: {exports.manifest}</p>
          </div>

          <div className="section-card">
            <h3>Artifact Coverage</h3>
            <ul>
              {Object.entries(result.summary.artifact_type_breakdown).map(([artifact, data]) => (
                <li key={artifact}>
                  {artifact}: {data.count} sample{data.count === 1 ? '' : 's'} with {data.avg_review_time_reduction}% average speed gain
                </li>
              ))}
            </ul>
          </div>

          <div className="section-card">
            <h3>Oracle Coverage</h3>
            <ul>
              {Object.entries(result.summary.oracle_product_breakdown).map(([product, data]) => (
                <li key={product}>
                  {product}: {data.count} sample{data.count === 1 ? '' : 's'} with {data.avg_grounding}% average grounding
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="section-card">
          <h3>Case Evidence</h3>
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
                  <span>Speed {Math.round(sample.reviewTimeReductionPercent)}%</span>
                  <span>Accuracy {sample.judgeEvaluation.validation.accuracy}</span>
                  <span>Grounding {sample.judgeEvaluation.validation.oracle_grounding}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
