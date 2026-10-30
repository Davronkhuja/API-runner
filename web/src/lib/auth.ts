/** Auth qoralamasi va Postman (`auth` obyekti) o'rtasida o'tkazish; meros (inherit) mantiqi. */
export type AuthType = 'inherit' | 'none' | 'bearer' | 'basic' | 'custom'
export interface AuthDraft { type: AuthType; token: string; user: string; pass: string; custom: string }
export type PmAuth = { type: string; [k: string]: any } | null | undefined

export const emptyAuth = (type: AuthType = 'inherit'): AuthDraft => ({ type, token: '', user: '', pass: '', custom: '' })

const field = (a: any, kind: string, key: string): string => a?.[kind]?.find((x: any) => x.key === key)?.value ?? ''

export function authFromPm(a: PmAuth): AuthDraft {
  if (!a) return emptyAuth('inherit')              // Postman: auth yo'q = meros
  switch (a.type) {
    case 'noauth': return emptyAuth('none')
    case 'bearer': return { ...emptyAuth('bearer'), token: field(a, 'bearer', 'token') }
    case 'basic': return { ...emptyAuth('basic'), user: field(a, 'basic', 'username'), pass: field(a, 'basic', 'password') }
    case 'x-custom': return { ...emptyAuth('custom'), custom: field(a, 'x-custom', 'value') }
    default: return emptyAuth('inherit')
  }
}

/** `undefined` = kalit yozilmaydi (meros). */
export function authToPm(a: AuthDraft): PmAuth {
  switch (a.type) {
    case 'inherit': return undefined
    case 'none': return { type: 'noauth' }
    case 'bearer': return { type: 'bearer', bearer: [{ key: 'token', value: a.token, type: 'string' }] }
    case 'basic': return { type: 'basic', basic: [{ key: 'username', value: a.user }, { key: 'password', value: a.pass }] }
    case 'custom': return { type: 'x-custom', 'x-custom': [{ key: 'value', value: a.custom }] }
  }
}

export function authHeader(a: AuthDraft): string {
  if (a.type === 'bearer') return a.token ? 'Bearer ' + a.token : ''
  if (a.type === 'basic') return a.user || a.pass ? 'Basic ' + btoa(unescape(encodeURIComponent(`${a.user}:${a.pass}`))) : ''
  if (a.type === 'custom') return a.custom
  return ''
}

/** Eng yaqin ota (papka → collection) dan meros: `chain` — ichkaridan tashqariga `auth` obyektlari. */
export function resolveAuth(a: AuthDraft, chain: PmAuth[]): AuthDraft {
  if (a.type !== 'inherit') return a
  for (const p of chain) { const d = authFromPm(p); if (d.type !== 'inherit') return d }
  return emptyAuth('none')
}
