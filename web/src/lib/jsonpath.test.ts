import { describe, expect, it } from 'vitest'
import { jsonPath as jp } from './jsonpath'

const doc = { store: { book: [{ t: 'A', price: 8, tags: ['x'] }, { t: 'B', price: 12 }, { t: 'C', price: 5 }], bicycle: { price: 20 } }, n: 1 }

describe('jsonpath', () => {
  it('$ va child', () => { expect(jp(doc, '$')).toEqual([doc]); expect(jp(doc, '$.n')).toEqual([1]); expect(jp(doc, "$['store'].bicycle.price")).toEqual([20]) })
  it('indeks, manfiy indeks, slice, wildcard', () => {
    expect(jp(doc, '$.store.book[0].t')).toEqual(['A']); expect(jp(doc, '$.store.book[-1].t')).toEqual(['C'])
    expect(jp(doc, '$.store.book[0:2].t')).toEqual(['A', 'B']); expect(jp(doc, '$.store.book[*].t')).toEqual(['A', 'B', 'C']); expect(jp(doc, '$.store.*').length).toBe(2)
  })
  it('descendant', () => { expect(jp(doc, '$..price')).toEqual([8, 12, 5, 20]); expect(jp(doc, '$..tags[0]')).toEqual(['x']) })
  it('filtr', () => { expect(jp(doc, '$.store.book[?(@.price<10)].t')).toEqual(['A', 'C']); expect(jp(doc, "$.store.book[?(@.t=='B')].price")).toEqual([12]) })
  it('mos kelmasa bo\'sh, xatoda Error', () => {
    expect(jp(doc, '$.nope.x')).toEqual([]); expect(jp(doc, '$.store.book[9]')).toEqual([])
    expect(() => jp(doc, 'store')).toThrow(); expect(() => jp(doc, '$.a[')).toThrow(); expect(() => jp(doc, '$.[?]')).toThrow()
  })
})
