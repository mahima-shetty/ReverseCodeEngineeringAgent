import type { PersonaView } from '../../lib/transform';
import { ModeToggle } from '../ModeToggle';
import { riskColor } from '../../lib/utils';

type Props = { view: PersonaView };

export function AntiPatternsTab({ view }: Props) {
  const aps = view.antiPatterns;

  return (
    <>
      <ModeToggle />
      {aps.length ? (
        <>
          <div className="section-card stream-in">
            <h3>⚠️ Detected Anti-Patterns ({aps.length})</h3>
          </div>
          {aps.map((a, idx) => (
            <div
              key={idx}
              className={`antipattern-item ${a.severity === 'MEDIUM' ? 'warn' : ''} stream-in`}
            >
              <h4>
                <span style={{ color: riskColor(a.severity) }}>[{a.severity}]</span> {a.pattern}
                {a.confidence_score ? (
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {' '}({a.confidence_score}% confidence)
                  </span>
                ) : null}
              </h4>
              <p>{a.description}</p>
              {a.recommendation ? (
                <p style={{ color: 'var(--accent3)', marginTop: 6 }}>💡 {a.recommendation}</p>
              ) : null}
              {a.evidence ? (
                <p style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4 }}>
                  <em>Evidence: {a.evidence}</em>
                </p>
              ) : null}
            </div>
          ))}
        </>
      ) : (
        <div className="section-card stream-in">
          <h3>✅ No Anti-Patterns Detected</h3>
        </div>
      )}
    </>
  );
}
