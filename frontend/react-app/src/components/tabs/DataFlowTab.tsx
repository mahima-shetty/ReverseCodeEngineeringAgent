import type { PersonaView } from '../../lib/transform';
import type { Persona } from '../../context/PersonaContext';
import { ModeToggle } from '../ModeToggle';

type Props = {
  view: PersonaView;
  persona: Persona;
};

export function DataFlowTab({ view, persona }: Props) {
  const df = view.dataFlow;

  return (
    <>
      <ModeToggle />

      <div className="section-card stream-in">
        <h3>
          {persona === 'qa' ? '🧪 Processing Steps (Edge Case Focus)' : '📐 Processing Steps'}
        </h3>
        <ul>
          {(df.steps ?? []).map((s, i) => (
            <li key={i}>
              <strong style={{ color: 'var(--persona-accent)' }}>{i + 1}.</strong> {s}
              {persona === 'qa' && (
                <span
                  style={{
                    fontSize: 11,
                    color: 'var(--muted)',
                    marginLeft: 8,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  — test boundary conditions
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      {(df.tables?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>🗄️ Tables / Objects</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {df.tables!.map((t) => (
              <span
                key={t}
                style={{
                  background: 'rgba(var(--persona-accent-rgb), 0.1)',
                  border: '1px solid var(--persona-accent)',
                  borderRadius: 6,
                  padding: '4px 10px',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 12,
                  color: 'var(--persona-accent)',
                }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {(df.transformations?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>🔁 Transformations</h3>
          <ul>
            {df.transformations!.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}

      {/* QA extra: edge case reminder */}
      {persona === 'qa' && (
        <div className="section-card stream-in">
          <h3>⚠️ QA Edge Case Checklist</h3>
          <ul>
            <li>Test with empty / null inputs at each step</li>
            <li>Test maximum data volume through the flow</li>
            <li>Verify data integrity after each transformation</li>
            {(df.tables?.length ?? 0) > 0 && <li>Test rollback behavior if table operations fail mid-flow</li>}
          </ul>
        </div>
      )}
    </>
  );
}
