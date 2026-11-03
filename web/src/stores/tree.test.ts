import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { dropPositionFor, isSelfOrDescendant, rowKey, useTree } from './tree'

const req = (id: string) => ({ id, name: id.toUpperCase(), request: { method: 'GET', header: [], url: { raw: '' } }, response: [] })
const folder = (id: string, item: any[] = []) => ({ id, name: id.toUpperCase(), item })
let t: ReturnType<typeof useTree>
beforeEach(() => {
  setActivePinia(createPinia()); t = useTree()
  t.metas = [{ id: 'c1', name: 'Col', requests: 3 }, { id: 'c2', name: 'Two', requests: 0 }]
  t.cols = {
    c1: { info: { _postman_id: 'c1', name: 'Col' }, item: [folder('f1', [req('a'), folder('f2', [req('b')])]), req('c')] },
    c2: { info: { _postman_id: 'c2', name: 'Two' }, item: [] },
  } as any
})
const ids = () => t.rows.map(r => (r.isCollection ? '#' + r.collectionId : r.id))

describe('rows', () => {
  it('flattens with depth and respects collapse', () => {
    expect(ids()).toEqual(['#c1', 'f1', 'a', 'f2', 'b', 'c', '#c2'])
    t.toggle(rowKey('c1', 'f2'), t.findItem('c1', 'f2')!); expect(ids()).not.toContain('b')
    t.toggle(rowKey('c1', ''), null); expect(ids()).toEqual(['#c1', '#c2'])
  })
  it('filter shows matches with ancestors and auto-expands', () => {
    t.toggle(rowKey('c1', 'f1'), t.findItem('c1', 'f1')!)
    t.filter = 'b'; expect(ids()).toEqual(['#c1', 'f1', 'f2', 'b'])
    t.filter = 'zzz'; expect(ids()).toEqual([])
  })
})

describe('selection', () => {
  it('click, cmd toggle, shift range', () => {
    t.select(rowKey('c1', 'a')); t.select(rowKey('c1', 'c'), { meta: true }); expect(t.selection).toEqual(['c1:a', 'c1:c'])
    t.select(rowKey('c1', 'c'), { meta: true }); expect(t.selection).toEqual(['c1:a'])
    t.select(rowKey('c1', 'a')); t.select(rowKey('c1', 'b'), { shift: true }); expect(t.selection).toEqual(['c1:a', 'c1:f2', 'c1:b'])
  })
  it('dragSet uses whole selection in visual order, else just the row', () => {
    t.select(rowKey('c1', 'c')); t.select(rowKey('c1', 'a'), { meta: true })
    expect(t.dragSet('c1:c')).toEqual(['c1:a', 'c1:c']); expect(t.dragSet('c1:b')).toEqual(['c1:b'])
  })
})

describe('drop rules', () => {
  it('folder cannot go into itself or descendants', () => {
    expect(isSelfOrDescendant(t.cols.c1.item, 'f1', 'b')).toBe(true)
    expect(t.canDrop(['c1:f1'], 'c1:f2', 'inside')).toBe(false)
    expect(t.canDrop(['c1:f1'], 'c1:b', 'before')).toBe(false)
    expect(t.canDrop(['c1:f1'], 'c1:f1', 'after')).toBe(false)
  })
  it('allowed moves', () => {
    expect(t.canDrop(['c1:a'], 'c1:c', 'after')).toBe(true)
    expect(t.canDrop(['c1:f1'], 'c2:', 'inside')).toBe(true)     // boshqa collection ildiziga
    expect(t.canDrop(['c1:f1'], 'c1:c', 'inside')).toBe(false)   // so'rov ichiga tashlab bo'lmaydi
    expect(t.canDrop(['c1:a'], 'c1:f1', 'inside')).toBe(true)
  })
  it('drop position zones', () => {
    expect(dropPositionFor(2, 28, true)).toBe('before'); expect(dropPositionFor(14, 28, true)).toBe('inside'); expect(dropPositionFor(26, 28, true)).toBe('after')
    expect(dropPositionFor(5, 28, false)).toBe('before'); expect(dropPositionFor(20, 28, false)).toBe('after')
  })
})
