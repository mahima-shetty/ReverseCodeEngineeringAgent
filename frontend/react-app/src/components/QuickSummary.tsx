import type { BatchAnalysisItem, BatchAnalysisSummary } from '../types';

type Props = {
  summary: BatchAnalysisSummary | null;
  selectedItem: BatchAnalysisItem | null;
};

export function QuickSummary({ summary, selectedItem }: Props) {
  if (!summary) {
    return (
      <div className="panel" id="quickStatsPanel">
        <div className="panel-header">
          <div className="panel-title">
            <div className="dot" style={{ background: 'var(--accent2)', boxShadow: '0 0 8px var(--accent2)' }} />
            QUICK SUMMARY
          </div>
        </div>
        <div style={{ padding: 24 }}>
          <div className="empty-state">
            <div className="icon">📋</div>
            <p>
              Run analysis to see
              <br />
              findings and review focus
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel" id="quickStatsPanel">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" style={{ background: 'var(--accent2)', boxShadow: '0 0 8px var(--accent2)' }} />
          QUICK SUMMARY
        </div>
      </div>
      <div style={{ padding: 24 }}>
        <div className="metrics-row stream-in">
          <div className="metric-chip cyan">
            <div className="value">{summary.total}</div>
            <div className="label">Batch Inputs</div>
          </div>
          <div className="metric-chip green">
            <div className="value">{itemsWithFindings(summary, selectedItem, 'security')}</div>
            <div className="label">Security Focus</div>
          </div>
          <div className="metric-chip orange">
            <div className="value">{selectedItem?.finalResult.antiPatterns.length ?? '—'}</div>
            <div className="label">Anti-patterns</div>
          </div>
          <div className="metric-chip red">
            <div className="value">{selectedItem?.finalResult.refactorRecommendations.length ?? '—'}</div>
            <div className="label">Refactors</div>
          </div>
        </div>
        <div className="section-card stream-in">
          <h3>Selected Review</h3>
          <p style={{ marginBottom: 12 }}>
            {selectedItem
              ? `${selectedItem.label}: ${selectedItem.analysisState === 'failed' ? (selectedItem.failureReason || 'Analysis failed.') : selectedItem.finalResult.summary.oneliner}`
              : 'Select an item below to inspect the original input, findings, and evidence.'}
          </p>
          {selectedItem ? (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <div>
                <div className="summary-kicker">SECURITY ISSUES</div>
                <div style={{ fontWeight: 800, color: 'var(--danger)' }}>
                  {selectedItem.finalResult.security.issues.length}
                </div>
              </div>
              <div>
                <div className="summary-kicker">ANTI-PATTERNS</div>
                <div style={{ fontWeight: 800, color: 'var(--warn)' }}>
                  {selectedItem.finalResult.antiPatterns.length}
                </div>
              </div>
              <div>
                <div className="summary-kicker">REFACTOR ITEMS</div>
                <div style={{ fontWeight: 800, color: 'var(--accent3)' }}>
                  {selectedItem.finalResult.refactorRecommendations.length}
                </div>
              </div>
              <div>
                <div className="summary-kicker">COMPLEXITY</div>
                <div style={{ fontWeight: 800, color: 'var(--accent)' }}>
                  {selectedItem.finalResult.summary.complexity}
                </div>
              </div>
              <div>
                <div className="summary-kicker">RISK</div>
                <div style={{ fontWeight: 800, color: 'var(--accent2)' }}>
                  {selectedItem.finalResult.summary.overallRisk}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function itemsWithFindings(
  summary: BatchAnalysisSummary,
  selectedItem: BatchAnalysisItem | null,
  type: 'security'
): number | string {
  if (!selectedItem) return summary.total;
  if (type === 'security') return selectedItem.finalResult.security.issues.length;
  return summary.total;
}
