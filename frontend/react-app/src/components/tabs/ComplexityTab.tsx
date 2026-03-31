import type { PersonaView } from '../../lib/transform';
import type { Persona } from '../../context/PersonaContext';
import { ModeToggle } from '../ModeToggle';

type Props = {
  view: PersonaView;
  persona: Persona;
};

export function ComplexityTab({ view, persona }: Props) {
  const cx = view.complexity;
  const m = cx.metrics;
  const isPM = persona === 'pm';

  return (
    <>
      <ModeToggle />

      {/* PM: simplified high-level score only */}
      {isPM ? (
        <>
          <div className="metrics-row stream-in">
            <div className="metric-chip orange">
              <div className="value">{cx.cyclomaticComplexity || '—'}</div>
              <div className="label">Complexity Score</div>
            </div>
            <div
              className={`metric-chip ${
                cx.riskLabel === 'Low' ? 'green' : cx.riskLabel === 'High' ? 'red' : 'orange'
              }`}
            >
              <div className="value">{cx.riskLabel ?? '—'}</div>
              <div className="label">Risk Level</div>
            </div>
            <div className="metric-chip cyan">
              <div className="value">{m.maintainability}</div>
              <div className="label">Maintainability</div>
            </div>
          </div>
          <div className="section-card stream-in">
            <h3>📊 What This Means</h3>
            <p>
              {cx.cyclomaticComplexity > 10
                ? 'This code has high complexity — it will be difficult and costly to maintain and test.'
                : cx.cyclomaticComplexity > 5
                ? 'This code has moderate complexity — some areas may need attention over time.'
                : 'This code has manageable complexity — maintenance costs should be reasonable.'}
            </p>
          </div>
        </>
      ) : (
        <>
          {/* Developer: full metrics */}
          <div className="metrics-row stream-in">
            <div className="metric-chip orange">
              <div className="value">{cx.cyclomaticComplexity || '—'}</div>
              <div className="label">Cyclomatic</div>
            </div>
            <div className="metric-chip red">
              <div className="value">{cx.nestingDepth || '—'}</div>
              <div className="label">Nesting Depth</div>
            </div>
            <div className="metric-chip cyan">
              <div className="value">{m.maintainability}</div>
              <div className="label">Maintainability</div>
            </div>
            <div className="metric-chip green">
              <div className="value">{m.readability}</div>
              <div className="label">Readability</div>
            </div>
          </div>

          {(cx.hotspots?.length ?? 0) > 0 && (
            <div className="section-card stream-in">
              <h3>🔥 Complexity Hotspots</h3>
              {cx.hotspots!.map((h) => (
                <div key={h.name} className="complexity-bar-wrap">
                  <div className="complexity-label">
                    <span style={{ color: 'var(--text)' }}>{h.name}</span>
                    <span>
                      {h.score}/10 — {h.reason}
                    </span>
                  </div>
                  <div className="complexity-bar">
                    <div
                      className="complexity-fill"
                      style={{
                        width: `${h.score * 10}%`,
                        background:
                          h.score > 7
                            ? 'var(--danger)'
                            : h.score > 4
                            ? 'var(--warn)'
                            : 'var(--accent3)',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
