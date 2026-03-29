import { useCallback, useRef, useState } from 'react';
import type { Lang } from '../types';

const LANG_OPTIONS: { id: Lang; label: string }[] = [
  { id: 'sql', label: 'SQL / PL/SQL' },
  { id: 'groovy', label: 'Groovy' },
  { id: 'oic', label: 'OIC / BI Flow' },
  { id: 'shell', label: 'Shell Script' },
  { id: 'auto', label: 'Auto-detect' },
];

const EXT_MAP: Record<string, Lang> = {
  sql: 'sql',
  groovy: 'groovy',
  xml: 'oic',
  json: 'oic',
  sh: 'shell',
};

type Props = {
  code: string;
  onCodeChange: (v: string) => void;
  currentLang: Lang;
  onLangChange: (lang: Lang) => void;
  onAnalyze: () => void;
  loading: boolean;
  statusText: string;
  statusActive: boolean;
};

export function CodeInputPanel({
  code,
  onCodeChange,
  currentLang,
  onLangChange,
  onAnalyze,
  loading,
  statusText,
  statusActive,
}: Props) {
  const [fileName, setFileName] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const applyLangFromExt = useCallback(
    (name: string) => {
      const ext = name.split('.').pop()?.toLowerCase() ?? '';
      const lang = EXT_MAP[ext];
      if (lang) onLangChange(lang);
    },
    [onLangChange]
  );

  const loadFile = useCallback(
    (file: File) => {
      setFileName(`📎 ${file.name}`);
      applyLangFromExt(file.name);
      const reader = new FileReader();
      reader.onload = () => onCodeChange(String(reader.result ?? ''));
      reader.readAsText(file);
    },
    [applyLangFromExt, onCodeChange]
  );

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) loadFile(file);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) loadFile(file);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" />
          CODE INPUT
        </div>
      </div>

      <div className="lang-tabs">
        {LANG_OPTIONS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`lang-tab ${currentLang === id ? 'active' : ''}`}
            onClick={() => onLangChange(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        className={`upload-zone ${dragOver ? 'dragover' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <input ref={fileRef} type="file" accept=".sql,.groovy,.xml,.json,.sh,.txt" onChange={onFileChange} />
        <p>
          ⬆ <span>Drop file here</span> or click to upload
        </p>
        <div className="file-name">{fileName}</div>
      </div>

      <textarea
        className="code-area"
        placeholder={
          '// Or paste your code directly here...\n// Supports: SQL, PL/SQL, Groovy, OIC/BI XML/JSON, Shell scripts'
        }
        value={code}
        onChange={(e) => onCodeChange(e.target.value)}
      />

      <button type="button" className={`analyze-btn ${loading ? 'loading' : ''}`} disabled={loading} onClick={onAnalyze}>
        <div className="spinner" />
        <span className="btn-text">{loading ? 'Analyzing...' : '⚡ Analyze Code'}</span>
      </button>

      <div className="status-bar">
        <div className={`status-dot ${statusActive ? 'active' : ''}`} />
        <span>{statusText}</span>
      </div>
    </div>
  );
}
