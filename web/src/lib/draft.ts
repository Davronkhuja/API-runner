import type { PmRequest, RequestItem } from '../types/model'

export interface KV { key: string; value: string; enabled: boolean; description?: string; kind?: 'text' | 'file' }
export type AuthType = 'none' | 'bearer' | 'basic' | 'custom'
export interface RequestDraft {
  name: string
  method: string
  url: string
  params: KV[]
  headers: KV[]
  auth: { type: AuthType; token: string; user: string; pass: string; custom: string }
  body: { mode: 'none' | 'raw' | 'json' | 'form' | 'multipart'; raw: string; contentType: string; fields: KV[] }
}

export const emptyKV = (): KV => ({ key: '', value: '', enabled: true })

export function newDraft(name = 'Yangi so\'rov'): RequestDraft {
  return {
    name, method: 'GET', url: '', params: [emptyKV()], headers: [emptyKV()],
    auth: { type: 'none', token: '', user: '', pass: '', custom: '' },
    body: { mode: 'none', raw: '', contentType: '', fields: [emptyKV()] },
  }
}

const withTrailing = (rows: KV[]) => (rows.length && !rows[rows.length - 1].key && !rows[rows.length - 1].value ? rows : [...rows, emptyKV()])

/** Saqlangan element -> tahrir qoralamasi. Eski (legacy) yozuv bo'lsa, undan aniq o'qiladi. */
export function draftFromItem(item: RequestItem): RequestDraft {
  const d = newDraft(item.name)
  const lg = item['x-apirunner']?.legacy
  if (lg) {
    d.method = lg.method ?? 'GET'
    d.url = lg.url ?? ''
    d.params = withTrailing((lg.params ?? []).map((p: any) => ({ key: p.name ?? '', value: p.value ?? '', enabled: true, kind: p.type === 'file' ? 'file' : 'text' })))
    d.headers = withTrailing((lg.headers ?? []).map((h: any) => ({ key: h.name ?? '', value: h.value ?? '', enabled: true })))
    const a: string = (lg.authorization ?? '').trim()
    if (a.toLowerCase().startsWith('bearer ')) d.auth = { ...d.auth, type: 'bearer', token: a.slice(7) }
    else if (a.toLowerCase().startsWith('basic ')) {
      try { const [u, ...p] = atob(a.slice(6)).split(':'); d.auth = { ...d.auth, type: 'basic', user: u, pass: p.join(':') } }
      catch { d.auth = { ...d.auth, type: 'custom', custom: a } }
    } else if (a) d.auth = { ...d.auth, type: 'custom', custom: a }
    const bt = lg.body_type ?? 'raw'
    d.body.contentType = lg.content_type ?? ''
    if (bt === 'multipart') { d.body.mode = 'multipart'; d.body.fields = withTrailing((lg.multipart_fields ?? []).map((f: any) => ({ key: f.name ?? '', value: f.value ?? '', enabled: true }))) }
    else if (lg.body) { d.body.mode = bt === 'json' ? 'json' : bt === 'form' ? 'form' : 'raw'; d.body.raw = lg.body }
    return d
  }
  const r: PmRequest = item.request
  d.method = r.method
  d.url = (r.url?.raw ?? '').split('?')[0]
  d.params = withTrailing((r.url?.query ?? []).map(q => ({ key: q.key, value: q.value, enabled: !q.disabled, description: q.description })))
  d.headers = withTrailing((r.header ?? []).map(h => ({ key: h.key, value: h.value, enabled: !h.disabled, description: h.description })))
  if (r.auth?.type === 'bearer') d.auth = { ...d.auth, type: 'bearer', token: r.auth.bearer?.find((x: any) => x.key === 'token')?.value ?? '' }
  const b = r.body
  if (b?.mode === 'raw') { d.body.mode = b.options?.raw?.language === 'json' ? 'json' : 'raw'; d.body.raw = b.raw ?? '' }
  else if (b?.mode === 'urlencoded') { d.body.mode = 'form'; d.body.fields = withTrailing((b.urlencoded ?? []).map(q => ({ key: q.key, value: q.value, enabled: !q.disabled }))) }
  else if (b?.mode === 'formdata') d.body.fields = withTrailing((b.formdata ?? []).map(f => ({ key: f.key, value: f.value ?? f.src ?? '', enabled: !f.disabled, kind: f.type })))
  if (b?.mode === 'formdata') d.body.mode = 'multipart'
  return d
}

