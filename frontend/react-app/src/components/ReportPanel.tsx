import { useEffect, useMemo, useRef, useState } from 'react';
import type { BatchAnalysisItem, NormalizedResult } from '../types';
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

const TAB_META: Record<TabId, { icon: string; label: string }> = {
  intent: { icon: 'ðŸ“‹', label: 'Functional Intent' },
  dataflow: { icon: 'ðŸ”„', label: 'Data Flow' },
  complexity: { icon: 'ðŸ“Š', label: 'Complexity' },
  security: { icon: 'ðŸ”’', label: 'Security' },
  antipatterns: { icon: 'âš ï¸', label: 'Anti-patterns' },
  refactor: { icon: 'ðŸ› ', label: 'Refactor' },
  jira: { icon: 'ðŸŽ«', label: 'Jira Tasks' },
  testscenarios: { icon: 'ðŸ§ª', label: 'Test Scenarios' },
  impact: { icon: 'ðŸ“ˆ', label: 'Impact Summary' },
};

type Props = {
  result: NormalizedResult;
  item?: BatchAnalysisItem | null;
};

export function ReportPanel({ result, item }: Props) {
  const { persona, mode } = usePersona();
  const panelRef = useRef<HTMLDivElement>(null);

  const view = useMemo(
    () => transformResponse(result, persona, mode),
    [result, persona, mode]
  );

  const [tab, setTab] = useState<TabId>(view.visibleTabs[0]);

  useEffect(() => {
    if (!view.visibleTabs.includes(tab)) {
      setTab(view.visibleTabs[0]);
    }
  }, [view.visibleTabs, tab]);

  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [result]);

  return (
    <div className="panel output-panel visible" id="outputPanel" ref={panelRef}>
      {item ? (
        <div className="judge-overview">
          <div className="judge-overview-grid">
            <div className="judge-pane">
              <div className="summary-kicker">Original Input</div>
              <div className="judge-pane-text">{item.originalInput}</div>
            </div>
            <div className="judge-pane">
              <div className="summary-kicker">Code Review Findings Summary</div>
              <div className="judge-score-grid">
                <span>Security issues: {result.security.issues.length}</span>
                <span>Anti-patterns: {result.antiPatterns.length}</span>
                <span>Refactor items: {result.refactorRecommendations.length}</span>
                <span>Complexity: {result.summary.complexity}</span>
                <span>Risk: {result.summary.overallRisk}</span>
              </div>
              <div className="judge-pane-text">{result.summary.oneliner}</div>
              {item.judgeEvaluation.blocking_issues.length > 0 ? (
                <ul className="judge-blocking-list">
                  {item.judgeEvaluation.blocking_issues.map((issue, index) => (
                    <li key={index}>{issue}</li>
                  ))}
                </ul>
              ) : null}
            </div>
            <div className="judge-pane">
              <div className="summary-kicker">Quality Checks</div>
              <div className="judge-score-grid">
                <span>Completeness: {item.judgeEvaluation.scores.completeness}</span>
                <span>Correctness: {item.judgeEvaluation.scores.correctness}</span>
                <span>Hallucination: {item.judgeEvaluation.scores.hallucination}</span>
                <span>Oracle grounding: {item.judgeEvaluation.validation.oracle_grounding}</span>
                <span>Oracle specificity: {item.judgeEvaluation.validation.oracle_specificity}</span>
                <span>Detected products: {(result.ragDiagnostics.products ?? []).join(', ') || 'none detected'}</span>
                <span>Primary provider: {item.primaryRaw.llm_metadata?.provider ?? 'blueverse'}</span>
                <span>Primary tokens: {item.primaryRaw.llm_metadata?.usage?.total_tokens ?? 'n/a'}</span>
                <span>Primary cost: ${item.primaryRaw.llm_metadata?.cost_usd ?? 0}</span>
              </div>
            </div>
            <div className="judge-pane">
              <div className="summary-kicker">RAG Grounding Diagnostics</div>
              <div className="judge-score-grid">
                <span>Products: {(result.ragDiagnostics.products ?? []).join(', ') || 'none detected'}</span>
                <span>Local hits: {result.ragDiagnostics.local_hits ?? 0}</span>
                <span>Vertex hits: {result.ragDiagnostics.vertex_hits ?? 0}</span>
                <span>Returned citations: {result.ragDiagnostics.returned_hits ?? 0}</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}
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
      </div>
    </div>
  );
}
