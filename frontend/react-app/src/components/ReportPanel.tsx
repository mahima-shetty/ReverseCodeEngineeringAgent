import { useEffect, useRef, useState } from 'react';
import type { NormalizedResult } from '../types';
import { riskColor } from '../lib/utils';

const TABS = [
  { id: 'intent' as const, icon: '📋', label: 'Functional Intent' },
  { id: 'dataflow' as const, icon: '🔄', label: 'Data Flow' },
  { id: 'complexity' as const, icon: '📊', label: 'Complexity' },
  { id: 'security' as const, icon: '🔒', label: 'Security' },
  { id: 'antipatterns' as const, icon: '⚠️', label: 'Anti-patterns' },
  { id: 'refactor' as const, icon: '🛠', label: 'Refactor' },
  { id: 'jira' as const, icon: '🎫', label: 'Jira Tasks' },
];

type TabId = (typeof TABS)[number]['id'];

type Props = {
  result: NormalizedResult;
};

export function ReportPanel({ result }: Props) {
  const [tab, setTab] = useState<TabId>('intent');
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [result]);

  const fi = result.functionalIntent;
  const df = result.dataFlow;
  const cx = result.complexity;
  const sec = result.security;
  const aps = result.antiPatterns;
  const recs = result.refactorRecommendations;
  const jira = result.jiraTickets;
  const m = cx.metrics;

  return (
    <div className="panel output-panel visible" id="outputPanel" ref={panelRef}>
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab-btn ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            <span className="tab-icon">{t.icon}</span> {t.label}
          </button>
        ))}
      </div>

      <div className={`tab-content ${tab === 'intent' ? 'active' : ''}`} style={{ display: tab === 'intent' ? 'block' : 'none' }}>
        <div className="section-card stream-in">
          <h3>📋 Purpose</h3>
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{fi.purpose}</div>
        </div>
        <div className="section-card stream-in">
          <h3>⚙️ Business Logic</h3>
          <ul>
            {(fi.businessLogic ?? []).map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div className="section-card stream-in">
            <h3>📥 Inputs</h3>
            <ul>
              {fi.inputs.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          </div>
          <div className="section-card stream-in">
            <h3>📤 Outputs</h3>
            <ul>
              {fi.outputs.map((o) => (
                <li key={o}>{o}</li>
              ))}
            </ul>
          </div>
        </div>
        {(fi.sideEffects?.length ?? 0) > 0 && (
          <div className="section-card stream-in">
            <h3>💥 Side Effects</h3>
            <ul>
              {fi.sideEffects!.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className={`tab-content ${tab === 'dataflow' ? 'active' : ''}`} style={{ display: tab === 'dataflow' ? 'block' : 'none' }}>
        <div className="section-card stream-in">
          <h3>📐 Processing Steps</h3>
          <ul>
            {(df.steps ?? []).map((s, i) => (
              <li key={i}>
                <strong style={{ color: 'var(--accent)' }}>{i + 1}.</strong> {s}
              </li>
            ))}
          </ul>
        </div>
        {(df.tables?.length ?? 0) > 0 && (
          <div className="section-card stream-in">
            <h3>🗄️ Tables / Objects</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {df.tables!.map((t) => (
                <span
                  key={t}
                  style={{
                    background: 'rgba(0,212,255,0.1)',
                    border: '1px solid var(--accent)',
                    borderRadius: 6,
                    padding: '4px 10px',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 12,
                    color: 'var(--accent)',
                  }}
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
        {(df.transformations?.length ?? 0) > 0 && (
          <div className="section-card stream-in">
            <h3>🔁 Transformations</h3>
            <ul>
              {df.transformations!.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className={`tab-content ${tab === 'complexity' ? 'active' : ''}`} style={{ display: tab === 'complexity' ? 'block' : 'none' }}>
        <div className="metrics-row stream-in">
          <div className="metric-chip orange">
            <div className="value">{cx.cyclomaticComplexity || '—'}</div>
            <div className="label">Cyclomatic</div>
          </div>
          <div className="metric-chip red">
            <div className="value">{cx.nestingDepth || '—'}</div>
            <div className="label">Nesting Depth</div>
          </div>
          <div className="metric-chip cyan">
            <div className="value">{m.maintainability}</div>
            <div className="label">Maintainability</div>
          </div>
          <div className="metric-chip green">
            <div className="value">{m.readability}</div>
            <div className="label">Readability</div>
          </div>
        </div>
        {(cx.hotspots?.length ?? 0) > 0 && (
          <div className="section-card stream-in">
            <h3>🔥 Complexity Hotspots</h3>
            {cx.hotspots!.map((h) => (
              <div key={h.name} className="complexity-bar-wrap">
                <div className="complexity-label">
                  <span style={{ color: 'var(--text)' }}>{h.name}</span>
                  <span>
                    {h.score}/10 — {h.reason}
                  </span>
                </div>
                <div className="complexity-bar">
                  <div
                    className="complexity-fill"
                    style={{
                      width: `${h.score * 10}%`,
                      background: h.score > 7 ? 'var(--danger)' : h.score > 4 ? 'var(--warn)' : 'var(--accent3)',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className={`tab-content ${tab === 'security' ? 'active' : ''}`} style={{ display: tab === 'security' ? 'block' : 'none' }}>
        <SecurityTab sec={sec} />
      </div>

      <div className={`tab-content ${tab === 'antipatterns' ? 'active' : ''}`} style={{ display: tab === 'antipatterns' ? 'block' : 'none' }}>
        {aps.length ? (
          <>
            <div className="section-card stream-in">
              <h3>⚠️ Detected Anti-Patterns ({aps.length})</h3>
            </div>
            {aps.map((a) => (
              <div key={a.pattern + a.description} className={`antipattern-item ${a.severity === 'MEDIUM' ? 'warn' : ''} stream-in`}>
                <h4>
                  <span style={{ color: riskColor(a.severity) }}>[{a.severity}]</span> {a.pattern} {a.confidence_score ? <span style={{ fontSize: 11, color: 'var(--muted)' }}>({a.confidence_score}% confidence)</span> : null}
                </h4>
                <p>{a.description}</p>
                {a.recommendation ? <p style={{ color: 'var(--accent3)', marginTop: 6 }}>💡 {a.recommendation}</p> : null}
                {a.evidence ? <p style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4 }}><em>Evidence: {a.evidence}</em></p> : null}
              </div>
            ))}
          </>
        ) : (
          <div className="section-card stream-in">
            <h3>✅ No Anti-Patterns Detected</h3>
          </div>
        )}
      </div>

      <div className={`tab-content ${tab === 'refactor' ? 'active' : ''}`} style={{ display: tab === 'refactor' ? 'block' : 'none' }}>
        {recs.length ? (
          recs.map((r) => (
            <div key={r.title + r.description} className="section-card stream-in">
              <h3>
                <span style={{ color: riskColor(r.priority) }}>[{r.priority}]</span> {r.title} {r.confidence_score ? <span style={{ fontSize: 11, color: 'var(--muted)' }}>({r.confidence_score}% confidence)</span> : null}
              </h3>
              <p style={{ marginBottom: 10 }}>{r.description}</p>
              {r.benefit ? <p style={{ color: 'var(--accent3)', marginBottom: 10 }}>✅ Benefit: {r.benefit}</p> : null}
              {r.evidence ? <p style={{ color: 'var(--muted)', fontSize: 11, marginBottom: 10 }}><em>Evidence: {r.evidence}</em></p> : null}
              {r.codeHint ? <div className="code-block">{r.codeHint}</div> : null}
            </div>
          ))
        ) : (
          <div className="section-card">
            <h3>✅ No Refactoring Needed</h3>
          </div>
        )}
      </div>
      <div className={`tab-content ${tab === 'jira' ? 'active' : ''}`} style={{ display: tab === 'jira' ? 'block' : 'none' }}>
        {jira.length ? (
          jira.map((t, idx) => (
            <div key={t.title + idx} className="section-card stream-in">
              <h3>🎫 [{t.type || 'Task'}] {t.title}</h3>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>Story Points: {t.story_points || '—'}</div>
              <p style={{ marginBottom: 10 }}>{t.description}</p>
            </div>
          ))
        ) : (
          <div className="section-card">
            <h3>✅ No Jira Tickets Generated</h3>
          </div>
        )}
      </div>
    </div>
  );
}

function SecurityTab({ sec }: { sec: NormalizedResult['security'] }) {
  const scoreColor = sec.score >= 80 ? 'var(--accent3)' : sec.score >= 50 ? 'var(--warn)' : 'var(--danger)';
  const highCount = (sec.issues ?? []).filter((i) => i.severity === 'HIGH').length;

  return (
    <>
      <div className="metrics-row stream-in">
        <div className="metric-chip">
          <div className="value" style={{ color: scoreColor }}>
            {sec.score || '—'}
          </div>
          <div className="label">Security Score</div>
        </div>
        <div className="metric-chip red">
          <div className="value">{highCount}</div>
          <div className="label">High Issues</div>
        </div>
        <div className="metric-chip orange">
          <div className="value">{(sec.hardcoding ?? []).length}</div>
          <div className="label">Hardcoded Items</div>
        </div>
      </div>
      {sec.issues?.length ? (
        <div className="section-card stream-in">
          <h3>🚨 Security Issues</h3>
          {sec.issues.map((i) => (
            <div key={i.type + i.description} className={`antipattern-item ${i.severity === 'MEDIUM' ? 'warn' : i.severity === 'LOW' ? 'low' : ''}`}>
              <h4>
                <span style={{ color: riskColor(i.severity) }}>[{i.severity}]</span> {i.type} {i.confidence_score ? <span style={{ fontSize: 11, color: 'var(--muted)' }}>({i.confidence_score}% confidence)</span> : null}
              </h4>
              <p>
                {i.description}{' '}
                {i.line ? <span style={{ color: 'var(--accent)' }}>@ {i.line}</span> : null}
              </p>
              {i.evidence ? <p style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4 }}><em>Evidence: {i.evidence}</em></p> : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="section-card stream-in">
          <h3>✅ No Security Issues Found</h3>
        </div>
      )}
      {(sec.hardcoding?.length ?? 0) > 0 && (
        <div className="section-card stream-in">
          <h3>🔑 Hardcoded Values</h3>
          {sec.hardcoding!.map((h) => (
            <div key={String(h.description)} className="antipattern-item warn">
              <h4>{(h.type ?? '').toUpperCase()}</h4>
              <p>{h.description}</p>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
