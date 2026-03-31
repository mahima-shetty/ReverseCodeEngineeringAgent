import type { PersonaView } from '../../lib/transform';
import { ModeToggle } from '../ModeToggle';
import { riskColor } from '../../lib/utils';

type Props = { view: PersonaView };

export function RefactorTab({ view }: Props) {
  const recs = view.refactorRecommendations;

  return (
    <>
      <ModeToggle />
      {recs.length ? (
        recs.map((r, idx) => (
          <div key={idx} className="section-card stream-in">
            <h3>
              <span style={{ color: riskColor(r.priority) }}>[{r.priority}]</span> {r.title}
              {r.confidence_score ? (
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {' '}({r.confidence_score}% confidence)
                </span>
              ) : null}
            </h3>
            <p style={{ marginBottom: 10 }}>{r.description}</p>
            {r.benefit ? (
              <p style={{ color: 'var(--accent3)', marginBottom: 10 }}>✅ Benefit: {r.benefit}</p>
            ) : null}
            {r.evidence ? (
              <p style={{ color: 'var(--muted)', fontSize: 11, marginBottom: 10 }}>
                <em>Evidence: {r.evidence}</em>
              </p>
            ) : null}
            {r.codeHint ? <div className="code-block">{r.codeHint}</div> : null}
          </div>
        ))
      ) : (
        <div className="section-card">
          <h3>✅ No Refactoring Needed</h3>
        </div>
      )}
    </>
  );
}
