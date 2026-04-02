import { useCallback, useMemo, useState } from 'react';
import { analyzeCodeApi } from './lib/api';
import { normalizeBatchItem } from './lib/normalize';
import type { AnalysisInput, BatchAnalysisItem, BatchAnalysisSummary } from './types';
import { PersonaProvider } from './context/PersonaContext';
import { BatchResultsPanel } from './components/BatchResultsPanel';
import { CodeInputPanel } from './components/CodeInputPanel';
import { ConfigBar } from './components/ConfigBar';
import { Header } from './components/Header';
import { QuickSummary } from './components/QuickSummary';
import { ReportPanel } from './components/ReportPanel';

function createInput(label = ''): AnalysisInput {
  return {
    id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
    label,
    code: '',
    language: 'auto',
  };
}

function getSessionId(): string {
  const key = 'codelens_session_id';
  const existing = globalThis.localStorage?.getItem(key);
  if (existing) return existing;
  const created = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  globalThis.localStorage?.setItem(key, created);
  return created;
}

function AppInner() {
  const [inputs, setInputs] = useState<AnalysisInput[]>([createInput('Input 1')]);
  const [endpoint, setEndpoint] = useState('');
  const [token, setToken] = useState('');
  const [judgeToken, setJudgeToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('Ready - configure tokens and add one or more inputs');
  const [statusActive, setStatusActive] = useState(false);
  const [sessionId] = useState(getSessionId);
  const [items, setItems] = useState<BatchAnalysisItem[]>([]);
  const [summary, setSummary] = useState<BatchAnalysisSummary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0] ?? null,
    [items, selectedId]
  );

  const addInput = useCallback(() => {
    setInputs((current) => [...current, createInput(`Input ${current.length + 1}`)]);
  }, []);

  const analyze = useCallback(async () => {
    const prepared = inputs
      .map((item, index) => ({
        ...item,
        label: item.label.trim() || `Input ${index + 1}`,
        code: item.code.trim(),
      }))
      .filter((item) => item.code);

    if (prepared.length === 0) {
      alert('Add at least one non-empty input first.');
      return;
    }
    if (!judgeToken.trim()) {
      alert('Judge token is required before results can be reviewed.');
      return;
    }

    setLoading(true);
    setStatusActive(true);
    setStatusText(`Reviewing ${prepared.length} input(s) for findings...`);

    try {
      const raw = await analyzeCodeApi(prepared, endpoint.trim(), token.trim(), judgeToken.trim(), sessionId);
      const normalizedItems = raw.items.map((item) => normalizeBatchItem(item));
      setItems(normalizedItems);
      setSummary(raw.summary);
      setSelectedId(normalizedItems[0]?.id ?? null);

      const totalSecurity = normalizedItems.reduce((sum, item) => sum + item.primaryResult.security.issues.length, 0);
      const totalAntiPatterns = normalizedItems.reduce((sum, item) => sum + item.primaryResult.antiPatterns.length, 0);
      setStatusText(
        `Review complete - ${totalSecurity} security issue(s) and ${totalAntiPatterns} anti-pattern(s) found across ${normalizedItems.length} input(s)`
      );
      setStatusActive(false);
    } catch (err) {
      console.error(err);
      const msg = err instanceof Error ? err.message : String(err);
      setStatusText(`Error: ${msg}`);
      setStatusActive(false);
      alert(`Analysis failed: ${msg}\n\nIf backend is not running: cd backend && uvicorn main:app --reload --port 8000`);
    } finally {
      setLoading(false);
    }
  }, [endpoint, inputs, judgeToken, sessionId, token]);

  return (
    <>
      <div className="glow-orb one" />
      <div className="glow-orb two" />
      <div className="container">
        <Header />
        <ConfigBar
          endpoint={endpoint}
          token={token}
          judgeToken={judgeToken}
          onEndpointChange={setEndpoint}
          onTokenChange={setToken}
          onJudgeTokenChange={setJudgeToken}
        />
        <div className="main">
          <CodeInputPanel
            inputs={inputs}
            onInputsChange={setInputs}
            onAnalyze={analyze}
            loading={loading}
            statusText={statusText}
            statusActive={statusActive}
            onAddInput={addInput}
          />
          <QuickSummary summary={summary} selectedItem={selectedItem} />
          <BatchResultsPanel items={items} selectedId={selectedItem?.id ?? null} onSelect={setSelectedId} />
          {selectedItem ? <ReportPanel result={selectedItem.primaryResult} item={selectedItem} /> : null}
        </div>
      </div>
    </>
  );
}

export default function App() {
  return (
    <PersonaProvider>
      <AppInner />
    </PersonaProvider>
  );
}
