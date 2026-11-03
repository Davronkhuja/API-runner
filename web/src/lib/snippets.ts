/** Code snippet generatori: bitta normallashgan so'rovdan 9 til/kutubxona uchun kod. */
import type { RequestDraft } from './draft'
import { resolveVars } from './oauth'
import { flatVars, specFor } from './scope'

export type Body = { type: 'none' } | { type: 'text'; text: string } | { type: 'multipart'; fields: [string, string][] }
export interface SnipReq { method: string; url: string; headers: [string, string][]; body: Body; notes: string[] }

export const LANGS = [
  ['curl', 'cURL'], ['python', 'Python — requests'], ['fetch', 'JavaScript — fetch'], ['axios', 'JavaScript — axios'], ['node', 'Node.js — http'],
  ['go', 'Go — net/http'], ['php', 'PHP — cURL'], ['java', 'Java — OkHttp'], ['csharp', 'C# — HttpClient'],
] as const
export type Lang = (typeof LANGS)[number][0]

/** Qoralama + meros auth + o'zgaruvchilar → normallashgan so'rov (o'zgaruvchilar qiymat bilan almashtirilgan). */
export function snipReqFromDraft(d: RequestDraft, ref: string | null): SnipReq {
  const spec = specFor(d, ref)
  const vars = flatVars(ref)
  const R = (s: string) => resolveVars(String(s ?? ''), vars)
  const notes: string[] = []
  const headers: [string, string][] = []
  const query: [string, string][] = (spec.params as any[]).filter(p => p.type !== 'file').map(p => [R(p.name), R(p.value)])
  const cfg = spec.auth_config
  if (spec.authorization) headers.push(['Authorization', R(spec.authorization)])
  if (cfg?.type === 'apikey' && cfg.key) (cfg.in === 'query' ? query : headers).push([R(cfg.key), R(cfg.value ?? '')])
  else if (cfg) notes.push(`${cfg.type.toUpperCase()} auth so'rov yuborilganda hosil qilinadi (imzo/token/challenge) — kodga kiritilmagan`)
  for (const h of spec.headers as any[]) headers.push([R(h.name), R(h.value)])
  if (spec.body_file) notes.push(`Binary body: ${R(spec.body_file).split('/').pop()} fayli so'rov tanasi sifatida yuboriladi — kodga kiritilmagan`)
  let body: Body = { type: 'none' }
  if (spec.body_type === 'multipart') body = { type: 'multipart', fields: (spec.multipart_fields as any[]).map(f => [R(f.name), R(f.value)]) }
  else if (spec.body) {
    body = { type: 'text', text: R(spec.body) }
    const ct = spec.content_type || (spec.body_type === 'json' ? 'application/json' : '')
    if (ct && !headers.some(([k]) => k.toLowerCase() === 'content-type')) headers.push(['Content-Type', R(ct)])
  }
  const qs = query.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
  const base = R(spec.url)
  return { method: spec.method, url: base + (qs ? (base.includes('?') ? '&' : '?') + qs : ''), headers, body, notes }
}

