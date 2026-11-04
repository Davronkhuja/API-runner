import { describe, expect, it } from 'vitest'
import { bodyLines, diffStats, headerDiff, lineDiff, stripVolatile } from './diff'

describe('lineDiff', () => {
  it('bir xil kirish — hammasi same', () => {
    expect(lineDiff(['a', 'b'], ['a', 'b']).every(x => x.type === 'same')).toBe(true)
  })
  it('qo\'shilgan va o\'chirilgan qatorlar', () => {
    const d = lineDiff(['{', 'x', 'y', '}'], ['{', 'x', 'z', 'w', '}'])
    expect(diffStats(d)).toEqual({ add: 2, del: 1 })
    expect(d.filter(x => x.type !== 'same').map(x => x.type + ':' + x.text)).toEqual(['del:y', 'add:z', 'add:w'])
  })
  it('qator raqamlari a va b tomonda to\'g\'ri', () => {
    const d = lineDiff(['1', '2', '3'], ['1', '3'])
    expect(d.find(x => x.type === 'del')).toMatchObject({ text: '2', a: 2 })
    expect(d.find(x => x.text === '3')).toMatchObject({ a: 3, b: 2 })
  })
})

describe('vaqt/ID e\'tiborsiz', () => {
  it('stripVolatile id, *_id, vaqt maydonlarini olib tashlaydi, ma\'noli maydonni qoldiradi', () => {
    expect(stripVolatile({ id: 1, user_id: 2, name: 'a', created_at: 'x', timestamp: 1, nested: { requestId: 'r', v: 1 }, list: [{ uuid: 'u', k: 2 }] }))
      .toEqual({ name: 'a', nested: { v: 1 }, list: [{ k: 2 }] })
  })
  it('bodyLines: ID/vaqt farqi diff bermaydi, haqiqiy farq beradi', () => {
    const a = JSON.stringify({ id: 1, ts: 100, n: 'x', items: [1, 2] }), b = JSON.stringify({ id: 9, ts: 200, n: 'x', items: [1, 3] })
    expect(diffStats(lineDiff(bodyLines(a, true), bodyLines(b, true)))).toEqual({ add: 1, del: 1 })
    expect(diffStats(lineDiff(bodyLines(a, false), bodyLines(b, false))).add).toBeGreaterThan(1)
  })
  it('JSON bo\'lmagan matn qator bo\'yicha', () => { expect(bodyLines('a\nb', true)).toEqual(['a', 'b']) })
  it('kalit tartibi farqi diff emas', () => { expect(bodyLines('{"b":1,"a":2}', false)).toEqual(bodyLines('{"a":2,"b":1}', false)) })
})

describe('headerDiff', () => {
  it('Date kabi o\'zgaruvchan sarlavhalar chiqarib tashlanadi', () => {
    expect(headerDiff({ Date: '1', 'X-A': 'x' }, { Date: '2', 'X-A': 'y' })).toEqual([{ key: 'x-a', a: 'x', b: 'y' }])
    expect(headerDiff({ Date: '1' }, { Date: '2' }, false)).toHaveLength(1)
  })
})
