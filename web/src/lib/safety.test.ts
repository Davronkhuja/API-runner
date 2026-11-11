import { describe, expect, it } from 'vitest'
import { hostOf, isSafeMethod, isTestHost } from './safety'

describe('safety', () => {
  it('safe methods', () => { for (const m of ['get', 'HEAD', 'Options']) expect(isSafeMethod(m)).toBe(true); for (const m of ['POST', 'PUT', 'PATCH', 'DELETE']) expect(isSafeMethod(m)).toBe(false) })
  it('hostOf parses urls, ports, ipv6 and rejects unresolved variables', () => {
    expect(hostOf('https://API.Online-Mahalla.uz:8443/a?b=1')).toBe('api.online-mahalla.uz')
    expect(hostOf('localhost:3000/x')).toBe('localhost')
    expect(hostOf('http://[::1]:5050/')).toBe('::1')
    expect(hostOf('{{base}}/users')).toBeNull()
    expect(hostOf('')).toBeNull()
  })
  it('builtin test hosts', () => {
    for (const h of ['localhost', '127.0.0.1', '::1', 'api.local', 'svc.test', 'x.localhost']) expect(isTestHost(h, [])).toBe(true)
    for (const h of ['hujjat.uz', 'api.online-mahalla.uz', 'localhost.evil.com', 'notlocal', 'evil.test.com', null]) expect(isTestHost(h as any, [])).toBe(false)
  })
  it('user test hosts: exact and wildcard', () => {
    const extra = ['api.stage.company.uz', '*.corp.uz']
    expect(isTestHost('api.stage.company.uz', extra)).toBe(true)
    expect(isTestHost('a.b.corp.uz', extra)).toBe(true)
    expect(isTestHost('corp.uz', extra)).toBe(true)
    expect(isTestHost('evilcorp.uz', extra)).toBe(false)
    expect(isTestHost('api.company.uz', extra)).toBe(false)
  })
})
