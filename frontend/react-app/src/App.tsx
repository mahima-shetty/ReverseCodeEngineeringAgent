import { useCallback, useState } from 'react';
import { analyzeCodeApi } from './lib/api';
import { normalizeBlueverseResponse } from './lib/normalize';
import type { Lang, NormalizedResult } from './types';
import { CodeInputPanel } from './components/CodeInputPanel';
import { ConfigBar } from './components/ConfigBar';
import { Header } from './components/Header';
import { QuickSummary } from './components/QuickSummary';
import { ReportPanel } from './components/ReportPanel';

export default function App() {
  const [code, setCode] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [token, setToken] = useState('');
  const [currentLang, setCurrentLang] = useState<Lang>('sql');
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('Ready — configure endpoint and paste code');
  const [statusActive, setStatusActive] = useState(false);
  const [result, setResult] = useState<NormalizedResult | null>(null);

  const analyze = useCallback(async () => {
    const trimmed = code.trim();
    if (!trimmed) {
      alert('Please paste some code or upload a file first.');
      return;
    }

    setLoading(true);
    setStatusText('Sending to Blueverse agent...');
    setStatusActive(true);

    try {
      setStatusText('Agent processing code...');
      const raw = await analyzeCodeApi(trimmed, currentLang, endpoint.trim(), token.trim());
      const normalized = normalizeBlueverseResponse(raw, trimmed, currentLang);
      setResult(normalized);
      setStatusText(`Analysis complete — ${normalized.summary.linesOfCode || '?'} lines reviewed`);
      setStatusActive(false);
    } catch (err) {
      console.error(err);
      const msg = err instanceof Error ? err.message : String(err);
      setStatusText(`Error: ${msg}`);
      setStatusActive(false);
      alert(
        `Analysis failed: ${msg}\n\nIf backend is not running: cd backend && uvicorn main:app --reload --port 8000`
      );
    } finally {
      setLoading(false);
    }
  }, [code, currentLang, endpoint, token]);

  return (
    <>
      <div className="glow-orb one" />
      <div className="glow-orb two" />
      <div className="container">
        <Header />
        <ConfigBar endpoint={endpoint} token={token} onEndpointChange={setEndpoint} onTokenChange={setToken} />
        <div className="main">
          <CodeInputPanel
            code={code}
            onCodeChange={setCode}
            currentLang={currentLang}
            onLangChange={setCurrentLang}
            onAnalyze={analyze}
            loading={loading}
            statusText={statusText}
            statusActive={statusActive}
          />
          <QuickSummary result={result} />
          {result ? <ReportPanel result={result} /> : null}
        </div>
      </div>
    </>
  );
}
