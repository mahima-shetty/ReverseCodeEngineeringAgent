import fs from 'node:fs';
import path from 'node:path';

const DEFAULT_API_BASE = process.env.CODELENS_API_BASE || 'http://127.0.0.1:8000';
const BACKEND_ENV_PATH = path.resolve(process.cwd(), 'backend', '.env');

let cachedBackendEnv = null;

function loadBackendEnv() {
  if (cachedBackendEnv) return cachedBackendEnv;
  const values = {};
  if (!fs.existsSync(BACKEND_ENV_PATH)) {
    cachedBackendEnv = values;
    return values;
  }

  const content = fs.readFileSync(BACKEND_ENV_PATH, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    const raw = trimmed.slice(eq + 1).trim();
    const value = raw.replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1');
    values[key] = value;
  }

  cachedBackendEnv = values;
  return values;
}

function requireEnv(name) {
  const backendEnv = loadBackendEnv();
  const value = process.env[name] || backendEnv[name];
  if (!value || !value.trim()) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value.trim();
}

export default class CodeLensApiProvider {
  id() {
    return 'codelens-api';
  }

  async callApi(_prompt, context) {
    const vars = context?.vars || {};
    const backendEnv = loadBackendEnv();
    const apiBase = (vars.apiBase || DEFAULT_API_BASE).replace(/\/$/, '');
    const endpoint = vars.endpoint || process.env.BLUEVERSE_URL || backendEnv.BLUEVERSE_URL || '';
    const token = vars.token || process.env.BLUEVERSE_BEARER_TOKEN || backendEnv.BLUEVERSE_BEARER_TOKEN || '';
    const judgeToken =
      vars.judgeToken ||
      process.env.BLUEVERSE_JUDGE_BEARER_TOKEN ||
      backendEnv.BLUEVERSE_JUDGE_BEARER_TOKEN ||
      '';

    if (!judgeToken) {
      throw new Error(
        'Missing judge token. Set BLUEVERSE_JUDGE_BEARER_TOKEN in backend/.env or export it before running Promptfoo.'
      );
    }

    const payload = {
      endpoint,
      token,
      judge_token: judgeToken,
      session_id: vars.sessionId || `promptfoo-${Date.now()}`,
      inputs: [
        {
          id: vars.id || 'promptfoo-input-1',
          label: vars.label || 'Promptfoo Input',
          language: vars.language || 'auto',
          code: vars.code || '',
        },
      ],
    };

    const response = await fetch(`${apiBase}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    const text = await response.text();
    let json;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }

    if (!response.ok) {
      throw new Error(
        `CodeLens API error ${response.status}: ${json?.detail || text || 'Unknown error'}`
      );
    }

    const item = json?.items?.[0];
    if (!item) {
      throw new Error('CodeLens API returned no analysis items');
    }

    return {
      output: JSON.stringify(item),
      tokenUsage:
        item?.judge_evaluation?.provider_metadata?.usage || item?.final_output?.llm_metadata?.usage,
      metadata: {
        final_status: item.final_status,
        analysis_state: item.analysis_state,
        render_source: item.render_source,
      },
    };
  }
}
