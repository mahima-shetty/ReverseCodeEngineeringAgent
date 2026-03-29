import type { NormalizedResult } from '../types';
import { riskColor } from '../lib/utils';

type Props = {
  result: NormalizedResult | null;
};

export function QuickSummary({ result }: Props) {
  if (!result) {
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
            <div className="icon">🔍</div>
            <p>
              Run analysis to see
              <br />
              the quick summary here
            </p>
          </div>
        </div>
      </div>
    );
  }

  const s = result.summary;
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
            <div className="value">{s.linesOfCode || '—'}</div>
            <div className="label">Lines of Code</div>
          </div>
          <div className="metric-chip purple">
            <div className="value">{s.functions}</div>
            <div className="label">Functions</div>
          </div>
          <div className="metric-chip orange">
            <div className="value">{s.tables}</div>
            <div className="label">Tables</div>
          </div>
        </div>
        <div className="section-card stream-in">
          <h3>🎯 Overview</h3>
          <p style={{ marginBottom: 12 }}>{s.oneliner}</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--muted)',
                  fontFamily: "'JetBrains Mono', monospace",
                  marginBottom: 4,
                }}
              >
                COMPLEXITY
              </div>
              <div style={{ fontWeight: 800, color: riskColor(s.complexity) }}>{s.complexity || '—'}</div>
            </div>
            <div>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--muted)',
                  fontFamily: "'JetBrains Mono', monospace",
                  marginBottom: 4,
                }}
              >
                RISK LEVEL
              </div>
              <div style={{ fontWeight: 800, color: riskColor(s.overallRisk) }}>{s.overallRisk || '—'}</div>
            </div>
            <div>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--muted)',
                  fontFamily: "'JetBrains Mono', monospace",
                  marginBottom: 4,
                }}
              >
                LANGUAGE
              </div>
              <div style={{ fontWeight: 800, color: 'var(--accent)' }}>{s.language || '—'}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
