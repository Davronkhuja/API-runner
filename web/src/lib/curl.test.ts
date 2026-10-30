import { describe, expect, it } from 'vitest'
import { parseCurl, applyCurlToDraft } from './curl'
import { newDraft } from './draft'

describe('parseCurl (eski UI bilan bir xil)', () => {
  it('post + headers + body', () => {
    const r = parseCurl(`curl -X POST 'https://a.io/x?y=1' -H 'Content-Type: application/json' -H "X-A: b" -d '{"k":1}'`)!
    expect(r.method).toBe('POST'); expect(r.url).toBe('https://a.io/x?y=1'); expect(r.headers).toContainEqual({ name: 'X-A', value: 'b' }); expect(r.body).toBe('{"k":1}')
  })
  it('data implies POST, -u basic, continuations, --url, -G', () => {
    expect(parseCurl("curl https://a.io -d 'a=1'")!.method).toBe('POST')
    expect(parseCurl('curl -u user:pass https://a.io')!.auth).toBe('Basic dXNlcjpwYXNz')
    expect(parseCurl("curl https://a.io \\\n -H 'A: 1' \\\n --compressed")!.headers).toEqual([{ name: 'A', value: '1' }])
    expect(parseCurl('curl --url https://a.io/p')!.url).toBe('https://a.io/p')
    expect(parseCurl("curl -G https://a.io -d 'q=1'")!.method).toBe('GET')
  })
  it('invalid -> null; valueless flags keep URL', () => {
    expect(parseCurl('https://a.io')).toBeNull(); expect(parseCurl('curl -X GET')).toBeNull()
    for (const f of ['-k', '-L', '-s', '--insecure', '--compressed']) expect(parseCurl(`curl ${f} https://a.io`)!.url).toBe('https://a.io')
  })
  it('applies to draft: query -> params, auth/content-type split', () => {
    const d = newDraft(); applyCurlToDraft(d, parseCurl(`curl https://a.io/x?y=1 -H 'Authorization: Bearer T' -H 'Content-Type: application/json' -d '{"a":1}'`)!)
    expect(d.url).toBe('https://a.io/x'); expect(d.params[0]).toMatchObject({ key: 'y', value: '1' }); expect(d.auth).toMatchObject({ type: 'bearer', token: 'T' })
    expect(d.body).toMatchObject({ mode: 'json', contentType: 'application/json' }); expect(d.method).toBe('POST')
  })
})

import { buildCurl } from './curl'
describe('buildCurl', () => {
  it('roundtrips through parseCurl', () => {
    const d = newDraft(); d.method = 'POST'; d.url = 'https://a.io/x'; d.params[0] = { key: 'q', value: 'a b', enabled: true }
    d.headers[0] = { key: 'X-A', value: "it's", enabled: true }; d.body = { ...d.body, mode: 'json', raw: '{"k":1}', contentType: 'application/json' }
    d.auth = { ...d.auth, type: 'bearer', token: 'T' }
    const p = parseCurl(buildCurl(d))!
    expect(p.method).toBe('POST'); expect(p.url).toBe('https://a.io/x?q=a%20b'); expect(p.body).toBe('{"k":1}')
    expect(p.headers).toContainEqual({ name: 'X-A', value: "it's" }); expect(p.headers).toContainEqual({ name: 'Authorization', value: 'Bearer T' })
  })
})
