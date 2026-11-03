import { describe, expect, it } from 'vitest'
import { parseSetCookie } from './cookies'
import { cleanSettings, mergeSettings } from './settings'

describe('cookies', () => {
  it('Set-Cookie atributlari', () => {
    expect(parseSetCookie('sid=a=b; Path=/x; Domain=e.com; Max-Age=60; HttpOnly; Secure; SameSite=Lax')).toEqual(
      { name: 'sid', value: 'a=b', domain: 'e.com', path: '/x', expires: '', maxAge: '60', httpOnly: true, secure: true, sameSite: 'Lax' })
    expect(parseSetCookie('flag').name).toBe('flag')
  })
})
describe('settings', () => {
  it('bo\'shlar tashlanadi, so\'rov globalni bosadi, false saqlanadi', () => {
    expect(cleanSettings({ proxy: '', max_redirects: NaN as any, follow_redirects: false })).toEqual({ follow_redirects: false })
    expect(mergeSettings({ proxy: 'http://g', http2: true }, { proxy: 'http://r', http2: undefined })).toEqual({ proxy: 'http://r', http2: true })
  })
})
