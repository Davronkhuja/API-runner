import type { PmRequest, RequestItem } from '../types/model'

export interface KV { key: string; value: string; enabled: boolean; description?: string; kind?: 'text' | 'file' }
import { cleanSettings, type ReqSettings } from './settings'
import { authFromPm, authHeader, authToPm, emptyAuth, type AuthDraft, type AuthType } from './auth'
export { authHeader, type AuthType }
export interface RequestDraft {
  name: string
  method: string
  url: string
  params: KV[]
  headers: KV[]
  auth: AuthDraft
  pathVars: { key: string; value: string }[]
  settings: ReqSettings
  body: { mode: 'none' | 'raw' | 'json' | 'form' | 'multipart'; raw: string; contentType: string; fields: KV[] }
}

export const emptyKV = (): KV => ({ key: '', value: '', enabled: true })

// ── URL ↔ Params ikki tomonlama sinxron ──
// URL matni to'liq (query bilan) saqlanadi; yuborishda query kesiladi va jadval manba bo'ladi.
const enc = (s: string) => encodeURIComponent(s).replace(/%7B%7B/gi, '{{').replace(/%7D%7D/gi, '}}')
const dec = (s: string) => { try { return decodeURIComponent(s.replace(/\+/g, ' ')) } catch { return s } }
export const baseUrl = (url: string) => { const i = url.indexOf('?'); return i < 0 ? url : url.slice(0, i) }
export function composeUrl(url: string, params: KV[]): string {
  const qs = params.filter(p => p.enabled && p.key.trim()).map(p => `${enc(p.key)}=${enc(p.value)}`).join('&')
  return baseUrl(url) + (qs ? '?' + qs : '')
}
/** URL'dagi query'dan qatorlar; jadvaldagi o'chirilgan (disabled) qatorlar saqlanadi. */
export function paramsFromUrl(url: string, existing: KV[]): KV[] {
  const i = url.indexOf('?')
  const fromUrl: KV[] = i < 0 ? [] : url.slice(i + 1).split('&').filter(Boolean).map(pair => {
    const e = pair.indexOf('=')
    return { key: dec(e < 0 ? pair : pair.slice(0, e)), value: e < 0 ? '' : dec(pair.slice(e + 1)), enabled: true }
  })
  // mavjud qatorlarning tavsifi/fayl turini kalit bo'yicha saqlaymiz
  const byKey = new Map(existing.filter(x => x.enabled).map(x => [x.key, x]))
  const merged = fromUrl.map(r => { const o = byKey.get(r.key); return o && (o.kind === 'file' || o.description) && o.value === r.value ? { ...o } : r })
  return [...merged, ...existing.filter(x => !x.enabled && x.key), emptyKV()]
}

export function newDraft(name = 'Yangi so\'rov'): RequestDraft {
  return {
    name, method: 'GET', url: '', params: [emptyKV()], headers: [emptyKV()],
    auth: emptyAuth('inherit'), pathVars: [], settings: {},
    body: { mode: 'none', raw: '', contentType: '', fields: [emptyKV()] },
  }
}

const withTrailing = (rows: KV[]) => (rows.length && !rows[rows.length - 1].key && !rows[rows.length - 1].value ? rows : [...rows, emptyKV()])

