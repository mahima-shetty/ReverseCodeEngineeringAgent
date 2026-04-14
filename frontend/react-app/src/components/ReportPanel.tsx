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

  const activeProvider = item?.finalRaw.llm_metadata?.provider ?? 'unknown';
  const providerFailures = item?.finalRaw.llm_metadata?.provider_failures ?? [];
  const primaryTokens = item?.finalRaw.llm_metadata?.total_tokens ?? 'n/a';
  const retrievalHits = item?.retrieval?.reranked_hits.length ?? 0;
  const isHeuristicFallback = item?.renderSource === 'heuristic';
  const hasProviderFailure = Boolean(item?.failureReason) || providerFailures.length > 0;

  return (
    <div className="panel output-panel visible" id="outputPanel" ref={panelRef}>
      {item ? (
        <div className="judge-overview">
          {item.analysisState !== 'ok' ? (
            <div className="judge-pane degraded-banner" style={{ marginBottom: 16 }}>
              <div className="summary-kicker">Analysis State</div>
              <div className="judge-pane-text">
                {item.analysisState === 'failed'
                  ? `Analysis failed. ${item.failureReason || 'No reviewed result is available.'}`
                  : isHeuristicFallback
                    ? `Showing fallback output from ${activeProvider}. ${item.failureReason || 'A provider returned no valid structured analysis.'}`
                    : hasProviderFailure
                      ? `Analysis completed with degraded quality. ${item.failureReason || 'One or more providers reported recoverable errors.'}`
                      : `Analysis completed with degraded quality. Retrieved evidence or claim support was weak, but the structured result came from ${activeProvider}.`}
              </div>
              {providerFailures.length > 0 ? (
                <ul className="judge-blocking-list">
                  {providerFailures.map((failure, index) => (
                    <li key={index}>{failure}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
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
                <span>Provider used: {activeProvider}</span>
                <span>Total tokens: {primaryTokens}</span>
                <span>Provider cost: ${item.finalRaw.llm_metadata?.cost_usd ?? 0}</span>
                <span>Rendered from: {item.renderSource}</span>
                <span>Retrieval hits: {retrievalHits}</span>
              </div>
            </div>
            <div className="judge-pane">
              <div className="summary-kicker">RAG Grounding Diagnostics</div>
              <div className="judge-score-grid">
                <span>Products: {(result.ragDiagnostics.products ?? []).join(', ') || 'none detected'}</span>
                <span>Returned citations: {result.ragCitations.length}</span>
                <span>Retrieved hits: {retrievalHits}</span>
                <span>Failure reason: {item.failureReason || 'none'}</span>
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
