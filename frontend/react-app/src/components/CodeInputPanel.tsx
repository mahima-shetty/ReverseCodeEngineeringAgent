import { useCallback, useRef, useState } from 'react';
import type { AnalysisInput, Lang } from '../types';

const LANG_OPTIONS: { id: Lang; label: string }[] = [
  { id: 'sql', label: 'SQL / PL/SQL' },
  { id: 'groovy', label: 'Groovy' },
  { id: 'bip', label: 'BI Publisher' },
  { id: 'oic', label: 'OIC / Integration Flow' },
  { id: 'shell', label: 'Shell Script' },
  { id: 'auto', label: 'Auto-detect' },
];

const EXT_MAP: Record<string, Lang> = {
  sql: 'sql',
  pls: 'sql',
  pks: 'sql',
  pkb: 'sql',
  fnc: 'sql',
  prc: 'sql',
  groovy: 'groovy',
  bip: 'bip',
  xdo: 'bip',
  xdm: 'bip',
  rtf: 'bip',
  xml: 'oic',
  json: 'oic',
  sh: 'shell',
  bash: 'shell',
  ksh: 'shell',
};

type Props = {
  inputs: AnalysisInput[];
  onInputsChange: (inputs: AnalysisInput[]) => void;
  onAnalyze: () => void;
  loading: boolean;
  statusText: string;
  statusActive: boolean;
  onAddInput: () => void;
};

export function CodeInputPanel({
  inputs,
  onInputsChange,
  onAnalyze,
  loading,
  statusText,
  statusActive,
  onAddInput,
}: Props) {
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const updateInput = useCallback(
    (id: string, patch: Partial<AnalysisInput>) => {
      onInputsChange(inputs.map((item) => (item.id === id ? { ...item, ...patch } : item)));
    },
    [inputs, onInputsChange]
  );

  const removeInput = useCallback(
    (id: string) => {
      if (inputs.length === 1) return;
      onInputsChange(inputs.filter((item) => item.id !== id));
    },
    [inputs, onInputsChange]
  );

  const loadFiles = useCallback(
    async (files: FileList | File[]) => {
      const loaded = await Promise.all(
        Array.from(files).map(
          (file) =>
            new Promise<AnalysisInput>((resolve) => {
              const reader = new FileReader();
              reader.onload = () => {
                const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
                const language = EXT_MAP[ext] ?? 'auto';
                resolve({
                  id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${file.name}`,
                  label: file.name,
                  code: String(reader.result ?? ''),
                  language,
                });
              };
              reader.readAsText(file);
            })
        )
      );

      const nonEmpty = loaded.filter((item) => item.code.trim());
      if (nonEmpty.length > 0) {
        onInputsChange([...inputs, ...nonEmpty]);
      }
    },
    [inputs, onInputsChange]
  );

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files?.length) void loadFiles(files);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files?.length) void loadFiles(files);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <div className="dot" />
          BATCH INPUTS
        </div>
        <button type="button" className="secondary-btn" onClick={onAddInput}>
          + Add Input
        </button>
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
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".sql,.pls,.pks,.pkb,.fnc,.prc,.groovy,.bip,.xdo,.xdm,.rtf,.xml,.json,.sh,.bash,.ksh,.txt"
          onChange={onFileChange}
        />
        <p>
          <span>Upload multiple files</span> or build a batch manually
        </p>
        <div className="file-name">Each file becomes its own review item.</div>
      </div>

      <div className="batch-input-list">
        {inputs.map((input, index) => (
          <div key={input.id} className="batch-input-card">
            <div className="batch-input-header">
              <div className="batch-input-title">Input {index + 1}</div>
              <div className="batch-input-actions">
                <select
                  className="lang-select"
                  value={input.language}
                  onChange={(e) => updateInput(input.id, { language: e.target.value as Lang })}
                >
                  {LANG_OPTIONS.map(({ id, label }) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="secondary-btn danger"
                  disabled={inputs.length === 1}
                  onClick={() => removeInput(input.id)}
                >
                  Remove
                </button>
              </div>
            </div>

            <input
              className="config-input"
              type="text"
              placeholder="Optional label, file name, or use-case"
              value={input.label}
              onChange={(e) => updateInput(input.id, { label: e.target.value })}
            />

            <textarea
              className="code-area batch"
              placeholder="// Paste code, prompt, or analysis input here"
              value={input.code}
              onChange={(e) => updateInput(input.id, { code: e.target.value })}
            />
          </div>
        ))}
      </div>

      <button type="button" className={`analyze-btn ${loading ? 'loading' : ''}`} disabled={loading} onClick={onAnalyze}>
        <div className="spinner" />
        <span className="btn-text">{loading ? 'Running batch...' : 'Run Primary + Judge Flow'}</span>
      </button>

      <div className="status-bar">
        <div className={`status-dot ${statusActive ? 'active' : ''}`} />
        <span>{statusText}</span>
      </div>
    </div>
  );
}
