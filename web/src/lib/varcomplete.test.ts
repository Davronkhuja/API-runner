import { describe, expect, it } from 'vitest'
import { completionEdit, triggerAt } from './varcomplete'

describe('triggerAt', () => {
  it('finds the query after {{', () => {
    expect(triggerAt('https://{{ba', 12)).toEqual({ from: 10, query: 'ba' })
    expect(triggerAt('x {{ ', 5)).toEqual({ from: 5, query: '' })
    expect(triggerAt('{{$gu', 5)).toEqual({ from: 2, query: '$gu' })
  })
  it('ignores closed or absent braces', () => {
    expect(triggerAt('{{a}} b', 7)).toBeNull()
    expect(triggerAt('plain {', 7)).toBeNull()
    expect(triggerAt('{{a b', 5)).toBeNull()
  })
})

describe('completionEdit', () => {
  it('adds closing braces', () => {
    const t = 'u/{{ba', e = completionEdit(t, 6, 4, 'base')
    expect(t.slice(0, e.from) + e.insert + t.slice(e.to)).toBe('u/{{base}}')
  })
  it('does not duplicate existing closing braces and replaces the rest of the name', () => {
    const t = '{{ba|se}}'.replace('|', ''), e = completionEdit(t, 4, 2, 'base_url')
    expect(t.slice(0, e.from) + e.insert + t.slice(e.to)).toBe('{{base_url}}')
  })
})
