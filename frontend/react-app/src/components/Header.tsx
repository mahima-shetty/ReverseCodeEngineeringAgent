import { PersonaBadge } from './PersonaBadge';
import { PersonaSelector } from './PersonaSelector';

export function Header() {
  return (
    <header>
      <div className="logo">
        <div className="logo-icon">🔎</div>
        <div className="logo-text">
          Code<span>Lens</span>
        </div>
      </div>
      <div className="header-right">
        <PersonaSelector />
        <PersonaBadge />
      </div>
    </header>
  );
}
