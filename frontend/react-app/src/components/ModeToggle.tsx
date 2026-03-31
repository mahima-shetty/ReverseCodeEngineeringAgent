import { usePersona, type ExplainMode } from '../context/PersonaContext';

const MODES: { id: ExplainMode; label: string }[] = [
  { id: 'technical', label: '⚙️ Technical' },
  { id: 'simplified', label: '💬 Simplified' },
];

export function ModeToggle() {
  const { mode, setMode } = usePersona();

  return (
    <div className="mode-toggle" role="group" aria-label="Explanation mode">
      <span className="mode-toggle-label">VIEW:</span>
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          className={`mode-toggle-btn ${mode === m.id ? 'active' : ''}`}
          onClick={() => setMode(m.id)}
          aria-pressed={mode === m.id}
          title={
            m.id === 'technical'
              ? 'Detailed, jargon-rich explanations'
              : 'Plain English, no code terms'
          }
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