/** Qoralama -> Postman so'rovi (saqlash uchun). */
export function requestFromDraft(d: RequestDraft): PmRequest {
  const rows = (kv: KV[]) => kv.filter(x => x.key || x.value)
  const query = rows(d.params).map(p => ({ key: p.key, value: p.value, ...(p.enabled ? {} : { disabled: true }), ...(p.description ? { description: p.description } : {}) }))
  const qs = rows(d.params).filter(p => p.enabled).map(p => `${encodeURIComponent(p.key)}=${encodeURIComponent(p.value)}`).join('&')
  const req: PmRequest = {
    method: d.method,
    header: rows(d.headers).map(h => ({ key: h.key, value: h.value, ...(h.enabled ? {} : { disabled: true }), ...(h.description ? { description: h.description } : {}) })),
    url: { raw: d.url + (qs ? '?' + qs : ''), query },
  }
  if (d.auth.type === 'bearer') req.auth = { type: 'bearer', bearer: [{ key: 'token', value: d.auth.token, type: 'string' }] }
  else if (d.auth.type === 'basic') req.auth = { type: 'basic', basic: [{ key: 'username', value: d.auth.user }, { key: 'password', value: d.auth.pass }] }
  else if (d.auth.type === 'custom') req.header.push({ key: 'Authorization', value: d.auth.custom })
  const m = d.body.mode
  if (m === 'raw' || m === 'json') req.body = { mode: 'raw', raw: d.body.raw, options: { raw: { language: m === 'json' ? 'json' : 'text' } } }
  else if (m === 'form') req.body = { mode: 'urlencoded', urlencoded: rows(d.body.fields).map(f => ({ key: f.key, value: f.value, ...(f.enabled ? {} : { disabled: true }) })) }
  else if (m === 'multipart') req.body = { mode: 'formdata', formdata: rows(d.body.fields).map(f => ({ key: f.key, value: f.value, type: f.kind === 'file' ? 'file' : 'text', ...(f.enabled ? {} : { disabled: true }) })) }
  return req
}

export function authHeader(a: RequestDraft['auth']): string {
  if (a.type === 'bearer') return a.token ? 'Bearer ' + a.token : ''
  if (a.type === 'basic') return a.user || a.pass ? 'Basic ' + btoa(unescape(encodeURIComponent(`${a.user}:${a.pass}`))) : ''
  if (a.type === 'custom') return a.custom
  return ''
}

/** Qoralama -> backend engine spec (/run_one, /run). Faqat yoqilgan qatorlar. */
export function specFromDraft(d: RequestDraft, vars: Record<string, string> = {}) {
  const on = (kv: KV[]) => kv.filter(x => x.enabled && x.key.trim())
  const spec: Record<string, any> = {
    method: d.method, url: d.url, authorization: authHeader(d.auth),
    params: on(d.params).map(p => ({ name: p.key, value: p.value, ...(p.kind === 'file' ? { type: 'file' } : {}) })),
    headers: on(d.headers).map(h => ({ name: h.key, value: h.value })),
    body: '', content_type: d.body.contentType, body_type: 'raw', env_vars: vars,
  }
  const m = d.body.mode
  if (m === 'raw' || m === 'json') { spec.body = d.body.raw; spec.body_type = m === 'json' ? 'json' : 'raw' }
  else if (m === 'form') {
    spec.body_type = 'form'
    spec.body = on(d.body.fields).map(f => `${encodeURIComponent(f.key)}=${encodeURIComponent(f.value)}`).join('&')
    spec.content_type ||= 'application/x-www-form-urlencoded'
  } else if (m === 'multipart') {
    spec.body_type = 'multipart'
    spec.multipart_fields = on(d.body.fields).map(f => ({ name: f.key, value: f.value }))
  }
  return spec
}
