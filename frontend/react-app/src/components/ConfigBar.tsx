type Props = {
  endpoint: string;
  token: string;
  onEndpointChange: (v: string) => void;
  onTokenChange: (v: string) => void;
};

export function ConfigBar({ endpoint, token, onEndpointChange, onTokenChange }: Props) {
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
        placeholder="Optional if set in backend/.env"
        style={{ flex: 1.2 }}
        value={token}
        onChange={(e) => onTokenChange(e.target.value)}
      />
    </div>
  );
}
