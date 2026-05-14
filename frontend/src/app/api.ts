export const DEFAULT_API_BASE_URL = "https://andrew418-crypto-research-agent.hf.space";

const RESPONSE_BODY_PREVIEW_LENGTH = 500;

export function getApiBaseUrl() {
  const configured = (import.meta.env.VITE_API_URL || "").trim().replace(/\/+$/, "");

  if (configured) {
    return configured;
  }

  return import.meta.env.PROD ? DEFAULT_API_BASE_URL : "";
}

async function parseErrorResponse(res: Response, label: string) {
  const body = await res.text().catch(() => "");
  const bodyPreview = body ? ` ${body.slice(0, RESPONSE_BODY_PREVIEW_LENGTH)}` : "";
  return new Error(`${label}: HTTP ${res.status} ${res.statusText || ""}${bodyPreview}`);
}

function formatFetchError(error: unknown, label: string, url: string) {
  const message = error instanceof Error ? error.message : String(error);
  return new Error(`${label}: network or CORS error while requesting ${url}. ${message}`);
}

export async function requestJson<T>(path: string, label: string, init?: RequestInit): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = path.startsWith("http") ? path : `${baseUrl}${path}`;
  const res = await fetch(url, init).catch((error) => {
    throw formatFetchError(error, label, url);
  });

  if (!res.ok) {
    throw await parseErrorResponse(res, label);
  }

  return res.json();
}
