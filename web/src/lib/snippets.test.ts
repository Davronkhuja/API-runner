import { describe, expect, it, vi } from 'vitest'

vi.mock('./scope', () => ({ flatVars: () => ({}), specFor: () => ({}) }))
import { generate, LANGS, type SnipReq } from './snippets'

const get: SnipReq = { method: 'GET', url: 'https://a.io/x?q=1', headers: [['X-A', 'b']], body: { type: 'none' }, notes: [] }
const post: SnipReq = { method: 'POST', url: 'https://a.io/p', headers: [['Content-Type', 'application/json'], ['Authorization', 'Bearer T']], body: { type: 'text', text: '{"a":"it\'s \\"q\\""}' }, notes: [] }
const multi: SnipReq = { method: 'POST', url: 'http://h:8080/up', headers: [['Content-Type', 'multipart/form-data']], body: { type: 'multipart', fields: [['f', 'v']] }, notes: ['JWT auth ...'] }

describe('snippets', () => {
  it('9 til, har biri URL va metodni o\'z ichiga oladi (GET/POST/multipart)', () => {
    expect(LANGS.length).toBe(9)
    for (const [l] of LANGS) for (const r of [get, post, multi]) {
      const c = generate(l, r)
      expect(c, l).toContain(new URL(r.url).pathname)
      expect(c.toLowerCase(), l).toContain(r.method.toLowerCase())
    }
  })
  it('cURL: qo\'shtirnoq escape va -d / -F', () => {
    expect(generate('curl', post)).toContain(`-d '{"a":"it'\\''s \\"q\\""}'`)
    expect(generate('curl', multi)).toContain("-F 'f=v'")
    expect(generate('curl', multi).startsWith('# JWT')).toBe(true)
  })
  it('Python/JS: JSON-escape qilingan tanasi', () => {
    for (const l of ['python', 'fetch', 'axios'] as const) expect(generate(l, post)).toContain(JSON.stringify(post.body.type === 'text' ? post.body.text : ''))
  })
  it('multipart: Content-Type qo\'lda qo\'yilmaydi (chegara kutubxonada)', () => {
    expect(generate('python', multi)).toContain('files = {')
    expect(generate('python', multi)).not.toContain('"Content-Type"')
    expect(generate('fetch', multi)).toContain('FormData')
    expect(generate('go', multi)).toContain('FormDataContentType')
    expect(generate('java', multi)).toContain('addFormDataPart')
    expect(generate('csharp', multi)).toContain('MultipartFormDataContent')
    expect(generate('php', multi)).toContain("'f' => 'v'")
  })
  it('Go importlari mos; PHP bir tirnoqda escape; C# nostandart metod', () => {
    expect(generate('go', get)).not.toContain('"strings"'); expect(generate('go', post)).toContain('"strings"')
    expect(generate('php', { ...post, body: { type: 'text', text: "o'z" } })).toContain("'o\\'z'")
    expect(generate('csharp', { ...get, method: 'PROPFIND' })).toContain('new HttpMethod("PROPFIND")')
  })
  it('Node: http/https va port', () => {
    expect(generate('node', multi)).toContain('require("http")'); expect(generate('node', multi)).toContain('port: 8080')
    expect(generate('node', get)).toContain('require("https")')
  })
})
