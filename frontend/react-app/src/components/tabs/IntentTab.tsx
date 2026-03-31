import type { PersonaView } from '../../lib/transform';
import type { Persona } from '../../context/PersonaContext';
import { ModeToggle } from '../ModeToggle';

type Props = {
  view: PersonaView;
  persona: Persona;
};

export function IntentTab({ view, persona }: Props) {
  const fi = view.functionalIntent;

  return (
    <>
      <ModeToggle />

      {/* PM: Business Summary card instead of full technical purpose */}
      {persona === 'pm' && fi.businessSummary ? (
        <div className="section-card stream-in">
          <h3>🎯 Business Summary</h3>
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{fi.businessSummary}</div>
        </div>
      ) : (
        <div className="section-card stream-in">
          <h3>📋 Purpose</h3>
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{fi.purpose}</div>
        </div>
      )}

      {/* Business Logic — hide for PM (already in summary) */}
      {persona !== 'pm' && (fi.businessLogic?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>⚙️ Business Logic</h3>
          <ul>
            {fi.businessLogic.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Inputs & Outputs */}
      {persona !== 'pm' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div className="section-card stream-in">
            <h3>📥 Inputs</h3>
            <ul>
              {fi.inputs.map((input, i) => (
                <li key={i}>{input}</li>
              ))}
            </ul>
          </div>
          <div className="section-card stream-in">
            <h3>📤 Outputs</h3>
            <ul>
              {fi.outputs.map((output, i) => (
                <li key={i}>{output}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Side Effects — developer only */}
      {persona === 'developer' && (fi.sideEffects?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>💥 Side Effects</h3>
          <ul>
            {fi.sideEffects!.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {/* QA: Testable interpretation note */}
      {persona === 'qa' && (
        <div className="section-card stream-in">
          <h3>🧪 Testable Interpretation</h3>
          <ul>
            {fi.inputs.map((inp, i) => (
              <li key={i}>Input: <strong>{inp}</strong> — verify validation and boundary conditions</li>
            ))}
            {fi.outputs.map((out, i) => (
              <li key={i}>Output: <strong>{out}</strong> — verify expected vs actual results</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
