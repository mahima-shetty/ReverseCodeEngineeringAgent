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
        <div className="evaluation-grid">
          <div className="section-card">
            <h3>Original Input</h3>
            <div className="code-block">{sample.analysisItem.originalInput}</div>
          </div>
          <div className="section-card">
            <h3>Judge Validation</h3>
            <ul>
              <li>Accuracy: {sample.judgeEvaluation.validation.accuracy}</li>
              <li>Oracle grounding: {sample.judgeEvaluation.validation.oracle_grounding}</li>
              <li>Oracle specificity: {sample.judgeEvaluation.validation.oracle_specificity}</li>
              <li>Precision: {sample.judgeEvaluation.finding_metrics?.precision ?? 0}</li>
              <li>Recall: {sample.judgeEvaluation.finding_metrics?.recall ?? 0}</li>
              <li>False positive rate: {sample.judgeEvaluation.finding_metrics?.false_positive_rate ?? 0}</li>
              <li>Time to first useful output: {sample.judgeEvaluation.latency_metrics?.time_to_first_useful_output ?? 0}s</li>
              <li>Total runtime: {sample.judgeEvaluation.latency_metrics?.total_runtime ?? 0}s</li>
              <li>Review time reduction: {sample.reviewTimeReductionPercent}%</li>
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