/** Saqlangan element -> tahrir qoralamasi. Eski (legacy) yozuv bo'lsa, undan aniq o'qiladi. */
export function draftFromItem(item: RequestItem): RequestDraft {
  const d = newDraft(item.name)
  d.settings = cleanSettings(item['x-apirunner']?.settings)
  const lg = item['x-apirunner']?.legacy
  if (lg) {
    d.method = lg.method ?? 'GET'
    d.params = withTrailing((lg.params ?? []).map((p: any) => ({ key: p.name ?? '', value: p.value ?? '', enabled: true, kind: p.type === 'file' ? 'file' : 'text' })))
    d.url = composeUrl(lg.url ?? '', d.params)
    d.pathVars = syncPathVars(d.url, [])
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
  const rawUrl = r.url?.raw ?? ''
  d.params = r.url?.query?.length || !rawUrl.includes('?') ? withTrailing((r.url?.query ?? []).map(q => ({ key: q.key, value: q.value, enabled: !q.disabled, description: q.description }))) : paramsFromUrl(rawUrl, [])
  d.url = composeUrl(r.url?.raw ?? '', d.params)
  d.pathVars = syncPathVars(d.url, r.url?.variable ?? [])
  d.headers = withTrailing((r.header ?? []).map(h => ({ key: h.key, value: h.value, enabled: !h.disabled, description: h.description })))
  d.auth = authFromPm(r.auth)

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
  const req: PmRequest = {
    method: d.method,
    header: rows(d.headers).map(h => ({ key: h.key, value: h.value, ...(h.enabled ? {} : { disabled: true }), ...(h.description ? { description: h.description } : {}) })),
    url: { raw: composeUrl(d.url, d.params), query },
  }
  const pmAuth = authToPm(d.auth)
  if (pmAuth) req.auth = pmAuth
  if (d.pathVars.length) req.url.variable = d.pathVars.map(v => ({ key: v.key, value: v.value }))
  const m = d.body.mode
  if (m === 'raw' || m === 'json') req.body = { mode: 'raw', raw: d.body.raw, options: { raw: { language: m === 'json' ? 'json' : 'text' } } }
  else if (m === 'form') req.body = { mode: 'urlencoded', urlencoded: rows(d.body.fields).map(f => ({ key: f.key, value: f.value, ...(f.enabled ? {} : { disabled: true }) })) }
  else if (m === 'multipart') req.body = { mode: 'formdata', formdata: rows(d.body.fields).map(f => ({ key: f.key, value: f.value, type: f.kind === 'file' ? 'file' : 'text', ...(f.enabled ? {} : { disabled: true }) })) }
  return req
}

/** Saqlashda `x-apirunner` kengaytmasi (faqat bo'sh bo'lmagan sozlamalar). */
export const extFromDraft = (d: RequestDraft) => { const s = cleanSettings(d.settings); return Object.keys(s).length ? { settings: s } : {} }

/** Qoralama -> backend engine spec (/run_one, /run). Faqat yoqilgan qatorlar. */
export function specFromDraft(d: RequestDraft, vars: Record<string, string> = {}) {
  const on = (kv: KV[]) => kv.filter(x => x.enabled && x.key.trim())
  const spec: Record<string, any> = {
    method: d.method, url: baseUrl(d.url), authorization: authHeader(d.auth),
    params: on(d.params).map(p => ({ name: p.key, value: p.value, ...(p.kind === 'file' ? { type: 'file' } : {}) })),
    headers: on(d.headers).map(h => ({ name: h.key, value: h.value })),
    body: '', content_type: d.body.contentType, body_type: 'raw', env_vars: vars,
    path_variables: d.pathVars.filter(v => v.key).map(v => ({ name: v.key, value: v.value })),
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

/** URL yo'lidagi `:name` (sxema/host/port/query tashqarida) nomlari, takrorlarsiz. */
export function pathVarNames(url: string): string[] {
  const m = /^([a-zA-Z][\w+.-]*:\/\/[^/?#]*)?([^?#]*)/.exec(url)
  const path = m?.[2] ?? ''
  return [...new Set([...path.matchAll(/(?<=\/):([A-Za-z_][\w-]*)/g)].map(x => x[1]))]
}
/** URL o'zgarganda jadvalni moslaydi; mavjud qiymatlar saqlanadi. */
export function syncPathVars(url: string, existing: { key: string; value: string }[]) {
  const by = new Map(existing.map(v => [v.key, v.value]))
  return pathVarNames(url).map(k => ({ key: k, value: by.get(k) ?? '' }))
}
