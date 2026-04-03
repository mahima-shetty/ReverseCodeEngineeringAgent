import { usePersona, type Persona } from '../context/PersonaContext';

const PERSONAS: { id: Persona; icon: string; label: string }[] = [
  { id: 'developer', icon: '💻', label: 'Developer' },
  { id: 'qa', icon: '🧪', label: 'QA Engineer' },
  { id: 'pm', icon: '📈', label: 'Project Manager' },
];

export function PersonaSelector() {
  const { persona, setPersona } = usePersona();

  return (
    <div className="persona-selector" role="group" aria-label="Select persona">
      {PERSONAS.map((p) => (
        <button
          key={p.id}
          type="button"
          className={`persona-selector-btn ${persona === p.id ? 'active' : ''}`}
          onClick={() => setPersona(p.id)}
          aria-pressed={persona === p.id}
          title={`Switch to ${p.label} view`}
        >
          <span className="persona-selector-icon">{p.icon}</span>
          {p.label}
        </button>
      ))}
    </div>
  );
}
