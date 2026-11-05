import { describe, expect, it } from 'vitest'
import { jsonError, maskVars } from './jsonlint'

describe('jsonError', () => {
  it('to\'g\'ri JSON va bo\'sh matn — xato yo\'q', () => { expect(jsonError('{"a": [1, 2]}')).toBeNull(); expect(jsonError('  ')).toBeNull() })
  it('{{var}} placeholder\'lari xato emas (qiymat o\'rnida ham, qator ichida ham)', () => {
    expect(jsonError('{"id": {{id}}, "n": "{{name}}"}')).toBeNull()
    expect(maskVars('a{{x}}b')).toHaveLength(7)
  })
  it('xato qatori va ustuni', () => {
    const e = jsonError('{\n  "a": 1,\n  "b": 2\n  "c": 3\n}')
    expect(e).not.toBeNull()
    expect(e!.line).toBe(4)
  })
  it('tugamagan JSON oxirida xato', () => { const e = jsonError('{"a": 1'); expect(e?.line).toBe(1) })
})
