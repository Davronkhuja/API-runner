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
    expect(d.url).toBe('https://a.io/x?y=1'); expect(d.params[0]).toMatchObject({ key: 'y', value: '1' }); expect(d.auth).toMatchObject({ type: 'bearer', token: 'T' })
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

import { composeUrl, paramsFromUrl, baseUrl, specFromDraft, requestFromDraft, draftFromItem } from './draft'
describe('URL <-> params sync', () => {
  it('compose/parse roundtrip keeps {{vars}} readable and decodes', () => {
    const rows = paramsFromUrl('http://h/p?a=1&b=x%20y&{{k}}={{v}}', [])
    expect(rows.slice(0, 3).map(r => [r.key, r.value])).toEqual([['a', '1'], ['b', 'x y'], ['{{k}}', '{{v}}']])
    expect(composeUrl('http://h/p', rows)).toBe('http://h/p?a=1&b=x%20y&{{k}}={{v}}')
  })
  it('disabled rows are kept in table but not in url', () => {
    const rows = paramsFromUrl('http://h?a=1', [{ key: 'off', value: '2', enabled: false }, { key: '', value: '', enabled: true }])
    expect(rows.map(r => r.key)).toEqual(['a', 'off', '']); expect(composeUrl('http://h?a=1', rows)).toBe('http://h?a=1')
  })
  it('send uses base url (table is the source of truth); save keeps full raw', () => {
    const d = newDraft(); d.url = 'http://h/p?a=1'; d.params = paramsFromUrl(d.url, d.params)
    expect(specFromDraft(d).url).toBe('http://h/p'); expect(specFromDraft(d).params).toEqual([{ name: 'a', value: '1' }])
    expect(requestFromDraft(d).url.raw).toBe('http://h/p?a=1'); expect(baseUrl('x')).toBe('x')
    expect(draftFromItem({ id: 'i', name: 'n', request: requestFromDraft(d), response: [] }).url).toBe('http://h/p?a=1')
  })
})
