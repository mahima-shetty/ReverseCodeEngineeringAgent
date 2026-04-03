import type { BatchAnalysisItem } from '../types';

type Props = {
  items: BatchAnalysisItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function findingBucket(item: BatchAnalysisItem): 'high' | 'medium' | 'low' {
  if (item.analysisState === 'failed') return 'high';
  const security = item.finalResult.security.issues.length;
  const antiPatterns = item.finalResult.antiPatterns.length;
  const risk = item.finalResult.summary.overallRisk;
  if (security >= 2 || antiPatterns >= 2 || risk === 'HIGH') return 'high';
  if (security >= 1 || antiPatterns >= 1 || risk === 'MEDIUM') return 'medium';
  return 'low';
}

const BUCKET_META = {
  high: { title: 'High Attention', className: 'rejected' },
  medium: { title: 'Needs Review', className: 'flagged' },
  low: { title: 'Lower Risk', className: 'approved' },
} as const;

export function BatchResultsPanel({ items, selectedId, onSelect }: Props) {
  if (items.length === 0) return null;

  return (
    <div className="panel batch-results-panel">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" />
          FINDINGS REVIEW
        </div>
      </div>

      <div className="batch-results-body">
        {(['high', 'medium', 'low'] as const).map((bucket) => {
          const group = items.filter((item) => findingBucket(item) === bucket);
          if (group.length === 0) return null;
          const meta = BUCKET_META[bucket];

          return (
            <section key={bucket} className="batch-group">
              <div className="batch-group-header">
                <div className={`status-pill ${meta.className}`}>{meta.title}</div>
                <span>{group.length} item(s)</span>
              </div>
              <div className="batch-result-grid">
                {group.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`batch-result-card ${selectedId === item.id ? 'active' : ''}`}
                    onClick={() => onSelect(item.id)}
                  >
                    <div className="batch-result-card-header">
                      <strong>{item.label}</strong>
                      <span className={`status-pill ${meta.className}`}>{item.finalResult.summary.overallRisk}</span>
                    </div>
                    <div className="batch-result-meta">
                      <span>{String(item.language).toUpperCase()}</span>
                      <span>{item.finalResult.summary.complexity} complexity</span>
                    </div>
                    <div className="batch-result-section">
                      <div className="summary-kicker">Original Input</div>
                      <p>{item.originalInput.slice(0, 180) || 'Empty input'}</p>
                    </div>
                    <div className="batch-result-section">
                      <div className="summary-kicker">Findings Summary</div>
                      <p>{item.analysisState === 'failed' ? (item.failureReason || 'Analysis failed') : item.finalResult.summary.oneliner}</p>
                    </div>
                    <div className="score-row">
                      <span>Security {item.finalResult.security.issues.length}</span>
                      <span>Anti-patterns {item.finalResult.antiPatterns.length}</span>
                      <span>Refactors {item.finalResult.refactorRecommendations.length}</span>
                      <span>RAG {item.judgeEvaluation.validation.oracle_grounding}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
