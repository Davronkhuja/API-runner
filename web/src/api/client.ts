declare global { interface Window { __API_TOKEN__?: string } }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export const token = () => window.__API_TOKEN__ ?? ''

export async function api<T = any>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-Session-Token', token())
  let body = init.body
  if (init.json !== undefined) { headers.set('Content-Type', 'application/json'); body = JSON.stringify(init.json) }
  const r = await fetch(path, { ...init, headers, body })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new ApiError(r.status, (data as any).error ?? `HTTP ${r.status}`)
  return data as T
}

/** Sahifa yopilayotganda yuboriladigan PUT (keepalive: navigatsiyadan keyin ham yetib boradi). */
export function keepalivePut(path: string, json: unknown) {
  try {
    fetch(path, { method: 'PUT', keepalive: true, headers: { 'Content-Type': 'application/json', 'X-Session-Token': token() }, body: JSON.stringify(json) }).catch(() => {})
  } catch { /* sahifa yopilmoqda */ }
}

export const get = <T = any>(p: string) => api<T>(p)
export const post = <T = any>(p: string, json?: unknown) => api<T>(p, { method: 'POST', json })
export const put = <T = any>(p: string, json?: unknown) => api<T>(p, { method: 'PUT', json })
export const patch = <T = any>(p: string, json?: unknown) => api<T>(p, { method: 'PATCH', json })
export const del = <T = any>(p: string) => api<T>(p, { method: 'DELETE' })

/** SSE: EventSource sarlavha qo'ya olmaydi, shuning uchun token query'da. */
export const eventSource = (path: string) =>
  new EventSource(path + (path.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token()))
