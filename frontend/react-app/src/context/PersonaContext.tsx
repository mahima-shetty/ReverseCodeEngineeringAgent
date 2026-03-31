import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type Persona = 'developer' | 'qa' | 'pm';
export type ExplainMode = 'technical' | 'simplified';

interface PersonaContextValue {
  persona: Persona;
  mode: ExplainMode;
  setPersona: (p: Persona) => void;
  setMode: (m: ExplainMode) => void;
}

const PersonaContext = createContext<PersonaContextValue>({
  persona: 'developer',
  mode: 'technical',
  setPersona: () => {},
  setMode: () => {},
});

const STORAGE_PERSONA = 'codelens_persona';
const STORAGE_MODE = 'codelens_mode';

const DEFAULT_MODES: Record<Persona, ExplainMode> = {
  developer: 'technical',
  qa: 'technical',
  pm: 'simplified',
};

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [persona, setPersonaState] = useState<Persona>(() => {
    return (localStorage.getItem(STORAGE_PERSONA) as Persona) || 'developer';
  });

  const [mode, setModeState] = useState<ExplainMode>(() => {
    return (localStorage.getItem(STORAGE_MODE) as ExplainMode) || 'technical';
  });

  const setPersona = (p: Persona) => {
    setPersonaState(p);
    localStorage.setItem(STORAGE_PERSONA, p);
    // Reset mode to the default for new persona
    const defaultMode = DEFAULT_MODES[p];
    setModeState(defaultMode);
    localStorage.setItem(STORAGE_MODE, defaultMode);
  };

  const setMode = (m: ExplainMode) => {
    setModeState(m);
    localStorage.setItem(STORAGE_MODE, m);
  };

  // Sync body data attribute for CSS theme switching
  useEffect(() => {
    document.body.setAttribute('data-persona', persona);
  }, [persona]);

  return (
    <PersonaContext.Provider value={{ persona, mode, setPersona, setMode }}>
      {children}
    </PersonaContext.Provider>
  );
}

export function usePersona(): PersonaContextValue {
  return useContext(PersonaContext);
}

export function useTheme(): { accentColor: string; personaLabel: string; personaIcon: string } {
  const { persona } = useContext(PersonaContext);
  const themes: Record<Persona, { accentColor: string; personaLabel: string; personaIcon: string }> = {
    developer: { accentColor: '#7b61ff', personaLabel: 'Developer', personaIcon: '💻' },
    qa: { accentColor: '#00d4ff', personaLabel: 'QA Engineer', personaIcon: '🐛' },
    pm: { accentColor: '#ff61dc', personaLabel: 'Project Manager', personaIcon: '📊' },
  };
  return themes[persona];
}
