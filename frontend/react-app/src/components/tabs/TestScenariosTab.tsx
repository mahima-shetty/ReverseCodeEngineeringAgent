import type { PersonaView } from '../../lib/transform';
import { ModeToggle } from '../ModeToggle';

type Props = { view: PersonaView };

export function TestScenariosTab({ view }: Props) {
  const scenarios = view.testScenarios ?? [];

  return (
    <>
      <ModeToggle />
      <div className="section-card stream-in">
        <h3>🧪 Derived Test Scenarios ({scenarios.length})</h3>
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>
          Auto-generated from security findings, anti-patterns, and refactor recommendations
        </p>
      </div>
      {scenarios.length ? (
        scenarios.map((s, idx) => (
          <div key={idx} className="test-scenario-item stream-in">
            <span className={`scenario-type-badge ${s.type}`}>{s.type}</span>
            <h4>{s.title}</h4>
            <p>{s.description}</p>
            <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>
              Source: {s.source}
            </p>
          </div>
        ))
      ) : (
        <div className="section-card stream-in">
          <h3>✅ No test scenarios derived — code appears clean</h3>
        </div>
      )}
    </>
  );
}
