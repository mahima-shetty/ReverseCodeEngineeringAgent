import { useEffect, useMemo, useRef, useState } from 'react';
import type { NormalizedResult, RagCitation } from '../types';
import { usePersona } from '../context/PersonaContext';
import { transformResponse, type TabId } from '../lib/transform';
import { IntentTab } from './tabs/IntentTab';
import { DataFlowTab } from './tabs/DataFlowTab';
import { ComplexityTab } from './tabs/ComplexityTab';
import { SecurityTab } from './tabs/SecurityTab';
import { AntiPatternsTab } from './tabs/AntiPatternsTab';
import { RefactorTab } from './tabs/RefactorTab';
import { JiraTab } from './tabs/JiraTab';
import { TestScenariosTab } from './tabs/TestScenariosTab';
import { ImpactSummaryTab } from './tabs/ImpactSummaryTab';

// Tab metadata for all possible tabs
const TAB_META: Record<TabId, { icon: string; label: string }> = {
  intent: { icon: '📋', label: 'Functional Intent' },
  dataflow: { icon: '🔄', label: 'Data Flow' },
  complexity: { icon: '📊', label: 'Complexity' },
  security: { icon: '🔒', label: 'Security' },
  antipatterns: { icon: '⚠️', label: 'Anti-patterns' },
  refactor: { icon: '🛠', label: 'Refactor' },
  jira: { icon: '🎫', label: 'Jira Tasks' },
  testscenarios: { icon: '🧪', label: 'Test Scenarios' },
  impact: { icon: '📈', label: 'Impact Summary' },
};

function RagCitationsPanel({ citations }: { citations: RagCitation[] }) {
  const [open, setOpen] = useState(false);
  if (!citations || citations.length === 0) return null;

  // Extract a readable filename from a gs:// URI
  const shortName = (src: string) => {
    const parts = src.split('/');
    return parts[parts.length - 1] || src;
  };

  return (
    <div style={{
      margin: '16px 0 0 0',
      borderTop: '1px solid var(--border, #e2e8f0)',
      paddingTop: 12,
    }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text-muted, #64748b)',
          padding: '4px 0',
        }}
      >
        <span>📚</span>
        <span>RAG Sources — Org Standards Applied ({citations.length})</span>
        <span style={{ marginLeft: 4 }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {citations.map((c, i) => (
            <div
              key={i}
              style={{
                background: 'var(--surface-alt, #f8fafc)',
                border: '1px solid var(--border, #e2e8f0)',
                borderRadius: 6,
                padding: '10px 14px',
              }}
            >
              <div style={{
                fontSize: 12,
                fontWeight: 700,
                color: 'var(--accent, #6366f1)',
                marginBottom: 4,
                wordBreak: 'break-all',
              }}>
                [{i + 1}] {shortName(c.source)}
              </div>
              <div style={{
                fontSize: 12,
                color: 'var(--text-muted, #64748b)',
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
                lineHeight: 1.5,
              }}>
                {c.excerpt}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type Props = {
  result: NormalizedResult;
};

export function ReportPanel({ result }: Props) {
  const { persona, mode } = usePersona();
  const panelRef = useRef<HTMLDivElement>(null);

  // Compute transformed persona view (memoized)
  const view = useMemo(
    () => transformResponse(result, persona, mode),
    [result, persona, mode]
  );

  // Active tab — reset to first visible tab when persona changes
  const [tab, setTab] = useState<TabId>(view.visibleTabs[0]);

  useEffect(() => {
    // If current tab is no longer visible for new persona, switch to first
    if (!view.visibleTabs.includes(tab)) {
      setTab(view.visibleTabs[0]);
    }
  }, [view.visibleTabs, tab]);

  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [result]);

  return (
    <div className="panel output-panel visible" id="outputPanel" ref={panelRef}>
      {/* ── Tab bar ── */}
      <div className="tabs">
        {view.visibleTabs.map((tabId) => {
          const meta = TAB_META[tabId];
          return (
            <button
              key={tabId}
              type="button"
              className={`tab-btn ${tab === tabId ? 'active' : ''}`}
              onClick={() => setTab(tabId)}
            >
              <span className="tab-icon">{meta.icon}</span> {meta.label}
            </button>
          );
        })}
      </div>

      {/* ── Tab content ── */}
      <div className="tab-content active" style={{ display: 'block', padding: 24 }}>
        {tab === 'intent' && <IntentTab view={view} persona={persona} />}
        {tab === 'dataflow' && <DataFlowTab view={view} persona={persona} />}
        {tab === 'complexity' && <ComplexityTab view={view} persona={persona} />}
        {tab === 'security' && <SecurityTab view={view} persona={persona} />}
        {tab === 'antipatterns' && <AntiPatternsTab view={view} />}
        {tab === 'refactor' && <RefactorTab view={view} />}
        {tab === 'jira' && <JiraTab view={view} persona={persona} />}
        {tab === 'testscenarios' && <TestScenariosTab view={view} />}
        {tab === 'impact' && <ImpactSummaryTab view={view} />}

        {/* ── RAG citations — always shown at bottom of every tab ── */}
        <RagCitationsPanel citations={result.ragCitations} />
      </div>
    </div>
  );
}
