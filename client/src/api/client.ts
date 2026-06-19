// Thin typed fetch wrapper around the FastAPI server.
// In dev, requests go to `/api/...` and Vite proxies them to the server.

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  const body = await parseBody(res);
  if (!res.ok) {
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
      headers: body === undefined ? undefined : jsonHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      headers: jsonHeaders,
      body: JSON.stringify(body),
    }),

  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      headers: jsonHeaders,
      body: JSON.stringify(body),
    }),

  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),

  // Multipart upload (FormData sets its own Content-Type boundary).
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),
};
