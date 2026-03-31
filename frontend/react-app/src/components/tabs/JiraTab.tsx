import type { PersonaView } from '../../lib/transform';
import type { Persona } from '../../context/PersonaContext';
import { ModeToggle } from '../ModeToggle';

type Props = { view: PersonaView; persona: Persona };

const typeColors: Record<string, string> = {
  Bug: 'var(--danger)',
  Security: 'var(--danger)',
  Epic: 'var(--accent2)',
  Story: 'var(--accent)',
  Task: 'var(--accent3)',
};

export function JiraTab({ view, persona }: Props) {
  const tickets = view.jiraTickets;
  const isPM = persona === 'pm';
  const isQA = persona === 'qa';

  return (
    <>
      <ModeToggle />
      {tickets.length ? (
        <>
          {isPM && (
            <div className="section-card stream-in" style={{ marginBottom: 14 }}>
              <h3>🎫 Prioritized Backlog ({tickets.length} items)</h3>
              <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                Sorted by priority: Bugs &amp; Security issues first, then Epics, Stories, Tasks
              </p>
            </div>
          )}
          {isQA && (
            <div className="section-card stream-in" style={{ marginBottom: 14 }}>
              <h3>🧪 Test-Oriented Tickets ({tickets.length} items)</h3>
            </div>
          )}
          {tickets.map((t, idx) => (
            <div key={idx} className="section-card stream-in">
              <h3>
                <span
                  style={{
                    color: typeColors[t.type] ?? 'var(--muted)',
                    marginRight: 6,
                  }}
                >
                  [{t.type || 'Task'}]
                </span>
                {t.title}
              </h3>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--muted)',
                  marginBottom: 8,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                Story Points: {t.story_points || '—'}
              </div>
              <p style={{ marginBottom: 10 }}>{t.description}</p>
              {isQA && (
                <p style={{ color: 'var(--accent3)', fontSize: 12 }}>
                  🧪 Add acceptance criteria and test cases before development
                </p>
              )}
            </div>
          ))}
        </>
      ) : (
        <div className="section-card">
          <h3>✅ No Jira Tickets Generated</h3>
        </div>
      )}
    </>
  );
}
