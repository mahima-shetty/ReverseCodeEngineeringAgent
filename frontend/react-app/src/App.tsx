import { useCallback, useEffect, useMemo, useState } from 'react';
import { analyzeCodeApi, evaluateBenchmarkApi, getLatestBenchmarkApi } from './lib/api';
import { normalizeBatchItem, normalizeBenchmarkEvaluation } from './lib/normalize';
import type {
  AnalysisInput,
  BatchAnalysisItem,
  BatchAnalysisSummary,
  BenchmarkEvaluationResult,
  BenchmarkSampleResult,
} from './types';
import { PersonaProvider } from './context/PersonaContext';
import { BatchResultsPanel } from './components/BatchResultsPanel';
import { CodeInputPanel } from './components/CodeInputPanel';
import { ConfigBar } from './components/ConfigBar';
import { EvaluationDashboard } from './components/EvaluationDashboard';
import { EvidenceDetailPanel } from './components/EvidenceDetailPanel';
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
  const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkEvaluationResult | null>(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [selectedBenchmarkCaseId, setSelectedBenchmarkCaseId] = useState<string | null>(null);

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0] ?? null,
    [items, selectedId]
  );
  const selectedBenchmarkSample = useMemo<BenchmarkSampleResult | null>(
    () => benchmarkResult?.sampleResults.find((item) => item.caseId === selectedBenchmarkCaseId)
      ?? benchmarkResult?.sampleResults[0]
      ?? null,
    [benchmarkResult, selectedBenchmarkCaseId]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadLatestBenchmark() {
      try {
        const raw = await getLatestBenchmarkApi();
        if (!raw || cancelled) return;
        const normalized = normalizeBenchmarkEvaluation(raw);
        setBenchmarkResult(normalized);
        setSelectedBenchmarkCaseId(normalized.sampleResults[0]?.caseId ?? null);
      } catch (err) {
        console.error('Could not load latest benchmark', err);
      }
    }

    void loadLatestBenchmark();
    return () => {
      cancelled = true;
    };
  }, []);

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

      const totalSecurity = normalizedItems.reduce((sum, item) => sum + item.finalResult.security.issues.length, 0);
      const totalAntiPatterns = normalizedItems.reduce((sum, item) => sum + item.finalResult.antiPatterns.length, 0);
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

  const runBenchmark = useCallback(async () => {
    if (!judgeToken.trim()) {
      alert('Judge token is required before benchmark results can be reviewed.');
      return;
    }

    setBenchmarkLoading(true);
    try {
      const raw = await evaluateBenchmarkApi(endpoint.trim(), token.trim(), judgeToken.trim());
      const normalized = normalizeBenchmarkEvaluation(raw);
      setBenchmarkResult(normalized);
      setSelectedBenchmarkCaseId(normalized.sampleResults[0]?.caseId ?? null);
    } catch (err) {
      console.error(err);
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Benchmark failed: ${msg}`);
    } finally {
      setBenchmarkLoading(false);
    }
  }, [endpoint, judgeToken, token]);

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
          {selectedItem ? <ReportPanel result={selectedItem.finalResult} item={selectedItem} /> : null}
        </div>
        <div className="benchmark-section">
          <EvaluationDashboard
            result={benchmarkResult}
            selectedCaseId={selectedBenchmarkCaseId}
            onSelectCase={setSelectedBenchmarkCaseId}
            onRunEvaluation={runBenchmark}
            loading={benchmarkLoading}
          />
          <EvidenceDetailPanel sample={selectedBenchmarkSample} />
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
