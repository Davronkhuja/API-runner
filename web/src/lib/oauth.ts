/** OAuth 2.0 token xotirasi, oqimlar (Client Credentials, Password, Authorization Code [+PKCE], Implicit) va avtomatik yangilash. */
import { reactive } from 'vue'
import { post } from '../api/client'
import type { AuthDraft } from './auth'

export interface OToken { access_token: string; token_type?: string; refresh_token?: string; expires_at?: number; scope?: string; obtained: number }
const STORE = 'apirunner_oauth_tokens'
const tokens = reactive<Record<string, OToken>>({})
try { Object.assign(tokens, JSON.parse(sessionStorage.getItem(STORE) ?? '{}')) } catch { /* ixtiyoriy */ }
const persist = () => { try { sessionStorage.setItem(STORE, JSON.stringify(tokens)) } catch { /* ixtiyoriy */ } }

const DIRECT = ['client_credentials', 'password']
export const isCodeFlow = (g: string) => g === 'authorization_code' || g === 'authorization_code_pkce' || g === 'implicit'

/** Token shu sozlamaga bog'lanadi (xom qiymatlar, o'zgaruvchilar yechilmasdan). */
export function tokenKey(a: AuthDraft): string {
  const c = a.cfg
  return [c.grant_type, c.accessTokenUrl, c.authUrl, c.clientId, c.scope, c.username].join('|')
}
export const tokenFor = (a: AuthDraft): OToken | null => tokens[tokenKey(a)] ?? null
export const clearToken = (a: AuthDraft) => { delete tokens[tokenKey(a)]; persist() }
export const isExpired = (t: OToken, skew = 10) => !!t.expires_at && t.expires_at - skew <= Math.floor(Date.now() / 1000)

export const resolveVars = (text: string, vars: Record<string, string>) => (text ?? '').replace(/\{\{\s*([^}]+?)\s*\}\}/g, (m, k) => (k in vars ? vars[k] : m))

function store(a: AuthDraft, t: any): OToken {
  const tok: OToken = { access_token: t.access_token, token_type: t.token_type, refresh_token: t.refresh_token, expires_at: t.expires_at, scope: t.scope, obtained: Date.now() }
  tokens[tokenKey(a)] = tok; persist()
  return tok
}

function tokenBody(a: AuthDraft, vars: Record<string, string>, extra: Record<string, string>) {
  const c = a.cfg
  return { token_url: c.accessTokenUrl, client_id: c.clientId, client_secret: c.clientSecret, scope: c.scope, username: c.username, password: c.password,
           client_auth: c.client_authentication === 'body' ? 'body' : 'header', variables: vars, ...extra }
}

const b64url = (b: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const rand = (n = 48) => b64url(crypto.getRandomValues(new Uint8Array(n)).buffer).slice(0, n)
export async function pkcePair() {
  const verifier = rand(64)
  return { verifier, challenge: b64url(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))) }
}

/** Authorization Code / PKCE / Implicit: popup ochadi, /oauth/callback `postMessage` yuboradi. */
async function authorize(a: AuthDraft, vars: Record<string, string>): Promise<OToken> {
  const c = a.cfg, g = c.grant_type
  const redirect = resolveVars(c.redirect_uri || '', vars) || `${location.origin}/oauth/callback`
  const state = c.state ? resolveVars(c.state, vars) : rand(16)
  const q = new URLSearchParams({ response_type: g === 'implicit' ? 'token' : 'code', client_id: resolveVars(c.clientId, vars), redirect_uri: redirect, state })
  if (c.scope) q.set('scope', resolveVars(c.scope, vars))
  let verifier = ''
  if (g === 'authorization_code_pkce') { const p = await pkcePair(); verifier = p.verifier; q.set('code_challenge', p.challenge); q.set('code_challenge_method', 'S256') }
  const base = resolveVars(c.authUrl, vars)
  if (!/^https?:\/\//i.test(base)) throw new Error('Auth URL (http/https) kiriting')
  const popup = window.open(base + (base.includes('?') ? '&' : '?') + q.toString(), 'apirunner-oauth', 'width=620,height=760')
  if (!popup) throw new Error('Popup bloklandi — brauzerda ruxsat bering')
  const result = await new Promise<{ search: string; hash: string }>((resolve, reject) => {
    const done = (fn: () => void) => { window.removeEventListener('message', on); clearInterval(poll); clearTimeout(to); fn() }
    const on = (e: MessageEvent) => { if (e.origin === location.origin && e.data?.type === 'apirunner-oauth') done(() => resolve(e.data)) }
    const poll = setInterval(() => { if (popup.closed) setTimeout(() => done(() => reject(new Error('Avtorizatsiya oynasi yopildi'))), 600) }, 500)
    const to = setTimeout(() => done(() => reject(new Error('Avtorizatsiya vaqti tugadi'))), 300_000)
    window.addEventListener('message', on)
  })
  const p = new URLSearchParams(g === 'implicit' ? result.hash.replace(/^#/, '') : result.search.replace(/^\?/, ''))
  if (p.get('error')) throw new Error(`Avtorizatsiya xatosi: ${p.get('error_description') || p.get('error')}`)
  if (p.get('state') !== state) throw new Error('State mos kelmadi (CSRF himoyasi)')
  if (g === 'implicit') {
    if (!p.get('access_token')) throw new Error('Javobda access_token yo\'q')
    const exp = Number(p.get('expires_in'))
    return store(a, { access_token: p.get('access_token'), token_type: p.get('token_type') ?? 'Bearer', ...(exp ? { expires_at: Math.floor(Date.now() / 1000) + exp } : {}) })
  }
  const code = p.get('code')
  if (!code) throw new Error('Javobda code yo\'q')
  const r = await post('/api/oauth2/token', tokenBody(a, vars, { grant_type: 'authorization_code', code, redirect_uri: redirect, ...(verifier ? { code_verifier: verifier } : {}) }))
  return store(a, r.token)
}

/** "Get New Access Token": har qanday grant uchun yangi token. */
export async function getNewToken(a: AuthDraft, vars: Record<string, string>): Promise<OToken> {
  const g = a.cfg.grant_type
  if (isCodeFlow(g)) return authorize(a, vars)
  const r = await post('/api/oauth2/token', tokenBody(a, vars, { grant_type: g }))
  return store(a, r.token)
}

/** Yuborishdan oldin: token bo'lmasa (to'g'ridan-to'g'ri grantlar) olinadi, eskirgan bo'lsa yangilanadi. Code oqimlarida token yo'q bo'lsa xato. */
export async function ensureToken(a: AuthDraft, vars: Record<string, string>): Promise<void> {
  const t = tokenFor(a)
  if (t && !isExpired(t)) return
  if (t?.refresh_token) {
    try { const r = await post('/api/oauth2/token', tokenBody(a, vars, { grant_type: 'refresh_token', refresh_token: t.refresh_token })); store(a, { refresh_token: t.refresh_token, ...r.token }); return } catch { /* refresh bo'lmadi — pastda qayta olinadi */ }
  }
  if (DIRECT.includes(a.cfg.grant_type)) { await getNewToken(a, vars); return }
  throw new Error(t ? 'OAuth token muddati tugagan — Auth tabida "Get New Access Token" bosing' : 'OAuth token yo\'q — Auth tabida "Get New Access Token" bosing')
}
