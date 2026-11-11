import { describe, expect, it } from 'vitest'
import { filterEvents, hexdump, oneLine, systemText, tryJson, type LogFilter } from './protocols'
import type { ProtoEvent } from '../stores/protocols'

const ev = (o: Partial<ProtoEvent>): ProtoEvent => ({ seq: 0, ts: 1, type: 'message', ...o })
const F: LogFilter = { dir: 'all', system: true, types: null, q: '', regex: false }

describe('protocols helpers', () => {
  it('hexdump', () => {
    expect(hexdump(Uint8Array.from([0, 65, 66, 255]))).toBe('000000  00 41 42 ff' + ' '.repeat(47 - 11) + '  .AB.')
    expect(hexdump(new Uint8Array(5000), 32).split('\n').pop()).toContain('yana 4968 bayt')
  })
  it('tryJson', () => {
    expect(tryJson('{"a": 1}')).toEqual({ a: 1 })
    expect(tryJson('hello')).toBeUndefined()
    expect(tryJson('42')).toBeUndefined()
    expect(tryJson('{bad')).toBeUndefined()
  })
  it('oneLine', () => { expect(oneLine('a\n  b\tc')).toBe('a b c'); expect(oneLine('x'.repeat(300), 10)).toBe('x'.repeat(10) + '…') })
  it('systemText', () => {
    expect(systemText(ev({ type: 'close', code: 4001, reason: 'bye' }))).toBe('Yopildi (kod 4001: bye)')
    expect(systemText(ev({ type: 'reconnecting', attempt: 2, delay: 0.05 }))).toContain('urinish 2')
    expect(systemText(ev({ type: 'open', status: 101, subprotocol: 'chat' }))).toBe('Ulandi (HTTP 101) · subprotokol: chat')
  })
  it('filterEvents: direction, system, types, search, regex', () => {
    const list = [ev({ seq: 1, type: 'open' }), ev({ seq: 2, dir: 'out', data: 'ping' }), ev({ seq: 3, dir: 'in', data: 'PONG 1' }), ev({ seq: 4, type: 'event', event: 'tick', data: 'x' }), ev({ seq: 5, type: 'event', event: 'message', data: 'y' })]
    const ids = (f: Partial<LogFilter>) => filterEvents(list, { ...F, ...f }).map(e => e.seq)
    expect(ids({})).toEqual([1, 2, 3, 4, 5])
    expect(ids({ dir: 'in' })).toEqual([1, 3, 4, 5])
    expect(ids({ system: false, dir: 'out' })).toEqual([2])
    expect(ids({ types: ['tick'] })).toEqual([1, 2, 3, 4])
    expect(ids({ q: 'pong', system: false })).toEqual([3])
    expect(ids({ q: 'p.ng', system: false })).toEqual([])                 // literal (regex o'chiq)
    expect(ids({ q: 'p.ng', regex: true, system: false })).toEqual([2, 3])
    expect(ids({ q: 'tick', system: false })).toEqual([4])               // event turi bo'yicha ham topiladi
    expect(ids({ q: '(', regex: true, system: false })).toEqual([2, 3, 4, 5])      // noto'g'ri regex — filtr qo'llanmaydi
  })
})
