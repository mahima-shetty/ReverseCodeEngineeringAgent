import { useTheme } from '../context/PersonaContext';

export function PersonaBadge() {
  const { personaIcon, personaLabel } = useTheme();

  return (
    <div className="persona-badge" aria-label={`Current persona: ${personaLabel}`}>
      <span className="persona-badge-icon">{personaIcon}</span>
      {personaLabel}
    </div>
  );
}
