// Thin typed fetch wrapper around the FastAPI server.
// In dev, requests go to `/api/...` and Vite proxies them to the server.

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/agent';

const TOKEN_KEY = 'drivethru_token';
let _onUnauthorized: (() => void) | null = null;

export function onUnauthorized(cb: () => void) {
  _onUnauthorized = cb;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors come back as an array of {loc, msg, ...}.
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d?.msg === 'string' ? d.msg : JSON.stringify(d)))
      .join('; ');
  }
  return fallback;
}

async function parseBody(res: Response): Promise<unknown> {
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = { ...init?.headers, ...authHeaders() } as Record<string, string>;
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const body = await parseBody(res);
  if (!res.ok) {
    if (res.status === 401) {
      clearToken();
      _onUnauthorized?.();
    }
    const detail = (body as { detail?: unknown })?.detail ?? body;
    throw new ApiError(res.status, detail, detailToMessage(detail, res.statusText));
  }
  return body as T;
}

const jsonHeaders = { 'Content-Type': 'application/json' };

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: body === undefined ? undefined : { ...jsonHeaders, ...authHeaders() },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      headers: { ...jsonHeaders, ...authHeaders() },
      body: JSON.stringify(body),
    }),

  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      headers: { ...jsonHeaders, ...authHeaders() },
      body: JSON.stringify(body),
    }),

  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),

  // Multipart upload (FormData sets its own Content-Type boundary).
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),
};
