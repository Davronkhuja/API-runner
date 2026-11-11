/** Xavfsizlik qoidalari so'rovning O'ZIGA qaraydi (metod + host), muhit turiga emas: muhitsiz yoki noto'g'ri turdagi muhitda ham prod host'ga yozuvchi so'rov himoyasiz ketmasin. */
import { useWorkspace } from '../stores/workspace'
import { flatVars } from './scope'

export const SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']
export const isSafeMethod = (m: string) => SAFE_METHODS.includes((m || '').toUpperCase())
import { DEFAULT_SAFETY, type Safety } from './settings'
export type { Safety }
export const safety = (): Safety => ({ ...DEFAULT_SAFETY, ...(useWorkspace().safety ?? {}) })

/** `{{var}}` larni hozirgi qamrov qiymatlari bilan almashtiradi (3 daraja chuqurlikkacha). Topilmaganlari joyida qoladi. */
export function resolveVars(raw: string, ref: string | null): string {
  const vars = flatVars(ref)
  let s = raw
  for (let i = 0; i < 3 && s.includes('{{'); i++) s = s.replace(/\{\{\s*([^{}\s]+)\s*\}\}/g, (m, k) => (k in vars ? String(vars[k]) : m))
  return s
}
/** URL'dan host (portsiz, kichik harf). Hal qilinmagan o'zgaruvchi yoki noto'g'ri URL — null (noma'lum = xavfli). */
export function hostOf(url: string): string | null {
  const t = url.trim()
  if (!t || t.includes('{{')) return null
  try { return new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(t) ? t : 'http://' + t).hostname.replace(/^\[|\]$/g, '').toLowerCase() || null } catch { return null }
}
const BUILTIN = (h: string) => h === 'localhost' || h === '127.0.0.1' || h === '::1' || h.endsWith('.localhost') || h.endsWith('.local') || h.endsWith('.test')
export function isTestHost(host: string | null, extra: string[] = safety().test_hosts): boolean {
  if (!host) return false
  if (BUILTIN(host)) return true
  return extra.some(p => { const x = p.trim().toLowerCase(); return x && (x.startsWith('*.') ? host === x.slice(2) || host.endsWith(x.slice(1)) : host === x) })
}
export interface HostInfo { host: string | null; safe: boolean }
export function hostInfo(url: string, ref: string | null): HostInfo {
  const host = hostOf(resolveVars(url, ref))
  return { host, safe: isTestHost(host) }
}
export const hostLabel = (h: string | null) => h ?? "noma'lum (o'zgaruvchi hal qilinmadi)"