const J = (s: string) => JSON.stringify(s)
const sq = (s: string) => "'" + s.replace(/'/g, "'\\''") + "'"
const phpq = (s: string) => "'" + s.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'"
const pyDict = (h: [string, string][]) => '{\n' + h.map(([k, v]) => `    ${J(k)}: ${J(v)},`).join('\n') + '\n}'
const jsObj = (h: [string, string][], ind = '  ') => '{\n' + h.map(([k, v]) => `${ind}${J(k)}: ${J(v)},`).join('\n') + `\n${ind.slice(2)}}`
const withNotes = (r: SnipReq, c: string) => (r.notes.length ? r.notes.map(n => `${c} ${n}`).join('\n') + '\n' : '')
const hasBody = (r: SnipReq) => r.body.type !== 'none'

const GEN: Record<Lang, (r: SnipReq) => string> = {
  curl: r => {
    const p = [`curl -X ${r.method} ${sq(r.url)}`]
    for (const [k, v] of r.headers) p.push(`-H ${sq(k + ': ' + v)}`)
    if (r.body.type === 'multipart') for (const [k, v] of r.body.fields) p.push(`-F ${sq(k + '=' + v)}`)
    else if (r.body.type === 'text') p.push(`-d ${sq(r.body.text)}`)
    return withNotes(r, '#') + p.join(' \\\n  ')
  },
  python: r => {
    const lines = [withNotes(r, '#') + 'import requests', '', `url = ${J(r.url)}`, `headers = ${pyDict(r.headers.filter(([k]) => !(r.body.type === 'multipart' && k.toLowerCase() === 'content-type')))}`]
    const args = ['headers=headers']
    if (r.body.type === 'text') { lines.push(`payload = ${J(r.body.text)}`); args.push('data=payload.encode("utf-8")') }
    if (r.body.type === 'multipart') { lines.push(`files = {\n${r.body.fields.map(([k, v]) => `    ${J(k)}: (None, ${J(v)}),`).join('\n')}\n}`); args.push('files=files') }
    lines.push('', `response = requests.request(${J(r.method)}, url, ${args.join(', ')})`, 'print(response.text)')
    return lines.join('\n')
  },
  fetch: r => {
    const opt = [`  method: ${J(r.method)},`, `  headers: ${jsObj(r.headers.filter(([k]) => !(r.body.type === 'multipart' && k.toLowerCase() === 'content-type')), '    ')},`]
    let pre = ''
    if (r.body.type === 'text') opt.push(`  body: ${J(r.body.text)},`)
    if (r.body.type === 'multipart') { pre = 'const form = new FormData();\n' + r.body.fields.map(([k, v]) => `form.append(${J(k)}, ${J(v)});`).join('\n') + '\n\n'; opt.push('  body: form,') }
    return `${withNotes(r, '//')}${pre}const response = await fetch(${J(r.url)}, {\n${opt.join('\n')}\n});\nconsole.log(await response.text());`
  },
  axios: r => {
    const opt = [`  method: ${J(r.method.toLowerCase())},`, `  url: ${J(r.url)},`, `  headers: ${jsObj(r.headers.filter(([k]) => !(r.body.type === 'multipart' && k.toLowerCase() === 'content-type')), '    ')},`]
    let pre = ''
    if (r.body.type === 'text') opt.push(`  data: ${J(r.body.text)},`)
    if (r.body.type === 'multipart') { pre = 'const form = new FormData();\n' + r.body.fields.map(([k, v]) => `form.append(${J(k)}, ${J(v)});`).join('\n') + '\n\n'; opt.push('  data: form,') }
    return `${withNotes(r, '//')}const axios = require("axios");\n\n${pre}const response = await axios({\n${opt.join('\n')}\n});\nconsole.log(response.data);`
  },
  node: r => {
    const u = new URL(r.url.startsWith('http') ? r.url : 'http://' + r.url)
    const mod = u.protocol === 'https:' ? 'https' : 'http'
    const boundary = r.body.type === 'multipart'
    const hdrs = r.headers.filter(([k]) => !(boundary && k.toLowerCase() === 'content-type'))
    if (boundary) hdrs.push(['Content-Type', 'multipart/form-data; boundary=----apirunner'])
    const payload = r.body.type === 'text' ? J(r.body.text)
      : r.body.type === 'multipart' ? J(r.body.fields.map(([k, v]) => `------apirunner\r\nContent-Disposition: form-data; name="${k}"\r\n\r\n${v}\r\n`).join('') + '------apirunner--\r\n') : ''
    return `${withNotes(r, '//')}const ${mod} = require("${mod}");\n\nconst options = {\n  method: ${J(r.method)},\n  hostname: ${J(u.hostname)},\n${u.port ? `  port: ${u.port},\n` : ''}  path: ${J(u.pathname + u.search)},\n  headers: ${jsObj(hdrs, '    ')},\n};\n\nconst req = ${mod}.request(options, (res) => {\n  const chunks = [];\n  res.on("data", (c) => chunks.push(c));\n  res.on("end", () => console.log(Buffer.concat(chunks).toString()));\n});\n${payload ? `req.write(${payload});\n` : ''}req.end();`
  },
  go: r => {
    const body = r.body.type === 'text' ? `strings.NewReader(${J(r.body.text)})` : r.body.type === 'multipart' ? 'payload' : 'nil'
    const mp = r.body.type === 'multipart'
      ? `\tpayload := &bytes.Buffer{}\n\twriter := multipart.NewWriter(payload)\n${r.body.fields.map(([k, v]) => `\t_ = writer.WriteField(${J(k)}, ${J(v)})`).join('\n')}\n\t_ = writer.Close()\n\n` : ''
    const hs = r.headers.filter(([k]) => !(mp && k.toLowerCase() === 'content-type')).map(([k, v]) => `\treq.Header.Add(${J(k)}, ${J(v)})`).join('\n')
    const imp = ['"fmt"', '"io"', '"net/http"', ...(r.body.type === 'text' ? ['"strings"'] : []), ...(mp ? ['"bytes"', '"mime/multipart"'] : [])].sort()
    return `${withNotes(r, '//')}package main\n\nimport (\n${imp.map(i => '\t' + i).join('\n')}\n)\n\nfunc main() {\n${mp}\treq, _ := http.NewRequest(${J(r.method)}, ${J(r.url)}, ${body})\n${hs}\n${mp ? '\treq.Header.Set("Content-Type", writer.FormDataContentType())\n' : ''}\n\tres, err := http.DefaultClient.Do(req)\n\tif err != nil {\n\t\tpanic(err)\n\t}\n\tdefer res.Body.Close()\n\tb, _ := io.ReadAll(res.Body)\n\tfmt.Println(string(b))\n}`
  },
  php: r => {
    const hs = r.headers.map(([k, v]) => `    ${phpq(k + ': ' + v)},`).join('\n')
    const body = r.body.type === 'text' ? `  CURLOPT_POSTFIELDS => ${phpq(r.body.text)},\n` : r.body.type === 'multipart' ? `  CURLOPT_POSTFIELDS => [\n${r.body.fields.map(([k, v]) => `    ${phpq(k)} => ${phpq(v)},`).join('\n')}\n  ],\n` : ''
    return `<?php\n${withNotes(r, '//')}$curl = curl_init();\n\ncurl_setopt_array($curl, [\n  CURLOPT_URL => ${phpq(r.url)},\n  CURLOPT_RETURNTRANSFER => true,\n  CURLOPT_CUSTOMREQUEST => ${phpq(r.method)},\n  CURLOPT_HTTPHEADER => [\n${hs}\n  ],\n${body}]);\n\n$response = curl_exec($curl);\ncurl_close($curl);\necho $response;`
  },
  java: r => {
    const media = r.headers.find(([k]) => k.toLowerCase() === 'content-type')?.[1] ?? 'text/plain'
    const mp = r.body.type === 'multipart'
    const bodyDef = r.body.type === 'text' ? `RequestBody body = RequestBody.create(${J(r.body.text)}, MediaType.parse(${J(media)}));\n`
      : r.body.type === 'multipart' ? `RequestBody body = new MultipartBody.Builder().setType(MultipartBody.FORM)\n${r.body.fields.map(([k, v]) => `    .addFormDataPart(${J(k)}, ${J(v)})`).join('\n')}\n    .build();\n` : ''
    const needsBody = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(r.method) || hasBody(r)
    const call = needsBody ? `.method(${J(r.method)}, ${hasBody(r) ? 'body' : 'RequestBody.create(new byte[0])'})` : `.method(${J(r.method)}, null)`
    return `${withNotes(r, '//')}OkHttpClient client = new OkHttpClient();\n\n${bodyDef}Request request = new Request.Builder()\n    .url(${J(r.url)})\n    ${call}\n${r.headers.filter(([k]) => !(mp && k.toLowerCase() === 'content-type')).map(([k, v]) => `    .addHeader(${J(k)}, ${J(v)})`).join('\n')}\n    .build();\n\ntry (Response response = client.newCall(request).execute()) {\n    System.out.println(response.body().string());\n}`
  },
  csharp: r => {
    const ct = r.headers.find(([k]) => k.toLowerCase() === 'content-type')?.[1]
    const hs = r.headers.filter(([k]) => k.toLowerCase() !== 'content-type').map(([k, v]) => `request.Headers.TryAddWithoutValidation(${J(k)}, ${J(v)});`).join('\n')
    const content = r.body.type === 'text' ? `request.Content = new StringContent(${J(r.body.text)}, System.Text.Encoding.UTF8${ct ? `, ${J(ct.split(';')[0].trim())}` : ''});\n`
      : r.body.type === 'multipart' ? `var content = new MultipartFormDataContent();\n${r.body.fields.map(([k, v]) => `content.Add(new StringContent(${J(v)}), ${J(k)});`).join('\n')}\nrequest.Content = content;\n` : ''
    const m = r.method[0] + r.method.slice(1).toLowerCase()
    const known = ['Get', 'Post', 'Put', 'Delete', 'Patch', 'Head', 'Options'].includes(m) ? `HttpMethod.${m}` : `new HttpMethod(${J(r.method)})`
    return `${withNotes(r, '//')}var client = new HttpClient();\nvar request = new HttpRequestMessage(${known}, ${J(r.url)});\n${hs}\n${content}var response = await client.SendAsync(request);\nresponse.EnsureSuccessStatusCode();\nConsole.WriteLine(await response.Content.ReadAsStringAsync());`
  },
}

export const generate = (lang: Lang, r: SnipReq) => GEN[lang](r)
