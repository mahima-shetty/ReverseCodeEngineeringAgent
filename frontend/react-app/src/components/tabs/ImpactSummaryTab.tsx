import type { PersonaView } from '../../lib/transform';
import { ModeToggle } from '../ModeToggle';

type Props = { view: PersonaView };

export function ImpactSummaryTab({ view }: Props) {
  const impact = view.impactSummary;

  if (!impact) {
    return (
      <div className="section-card stream-in">
        <h3>📊 No impact data available</h3>
      </div>
    );
  }

  return (
    <>
      <ModeToggle />

      {/* Business Impact */}
      <div className="impact-summary-card stream-in">
        <h3>🏢 Business Impact</h3>
        <p style={{ fontSize: 14, lineHeight: 1.7, color: '#b0c4de' }}>{impact.businessImpact}</p>
      </div>

      {/* Risk Overview */}
      <div className="impact-summary-card stream-in">
        <h3>🛡️ Risk Overview</h3>
        <div className={`risk-level-badge ${impact.riskLevel}`}>
          {impact.riskLevel === 'Low' ? '🟢' : impact.riskLevel === 'Medium' ? '🟡' : '🔴'}
          {impact.riskLevel} Risk
        </div>
        <p style={{ fontSize: 14, lineHeight: 1.7, color: '#b0c4de' }}>{impact.riskOverview}</p>
      </div>

      {/* Top Actions */}
      {impact.topActions.length > 0 && (
        <div className="impact-summary-card stream-in">
          <h3>🎯 Recommended Actions</h3>
          <ul className="top-actions-list">
            {impact.topActions.map((action, idx) => (
              <li key={idx}>{action}</li>
            ))}
          </ul>
        </div>
      )}

      {impact.topActions.length === 0 && (
        <div className="section-card stream-in">
          <h3>✅ No immediate actions required</h3>
          <p style={{ color: 'var(--muted)', fontSize: 13 }}>
            The code appears to be in good health with no high-priority concerns.
          </p>
        </div>
      )}
    </>
  );
}
