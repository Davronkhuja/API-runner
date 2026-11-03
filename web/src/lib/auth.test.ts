import { describe, expect, it } from 'vitest'
import { authFromPm, authToPm, emptyAuth, resolveAuth } from './auth'
import { pathVarNames, syncPathVars } from './draft'

const bearer = (t: string) => authToPm({ ...emptyAuth('bearer'), token: t })

describe('auth', () => {
  it('auth yo\'q = meros; noauth = none', () => {
    expect(authFromPm(undefined).type).toBe('inherit'); expect(authFromPm(null).type).toBe('inherit')
    expect(authFromPm({ type: 'noauth' }).type).toBe('none')
  })
  it('roundtrip bearer/basic/custom', () => {
    for (const a of [{ ...emptyAuth('bearer'), token: 'T' }, { ...emptyAuth('basic'), user: 'u', pass: 'p' }, { ...emptyAuth('custom'), custom: 'X y' }, emptyAuth('none')])
      expect(authFromPm(authToPm(a))).toEqual(a)
    expect(authToPm(emptyAuth('inherit'))).toBeUndefined()
  })
  it('meros eng yaqin ota bo\'yicha, noauth zanjirni to\'xtatadi', () => {
    expect(resolveAuth(emptyAuth('inherit'), [undefined, bearer('F'), bearer('C')]).token).toBe('F')
    expect(resolveAuth(emptyAuth('inherit'), [{ type: 'noauth' }, bearer('C')]).type).toBe('none')
    expect(resolveAuth(emptyAuth('inherit'), []).type).toBe('none')
    expect(resolveAuth({ ...emptyAuth('bearer'), token: 'own' }, [bearer('C')]).token).toBe('own')
  })
})

describe('path variables', () => {
  it('faqat yo\'ldagi :name (port/query/sxema emas)', () => {
    expect(pathVarNames('http://h:5050/users/:id/x/:id/:n?q=:z')).toEqual(['id', 'n'])
    expect(pathVarNames('{{host}}/a/:b')).toEqual(['b'])
  })
  it('qiymatlar saqlanadi', () => expect(syncPathVars('/a/:x/:y', [{ key: 'x', value: '1' }, { key: 'gone', value: '9' }])).toEqual([{ key: 'x', value: '1' }, { key: 'y', value: '' }]))
})
