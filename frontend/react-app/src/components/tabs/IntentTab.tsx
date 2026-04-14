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

      {persona === 'pm' && fi.businessSummary ? (
        <div className="section-card stream-in">
          <h3>Business Summary</h3>
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{fi.businessSummary}</div>
        </div>
      ) : (
        <div className="section-card stream-in">
          <h3>Purpose</h3>
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{fi.purpose}</div>
        </div>
      )}

      {persona !== 'pm' && (fi.businessLogic?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>Business Logic</h3>
          <ul>
            {fi.businessLogic.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {persona !== 'pm' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div className="section-card stream-in">
            <h3>Inputs</h3>
            <ul>
              {fi.inputs.map((input, index) => (
                <li key={index}>{input}</li>
              ))}
            </ul>
          </div>
          <div className="section-card stream-in">
            <h3>Outputs</h3>
            <ul>
              {fi.outputs.map((output, index) => (
                <li key={index}>{output}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {persona === 'developer' && (fi.sideEffects?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>Side Effects</h3>
          <ul>
            {fi.sideEffects.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {persona === 'qa' && (
        <div className="section-card stream-in">
          <h3>Testable Interpretation</h3>
          {(fi.testableInterpretation?.length ?? 0) > 0 ? (
            <ul>
              {fi.testableInterpretation.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          ) : (
            <ul>
              {fi.inputs.map((input, index) => (
                <li key={index}>
                  Input: <strong>{input}</strong> - verify validation and boundary conditions
                </li>
              ))}
              {fi.outputs.map((output, index) => (
                <li key={index}>
                  Output: <strong>{output}</strong> - verify expected vs actual results
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
}
