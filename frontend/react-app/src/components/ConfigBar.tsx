type Props = {
  endpoint: string;
  token: string;
  judgeToken: string;
  benchmarkJudgeToken: string;
  onEndpointChange: (v: string) => void;
  onTokenChange: (v: string) => void;
  onJudgeTokenChange: (v: string) => void;
  onBenchmarkJudgeTokenChange: (v: string) => void;
};

export function ConfigBar({
  endpoint,
  token,
  judgeToken,
  benchmarkJudgeToken,
  onEndpointChange,
  onTokenChange,
  onJudgeTokenChange,
  onBenchmarkJudgeTokenChange,
}: Props) {
  return (
    <div className="config-bar">
      <label>ENDPOINT</label>
      <input
        className="config-input"
        type="text"
        placeholder="Leave empty to use backend/.env BLUEVERSE_URL"
        value={endpoint}
        onChange={(e) => onEndpointChange(e.target.value)}
      />
      <div className="config-divider" />
      <label>BEARER TOKEN</label>
      <input
        className="config-input"
        type="password"
        placeholder="Primary agent token"
        style={{ flex: 1 }}
        value={token}
        onChange={(e) => onTokenChange(e.target.value)}
      />
      <div className="config-divider" />
      <label>JUDGE TOKEN</label>
      <input
        className="config-input"
        type="password"
        placeholder="Required for evaluator agent"
        style={{ flex: 1 }}
        value={judgeToken}
        onChange={(e) => onJudgeTokenChange(e.target.value)}
      />
      <div className="config-divider" />
      <label>BENCHMARK JUDGE TOKEN</label>
      <input
        className="config-input"
        type="password"
        placeholder="Optional separate benchmark judge token"
        style={{ flex: 1 }}
        value={benchmarkJudgeToken}
        onChange={(e) => onBenchmarkJudgeTokenChange(e.target.value)}
      />
    </div>
  );
}
