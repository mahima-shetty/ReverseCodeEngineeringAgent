import type { BenchmarkSampleResult } from '../types';

type Props = {
  sample: BenchmarkSampleResult | null;
};

export function EvidenceDetailPanel({ sample }: Props) {
  if (!sample) return null;

  return (
    <div className="panel output-panel visible">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" />
          BENCHMARK EVIDENCE
        </div>
      </div>
      <div style={{ padding: 24 }}>
        <div className="section-card benchmark-hero-card">
          <div className="benchmark-hero-topline">Selected Benchmark Case</div>
          <h3>{sample.analysisItem.label}</h3>
          <p>This view shows the original artifact, structured gold expectations, and the claim-level grounding signals produced by the benchmark runner.</p>
        </div>
        <div className="evaluation-grid">
          <div className="section-card">
            <h3>Original Input</h3>
            <div className="code-block">{sample.analysisItem.originalInput}</div>
          </div>
          <div className="section-card">
            <h3>Scorecard</h3>
            <ul>
              <li>Grounded accuracy: {sample.caseKpis.groundedAccuracy}</li>
              <li>Claim support rate: {sample.caseKpis.claimSupportRate}</li>
              <li>Unsupported claim rate: {sample.caseKpis.unsupportedClaimRate}</li>
              <li>Citation precision: {sample.caseKpis.citationPrecision}</li>
              <li>Recall@K: {sample.caseKpis.recallAtK}</li>
              <li>MRR: {sample.caseKpis.mrr}</li>
              <li>Time to first useful answer: {sample.judgeEvaluation.latency_metrics?.time_to_first_useful_output ?? 0}s</li>
              <li>Total runtime: {sample.judgeEvaluation.latency_metrics?.total_runtime ?? 0}s</li>
            </ul>
          </div>
          <div className="section-card">
            <h3>Expected Gold</h3>
            <ul>
              <li>Query: {sample.expectedAnswer.rawExpected.query}</li>
              <li>Expected claims: {sample.expectedAnswer.rawExpected.expected_claims.join(', ') || 'none'}</li>
              <li>Forbidden claims: {sample.expectedAnswer.rawExpected.forbidden_claims.join(', ') || 'none'}</li>
              <li>Expected sources: {sample.expectedAnswer.rawExpected.expected_sources.join(', ') || 'none'}</li>
              <li>Gold qrels: {sample.expectedAnswer.rawExpected.qrels.join(', ') || 'none'}</li>
            </ul>
          </div>
          <div className="section-card">
            <h3>Matched and Missed</h3>
            <ul>
              {Object.entries(sample.matchedKeywords).map(([key, values]) => (
                <li key={key}>{key}: {values.length ? values.join(', ') : 'none matched'}</li>
              ))}
            </ul>
            <ul>
              {Object.entries(sample.missedKeywords).map(([key, values]) => (
                <li key={key}>{key}: {values.length ? values.join(', ') : 'none missed'}</li>
              ))}
            </ul>
          </div>
          <div className="section-card">
            <h3>Grounding</h3>
            <ul>
              <li>Expected sources: {sample.grounding.expectedSources.join(', ') || 'none'}</li>
              <li>Matched sources: {sample.grounding.matchedSources.join(', ') || 'none'}</li>
              <li>Citation sources: {sample.grounding.citationSources.join(', ') || 'none'}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
