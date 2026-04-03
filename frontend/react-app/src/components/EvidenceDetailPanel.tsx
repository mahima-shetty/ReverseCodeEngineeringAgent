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
          <p>
            This view explains what the system saw, what it got right, what it missed, and how well the result stayed grounded
            in Oracle specific evidence.
          </p>
        </div>
        <div className="evaluation-grid">
          <div className="section-card">
            <h3>Original Input</h3>
            <div className="code-block">{sample.analysisItem.originalInput}</div>
          </div>
          <div className="section-card">
            <h3>Plain English Scorecard</h3>
            <ul>
              <li>How accurate the result was: {sample.judgeEvaluation.validation.accuracy}</li>
              <li>How well it stayed Oracle specific: {sample.judgeEvaluation.validation.oracle_grounding}</li>
              <li>How specific the answer was to the product area: {sample.judgeEvaluation.validation.oracle_specificity}</li>
              <li>How many valid findings it kept: {sample.judgeEvaluation.finding_metrics?.precision ?? 0}</li>
              <li>How many important issues it caught: {sample.judgeEvaluation.finding_metrics?.recall ?? 0}</li>
              <li>How many unsupported claims it made: {sample.judgeEvaluation.finding_metrics?.false_positive_rate ?? 0}</li>
              <li>Time to first useful answer: {sample.judgeEvaluation.latency_metrics?.time_to_first_useful_output ?? 0}s</li>
              <li>Total runtime: {sample.judgeEvaluation.latency_metrics?.total_runtime ?? 0}s</li>
              <li>Manual review time saved: {sample.reviewTimeReductionPercent}%</li>
            </ul>
          </div>
          <div className="section-card">
            <h3>Matched Findings</h3>
            <ul>
              {Object.entries(sample.matchedKeywords).map(([key, values]) => (
                <li key={key}>{key}: {values.length ? values.join(', ') : 'none matched'}</li>
              ))}
            </ul>
          </div>
          <div className="section-card">
            <h3>Missed and Unsupported</h3>
            <ul>
              {Object.entries(sample.missedKeywords).map(([key, values]) => (
                <li key={key}>{key}: {values.length ? values.join(', ') : 'none missed'}</li>
              ))}
            </ul>
            {sample.unsupportedFindings.length > 0 ? (
              <>
                <h3>Unsupported Claims</h3>
                <ul>
                  {sample.unsupportedFindings.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
          <div className="section-card">
            <h3>Oracle Grounding</h3>
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
