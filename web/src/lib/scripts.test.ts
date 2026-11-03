import { describe, expect, it } from 'vitest'
import { eventsFromText, textFromEvents } from './scripts'
import { PM_API, SNIPPETS } from './pmApi'
import { normalizeDraft } from './draft'

describe('scripts: Postman event ↔ matn', () => {
  it('exec massiv/satr, eski `events` kaliti', () => {
    expect(textFromEvents({ event: [{ listen: 'prerequest', script: { exec: ['a', 'b'] } }, { listen: 'test', script: { exec: 'x' } }] })).toEqual({ pre: 'a\nb', test: 'x' })
    expect(textFromEvents({ events: [{ listen: 'test', script: { exec: ['t'] } }] })).toEqual({ pre: '', test: 't' })
    expect(textFromEvents({})).toEqual({ pre: '', test: '' })
  })
  it("matndan event; bo'sh skript yozilmaydi, boshqa listen'lar saqlanadi", () => {
    const ev = eventsFromText([{ listen: 'custom', script: { exec: ['k'] } }], { pre: 'p1\np2', test: '  ' })
    expect(ev).toEqual([{ listen: 'prerequest', script: { type: 'text/javascript', exec: ['p1', 'p2'] } }, { listen: 'custom', script: { exec: ['k'] } }])
    expect(eventsFromText(undefined, { pre: '', test: '' })).toEqual([])
  })
  it('roundtrip', () => {
    const s = { pre: "console.log('x')\n// izoh", test: 'tests["a"] = true' }
    expect(textFromEvents({ event: eventsFromText(undefined, s) })).toEqual(s)
  })
})

describe('pm API ro\'yxati', () => {
  it('takrorlanmaydi va asosiy API bor', () => {
    const labels = PM_API.map(a => a.label)
    expect(new Set(labels).size).toBe(labels.length)
    for (const l of ['pm.test', 'pm.expect', 'pm.sendRequest', 'pm.environment.set', 'pm.response.json', 'pm.execution.setNextRequest', 'postman.setNextRequest', 'tests', 'require']) expect(labels).toContain(l)
  })
  it('snippetlar nomlari noyob, pre/test bo\'yicha bo\'lingan', () => {
    expect(new Set(SNIPPETS.map(s => s.title)).size).toBe(SNIPPETS.length)
    expect(SNIPPETS.some(s => s.where === 'pre')).toBe(true); expect(SNIPPETS.some(s => s.where === 'test')).toBe(true)
  })
})

describe('draft normalizatsiyasi', () => {
  it("eski sessiya qoralamasi: yangi maydonlar to'ldiriladi", () => {
    const d = normalizeDraft({ name: 'x', method: 'GET', url: 'u', params: [], headers: [], auth: { type: 'bearer', token: 't' }, body: { mode: 'raw', raw: 'r' } })
    expect(d.scripts).toEqual({ pre: '', test: '' }); expect(d.settings).toEqual({}); expect(d.pathVars).toEqual([])
    expect(d.auth.type).toBe('bearer'); expect(d.auth.cfg).toBeDefined(); expect(d.body.raw).toBe('r'); expect(d.body.gql).toBeDefined()
  })
})
