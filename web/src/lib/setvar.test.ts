import { describe, expect, it } from 'vitest'
import { suggestVarName, upsertVar, validateVarName } from './setvar'

describe('suggestVarName', () => {
  it('slugifies', () => {
    expect(suggestVarName('https://api.example.com/v1')).toBe('api_example_com_v1')
    expect(suggestVarName('Bearer abc')).toBe('bearer_abc')
    expect(suggestVarName('12345')).toBe('v_12345')
    expect(suggestVarName('???')).toBe('value')
    expect(suggestVarName('x', 'Content Type')).toBe('content_type')
  })
})
describe('validateVarName', () => {
  it('accepts normal and dynamic-like names, rejects bad', () => {
    expect(validateVarName('base_url')).toBeNull()
    expect(validateVarName('a.b-c')).toBeNull()
    expect(validateVarName('')).not.toBeNull()
    expect(validateVarName('1abc')).not.toBeNull()
    expect(validateVarName('a b')).not.toBeNull()
    expect(validateVarName('a}}')).not.toBeNull()
  })
})
describe('upsertVar', () => {
  const make = (key: string, value: string) => ({ key, value, enabled: true, type: 'default' })
  it('appends new', () => {
    const r = upsertVar([], 'a', '1', make)
    expect(r.existed).toBe(false); expect(r.rows).toEqual([{ key: 'a', value: '1', enabled: true, type: 'default' }])
  })
  it('updates existing and keeps current in sync only when set', () => {
    const r = upsertVar([{ key: 'a', value: '1', current: '9' }, { key: 'b', value: 'x' }], 'a', '2', make)
    expect(r.existed).toBe(true); expect(r.rows[0]).toEqual({ key: 'a', value: '2', current: '2' }); expect(r.rows[1]).toEqual({ key: 'b', value: 'x' })
  })
})
