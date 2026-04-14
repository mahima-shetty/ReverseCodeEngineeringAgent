import type { BenchmarkEvaluationResult, BenchmarkSampleResult } from '../types';

type Props = {
  result: BenchmarkEvaluationResult | null;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  onRunEvaluation: () => void;
  loading: boolean;
};

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function formatSeconds(value: number): string {
  return `${value.toFixed(2)}s`;
}

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`;
}

function renderList(items: string[], empty = 'None'): JSX.Element {
  if (!items.length) return <p>{empty}</p>;
  return (
    <ul>
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

function BenchmarkActualColumn({ sample }: { sample: BenchmarkSampleResult }) {
  const result = sample.actualResult;
  return (
    <div className="benchmark-compare-column">
      <div className="benchmark-column-header">
        <span className="benchmark-column-kicker">Actual Result</span>
        <span className={`status-pill ${sample.finalStatus}`}>{sample.finalStatus}</span>
      </div>
      <div className="section-card">
        <h3>Summary</h3>
        <p>{result.summary.oneliner || 'No summary returned.'}</p>
        <p>Complexity: {result.summary.complexity}</p>
        <p>Risk: {result.summary.overallRisk}</p>
      </div>
      <div className="section-card">
        <h3>Intent and Data Flow</h3>
        <p>{result.functionalIntent.purpose || 'No purpose returned.'}</p>
        <h3>Business Logic</h3>
        {renderList(result.functionalIntent.businessLogic)}
        <h3>Data Flow Steps</h3>
        {renderList(result.dataFlow.steps)}
      </div>
      <div className="section-card">
        <h3>Security Findings</h3>
        {result.security.issues.length ? (
          <ul>
            {result.security.issues.map((issue, index) => (
              <li key={`${issue.type}-${index}`}>
                {issue.type}: {issue.description}
              </li>
            ))}
          </ul>
        ) : (
          <p>No security findings returned.</p>
        )}
      </div>
      <div className="section-card">
        <h3>Retrieval Evidence</h3>
        {sample.analysisItem.retrieval?.reranked_hits?.length ? (
          <ul>
            {sample.analysisItem.retrieval.reranked_hits.map((hit) => (
              <li key={hit.chunk_id}>
                {hit.product || 'oracle'}: {hit.source}
              </li>
            ))}
          </ul>
        ) : (
          <p>No reranked hits available.</p>
        )}
      </div>
    </div>
  );
}

function BenchmarkExpectedColumn({ sample }: { sample: BenchmarkSampleResult }) {
  const expected = sample.expectedAnswer.rawExpected;
  return (
    <div className="benchmark-compare-column">
      <div className="benchmark-column-header">
        <span className="benchmark-column-kicker">Expected Answer</span>
      </div>
      <div className="section-card">
        <h3>Benchmark Query</h3>
        <p>{expected.query}</p>
      </div>
      <div className="section-card">
        <h3>Expected Claims</h3>
        {renderList(expected.expected_claims)}
      </div>
      <div className="section-card">
        <h3>Forbidden Claims</h3>
        {renderList(expected.forbidden_claims)}
      </div>
      <div className="section-card">
        <h3>Expected Sources</h3>
        {renderList(expected.expected_sources)}
        <h3>Gold Qrels</h3>
        {renderList(expected.qrels)}
      </div>
    </div>
  );
}

function BenchmarkKpiColumn({ sample }: { sample: BenchmarkSampleResult }) {
  return (
    <div className="benchmark-compare-column">
      <div className="benchmark-column-header">
        <span className="benchmark-column-kicker">Case KPIs</span>
        <span className={`status-pill ${sample.caseKpis.workflowSuccess ? 'approved' : 'rejected'}`}>
          {sample.caseKpis.workflowSuccess ? 'Workflow Pass' : 'Workflow Fail'}
        </span>
      </div>
      <div className="metrics-row benchmark-case-kpis">
        <div className="metric-chip green">
          <div className="value">{formatPercent(sample.caseKpis.groundedAccuracy)}</div>
          <div className="label">Grounded Accuracy</div>
        </div>
        <div className="metric-chip cyan">
          <div className="value">{formatPercent(sample.caseKpis.claimSupportRate)}</div>
          <div className="label">Claim Support</div>
        </div>
        <div className="metric-chip red">
          <div className="value">{formatPercent(sample.caseKpis.unsupportedClaimRate)}</div>
          <div className="label">Unsupported Rate</div>
        </div>
        <div className="metric-chip purple">
          <div className="value">{formatPercent(sample.caseKpis.recallAtK)}</div>
          <div className="label">Recall@K</div>
        </div>
        <div className="metric-chip orange">
          <div className="value">{formatPercent(sample.caseKpis.mrr)}</div>
          <div className="label">MRR</div>
        </div>
      </div>
      <div className="section-card">
        <h3>Delivery Verdict</h3>
        <p>Deliverable: {sample.deliverable ? 'Yes' : 'No'}</p>
        <p>Analysis state: {sample.analysisItem.analysisState}</p>
        <p>Render source: {sample.analysisItem.renderSource}</p>
        <p>Review time reduction: {sample.reviewTimeReductionPercent}%</p>
      </div>
      <div className="section-card">
        <h3>Judge Metrics</h3>
        <ul>
          <li>Accuracy: {sample.judgeEvaluation.validation.accuracy}</li>
          <li>Oracle grounding: {sample.judgeEvaluation.validation.oracle_grounding}</li>
          <li>Oracle specificity: {sample.judgeEvaluation.validation.oracle_specificity}</li>
          <li>Precision: {sample.judgeEvaluation.finding_metrics?.precision ?? 0}</li>
          <li>Recall: {sample.judgeEvaluation.finding_metrics?.recall ?? 0}</li>
          <li>False positive rate: {sample.judgeEvaluation.finding_metrics?.false_positive_rate ?? 0}</li>
        </ul>
      </div>
      <div className="section-card">
        <h3>Matched vs Missed</h3>
        <h3>Matched</h3>
        <ul>
          {Object.entries(sample.matchedKeywords).map(([key, values]) => (
            <li key={key}>{key}: {values.length ? values.join(', ') : 'none matched'}</li>
          ))}
        </ul>
        <h3>Missed</h3>
        <ul>
          {Object.entries(sample.missedKeywords).map(([key, values]) => (
            <li key={key}>{key}: {values.length ? values.join(', ') : 'none missed'}</li>
          ))}
        </ul>
      </div>
      <div className="section-card">
        <h3>Unsupported Claims</h3>
        {renderList(sample.unsupportedFindings, 'No unsupported claims.')}
      </div>
      <div className="section-card">
        <h3>Run Cost and Latency</h3>
        <p>Latency: {formatSeconds(sample.caseKpis.latencySeconds)}</p>
        <p>Cost per bundle: {formatUsd(sample.caseKpis.costPerBundleUsd)}</p>
        <p>Citation precision: {formatPercent(sample.caseKpis.citationPrecision)}</p>
      </div>
    </div>
  );
}

export function BenchmarkWorkspace({ result, selectedCaseId, onSelectCase, onRunEvaluation, loading }: Props) {
  if (!result) {
    return (
      <div className="panel benchmark-workspace">
        <div className="panel-header">
          <div className="panel-title">
            <div className="dot" />
            BENCHMARK KPI WORKSPACE
          </div>
        </div>
        <div style={{ padding: 24 }}>
          <div className="empty-state">
            <div className="icon">B</div>
            <p>
              Run the benchmark suite to see
              <br />
              grounded comparisons and retrieval metrics
            </p>
          </div>
          <button type="button" className={`analyze-btn ${loading ? 'loading' : ''}`} onClick={onRunEvaluation} disabled={loading}>
            <div className="spinner" />
            <span className="btn-text">{loading ? 'Running benchmark...' : 'Run Benchmark Workspace'}</span>
          </button>
        </div>
      </div>
    );
  }

  const selectedSample =
    result.sampleResults.find((item) => item.caseId === selectedCaseId) ??
    result.sampleResults[0] ??
    null;

  if (!selectedSample) return null;

  return (
    <div className="panel benchmark-workspace">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" />
          BENCHMARK KPI WORKSPACE
        </div>
        <button type="button" className="secondary-btn" onClick={onRunEvaluation} disabled={loading}>
          {loading ? 'Running...' : 'Re run Benchmark'}
        </button>
      </div>

      <div className="benchmark-workspace-body">
        <div className="section-card benchmark-hero-card">
          <div className="benchmark-hero-topline">Benchmark Summary</div>
          <h3>Grounded benchmark view</h3>
          <p>The comparison grid below shows the actual output, the structured gold answer, and retrieval-plus-verification metrics for the selected case.</p>
        </div>

        <div className="metrics-row benchmark-top-kpis">
          <div className="metric-chip green">
            <div className="value">{formatPercent(result.summary.kpis.grounded_accuracy_percent)}</div>
            <div className="label">Grounded Accuracy</div>
          </div>
          <div className="metric-chip cyan">
            <div className="value">{formatPercent(result.summary.kpis.claim_support_rate_percent ?? 0)}</div>
            <div className="label">Claim Support</div>
          </div>
          <div className="metric-chip red">
            <div className="value">{formatPercent(result.summary.kpis.unsupported_claim_rate_percent)}</div>
            <div className="label">Unsupported Rate</div>
          </div>
          <div className="metric-chip purple">
            <div className="value">{formatPercent(result.summary.kpis.recall_at_k_percent ?? 0)}</div>
            <div className="label">Recall@K</div>
          </div>
          <div className="metric-chip orange">
            <div className="value">{formatPercent(result.summary.kpis.mrr_percent ?? 0)}</div>
            <div className="label">MRR</div>
          </div>
        </div>

        <div className="benchmark-case-selector section-card">
          <h3>Benchmark Cases</h3>
          <div className="benchmark-case-list">
            {result.sampleResults.map((sample) => (
              <button
                key={sample.caseId}
                type="button"
                className={`benchmark-case-row ${selectedSample.caseId === sample.caseId ? 'active' : ''}`}
                onClick={() => onSelectCase(sample.caseId)}
              >
                <div className="benchmark-case-main">
                  <strong>{sample.analysisItem.label}</strong>
                  <span>
                    {sample.artifactType} / {sample.oracleProduct}
                  </span>
                </div>
                <div className="benchmark-case-meta">
                  <span className={`status-pill ${sample.finalStatus}`}>{sample.finalStatus}</span>
                  <span>GA {Math.round(sample.caseKpis.groundedAccuracy)}%</span>
                  <span>Recall {Math.round(sample.caseKpis.recallAtK)}%</span>
                  <span>{sample.caseKpis.workflowSuccess ? 'PASS' : 'FAIL'}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="benchmark-compare-grid">
          <BenchmarkActualColumn sample={selectedSample} />
          <BenchmarkExpectedColumn sample={selectedSample} />
          <BenchmarkKpiColumn sample={selectedSample} />
        </div>
      </div>
    </div>
  );
}
