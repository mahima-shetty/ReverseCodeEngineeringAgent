import type { PersonaView } from '../../lib/transform';
import type { Persona } from '../../context/PersonaContext';
import { ModeToggle } from '../ModeToggle';
import { riskColor } from '../../lib/utils';

type Props = {
  view: PersonaView;
  persona: Persona;
};

export function SecurityTab({ view, persona }: Props) {
  const sec = view.security;
  const isPM = persona === 'pm';
  const isQA = persona === 'qa';

  const scoreColor =
    (sec.score ?? 0) >= 80
      ? 'var(--accent3)'
      : (sec.score ?? 0) >= 50
      ? 'var(--warn)'
      : 'var(--danger)';

  const highCount = (sec.issues ?? []).filter(
    (i) => i.severity === 'HIGH' || i.severity === 'CRITICAL'
  ).length;

  return (
    <>
      <ModeToggle />

      {/* PM: risk level label instead of numeric score */}
      {isPM ? (
        <div className="metrics-row stream-in">
          <div className="metric-chip">
            <div
              className="value"
              style={{
                color:
                  sec.riskLabel === 'Low'
                    ? 'var(--accent3)'
                    : sec.riskLabel === 'High'
                    ? 'var(--danger)'
                    : 'var(--warn)',
                fontSize: 22,
              }}
            >
              {sec.riskLabel ?? '—'} Risk
            </div>
            <div className="label">Overall Security</div>
          </div>
          <div className="metric-chip red">
            <div className="value">{highCount}</div>
            <div className="label">Critical Issues</div>
          </div>
        </div>
      ) : (
        <div className="metrics-row stream-in">
          <div className="metric-chip">
            <div className="value" style={{ color: scoreColor }}>
              {sec.score || '—'}
            </div>
            <div className="label">Security Score</div>
          </div>
          <div className="metric-chip red">
            <div className="value">{highCount}</div>
            <div className="label">High Issues</div>
          </div>
          <div className="metric-chip orange">
            <div className="value">{(sec.hardcoding ?? []).length}</div>
            <div className="label">Hardcoded Items</div>
          </div>
        </div>
      )}

      {/* Security Issues */}
      {(sec.issues?.length ?? 0) > 0 ? (
        <div className="section-card stream-in">
          <h3>
            {isQA
              ? '🧪 Security Test Scenarios'
              : isPM
              ? '🚨 Key Security Risks'
              : '🚨 Security Issues'}
          </h3>
          {sec.issues!.map((issue, idx) => (
            <div
              key={idx}
              className={`antipattern-item ${
                issue.severity === 'MEDIUM'
                  ? 'warn'
                  : issue.severity === 'LOW'
                  ? 'low'
                  : ''
              }`}
            >
              <h4>
                <span style={{ color: riskColor(issue.severity) }}>
                  [{issue.severity}]
                </span>{' '}
                {issue.type}
                {!isPM && issue.confidence_score ? (
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {' '}({issue.confidence_score}% confidence)
                  </span>
                ) : null}
              </h4>
              <p>
                {issue.description}
                {/* Only show line reference in technical developer mode */}
                {issue.line && !isPM ? (
                  <span style={{ color: 'var(--persona-accent)' }}>
                    {' '}@ {issue.line}
                  </span>
                ) : null}
              </p>
              {/* QA: show test action hint */}
              {isQA && (
                <p style={{ color: 'var(--accent3)', marginTop: 4 }}>
                  ✅ Write test: verify system rejects or handles this condition safely
                </p>
              )}
              {issue.evidence && !isPM ? (
                <p
                  style={{
                    color: 'var(--muted)',
                    fontSize: 11,
                    marginTop: 4,
                  }}
                >
                  <em>Evidence: {issue.evidence}</em>
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="section-card stream-in">
          <h3>✅ No Security Issues Found</h3>
        </div>
      )}

      {/* Hardcoded values — hidden for PM */}
      {!isPM && (sec.hardcoding?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>🔑 Hardcoded Values</h3>
          {sec.hardcoding!.map((h, idx) => (
            <div key={idx} className="antipattern-item warn">
              <h4>{(h.type ?? '').toUpperCase()}</h4>
              <p>{h.description}</p>
              {isQA && (
                <p style={{ color: 'var(--accent3)', marginTop: 4 }}>
                  ✅ Test: verify production environment uses environment variables, not hardcoded values
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
