// Eski UI'dagi tokenizeCurl/parseCurl ning 1:1 porti (xatti-harakati characterization testlar bilan qotirilgan).
export interface ParsedCurl { method: string | null; url: string; headers: { name: string; value: string }[]; body: string | null; auth: string | null }

export function tokenizeCurl(str: string): string[] {
  // Qo'shni segmentlar (masalan 'it'\''s' yoki a"b"c) bitta tokenga birlashadi — POSIX shell kabi.
  const tokens: string[] = []
  let i = 0
  while (i < str.length) {
    while (i < str.length && /\s/.test(str[i])) i++
    if (i >= str.length) break
    let t = ''
    while (i < str.length && !/\s/.test(str[i])) {
      if (str[i] === "'") {
        i++
        while (i < str.length && str[i] !== "'") t += str[i++]
        i++
      } else if (str[i] === '"') {
        i++
        while (i < str.length && str[i] !== '"') {
          if (str[i] === '\\' && i + 1 < str.length) {
            i++
            const c = str[i]
            t += c === 'n' ? '\n' : c === 't' ? '\t' : c === '"' ? '"' : '\\' + c
          } else t += str[i]
          i++
        }
        i++
      } else if (str[i] === '\\' && i + 1 < str.length && str[i + 1] === "'") {
        t += "'"; i += 2
      } else t += str[i++]
    }
    tokens.push(t)
  }
  return tokens
}

const NO_VALUE = ['--compressed', '--silent', '-s', '-v', '--verbose', '-L', '--location', '--insecure', '-k', '--no-keepalive', '-i', '--include', '--http1.1', '--http2', '-f', '--fail', '-o', '--output']

export function parseCurl(raw: string): ParsedCurl | null {
  const text = raw.trim().replace(/\\\r?\n/g, ' ').replace(/\r?\n/g, ' ').trim()
  if (!/^curl\b/i.test(text)) return null
  const tokens = tokenizeCurl(text)
  const r: { method: string | null; url: string | null; headers: { name: string; value: string }[]; body: string | null; auth: string | null } = { method: null, url: null, headers: [], body: null, auth: null }
  let i = 1
  while (i < tokens.length) {
    const t = tokens[i]
    if (t === '-X' || t === '--request') r.method = (tokens[++i] || '').toUpperCase()
    else if (t === '-H' || t === '--header') {
      const h = tokens[++i] || ''; const ci = h.indexOf(':')
      if (ci > 0) r.headers.push({ name: h.slice(0, ci).trim(), value: h.slice(ci + 1).trim() })
    } else if (['-d', '--data', '--data-raw', '--data-binary', '--data-ascii', '--data-urlencode'].includes(t)) {
      r.body = tokens[++i] || ''
      if (!r.method) r.method = 'POST'
    } else if (t === '-u' || t === '--user') r.auth = 'Basic ' + btoa(tokens[++i] || '')
    else if (t === '--url') r.url = tokens[++i] || ''
    else if (t === '-G' || t === '--get') r.method = 'GET'
    else if (/^https?:\/\//i.test(t) || (!t.startsWith('-') && !r.url && t !== 'curl')) r.url = t
    else if (t.startsWith('-') && !NO_VALUE.includes(t)) {
      if (i + 1 < tokens.length && !tokens[i + 1].startsWith('-') && !/^https?:\/\//i.test(tokens[i + 1])) i++
    }
    i++
  }
  return r.url ? (r as ParsedCurl) : null
}

/** Tahrir qoralamasiga qo'llash. */
import type { RequestDraft } from './draft'
import { emptyKV } from './draft'

export function applyCurlToDraft(d: RequestDraft, p: ParsedCurl) {
  const q = p.url.indexOf('?')
  d.url = q >= 0 ? p.url.slice(0, q) : p.url
  d.params = [...(q >= 0 ? [...new URLSearchParams(p.url.slice(q + 1)).entries()].map(([key, value]) => ({ key, value, enabled: true })) : []), emptyKV()]
  d.method = p.method || 'GET'
  d.headers = []
  d.auth = { ...d.auth, type: 'none' }
  let auth = p.auth
  for (const h of p.headers) {
    const low = h.name.toLowerCase()
    if (low === 'authorization') auth = h.value
    else if (low === 'content-type') d.body.contentType = h.value
    else d.headers.push({ key: h.name, value: h.value, enabled: true })
  }
  d.headers.push(emptyKV())
  if (auth) {
    if (/^bearer /i.test(auth)) d.auth = { ...d.auth, type: 'bearer', token: auth.slice(7) }
    else if (/^basic /i.test(auth)) { try { const [u, ...pw] = atob(auth.slice(6)).split(':'); d.auth = { ...d.auth, type: 'basic', user: u, pass: pw.join(':') } } catch { d.auth = { ...d.auth, type: 'custom', custom: auth } } }
    else d.auth = { ...d.auth, type: 'custom', custom: auth }
  }
  if (p.body != null) {
    d.body.raw = p.body
    d.body.mode = /json/i.test(d.body.contentType) || /^\s*[\[{]/.test(p.body) ? 'json' : 'raw'
  }
}

import { specFromDraft } from './draft'

const sq = (s: string) => "'" + s.replace(/'/g, "'\\''") + "'"

/** Qoralamadan cURL buyrug'i (Copy as cURL). */
export function buildCurl(d: RequestDraft): string {
  const spec = specFromDraft(d)
  const qs = spec.params.filter((p: any) => p.type !== 'file').map((p: any) => `${encodeURIComponent(p.name)}=${encodeURIComponent(p.value)}`).join('&')
  const parts = [`curl -X ${spec.method} ${sq(spec.url + (qs ? '?' + qs : ''))}`]
  if (spec.authorization) parts.push(`-H ${sq('Authorization: ' + spec.authorization)}`)
  for (const h of spec.headers) parts.push(`-H ${sq(h.name + ': ' + h.value)}`)
  if (spec.content_type && spec.body) parts.push(`-H ${sq('Content-Type: ' + spec.content_type)}`)
  if (spec.body_type === 'multipart') for (const f of spec.multipart_fields) parts.push(`-F ${sq(f.name + '=' + f.value)}`)
  else if (spec.body) parts.push(`-d ${sq(spec.body)}`)
  return parts.join(' \\\n  ')
}
