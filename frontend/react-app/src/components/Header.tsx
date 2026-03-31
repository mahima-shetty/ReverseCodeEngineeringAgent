import { PersonaSelector } from './PersonaSelector';
import { PersonaBadge } from './PersonaBadge';

export function Header() {
  return (
    <header>
      <div className="logo">
        <div className="logo-icon">🔬</div>
        <div className="logo-text">
          LTM<span>Universe</span>
        </div>
      </div>
      <div className="header-right">
        <PersonaSelector />
        <PersonaBadge />
      </div>
    </header>
  );
}
