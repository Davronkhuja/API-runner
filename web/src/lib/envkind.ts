/** Muhit turi (Dev/Test/Prod) va xavfli so'rovlar tasdig'i. Server faqat `kind` va `confirm_writes` ni saqlaydi; qoida shu yerda. */
import type { Environment, EnvKind } from '../types/model'
import { useWorkspace } from '../stores/workspace'
import { reactive } from 'vue'
import { askConfirm, askConfirmChecks } from './ui'
import { hostInfo, hostLabel, isProdHost, safety } from './safety'

export const KINDS: { id: EnvKind; label: string }[] = [{ id: 'dev', label: 'Dev' }, { id: 'test', label: 'Test' }, { id: 'prod', label: 'Prod' }]
export const WRITE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
export const isWrite = (method: string) => WRITE_METHODS.includes((method || '').toUpperCase())
export const isProd = (env: Environment | null | undefined) => env?.kind === 'prod'
export const kindLabel = (k?: string) => KINDS.find(x => x.id === k)?.label ?? ''

/** Shu sessiyada (sahifa yangilanguncha) «boshqa so'ramaslik» deb belgilangan host'lar. Sozlamalar → Xavfsizlik'da ko'rinadi va qaytarib olinadi. */
export const sessionSkipHosts = reactive(new Set<string>())

/**
 * Tasdiq so'rash kerakmi (YAGONA so'rov): faqat sozlamada yoqilgan bo'lsa (sukut O'CHIQ) va faqat DELETE uchun, hamda muhit Prod yoki host foydalanuvchining
 * «prod» ro'yxatida bo'lsa. POST/PUT/PATCH kundalik ish — so'ralmaydi. Host «boshqa so'ramaslik» ro'yxatida bo'lsa ham so'ralmaydi.
 */
export function singleConfirmReason(method: string, url: string | undefined, ref: string | null): { host: string | null; prodEnv: boolean; prodHost: boolean } | null {
  const sf = safety()
  if (!sf.single_confirm || (method || '').toUpperCase() !== 'DELETE') return null
  const env = useWorkspace().activeEnv
  const host = url ? hostInfo(url, ref).host : null
  const prodEnv = isProd(env), prodHost = isProdHost(host)
  if (!prodEnv && !prodHost) return null
  if (sessionSkipHosts.has('*') || (host && (sf.skip_hosts.includes(host) || sessionSkipHosts.has(host)))) return null
  return { host, prodEnv, prodHost }
}

/**
 * Yuborishdan oldin tasdiq. count > 1 (Batch) — ketma-ket yozuvchi so'rovlar: muhit/host qoidasi bo'yicha (Runner'dagi RunGuard kabi himoya).
 * count == 1 — yagona so'rov: `singleConfirmReason` (sukut o'chiq). false — foydalanuvchi bekor qildi.
 */
export async function confirmWrite(method: string, url?: string, ref: string | null = null, count = 1): Promise<boolean> {
  if (count > 1) return confirmBatchWrite(method, url, ref, count)
  const why = singleConfirmReason(method, url, ref)
  if (!why) return true
  const env = useWorkspace().activeEnv
  const where = why.prodHost ? `«${hostLabel(why.host)}» (prod host)` : `«${env!.name}» (Prod muhit)`
  const checks = [...(why.host ? [{ id: 'host', label: 'Bu host uchun boshqa so\'ramaslik' }] : []), { id: 'session', label: 'Bu sessiyada boshqa so\'ramaslik' }]
  const r = await askConfirmChecks(`DELETE so'rovi ${where} ga yuboriladi va ma'lumotni o'chirishi mumkin. Yuborilsinmi?`, 'Yuborish', checks)
  if (!r.ok) return false
  if (why.host && r.checked.includes('host')) { const sf = safety(); await useWorkspace().saveSafety({ ...sf, skip_hosts: [...new Set([...sf.skip_hosts, why.host])] }) }
  else if (why.host && r.checked.includes('session')) sessionSkipHosts.add(why.host)
  else if (r.checked.includes('session')) sessionSkipHosts.add('*')
  return true
}

async function confirmBatchWrite(method: string, url: string | undefined, ref: string | null, count: number): Promise<boolean> {
  if (!isWrite(method)) return true
  const env = useWorkspace().activeEnv
  const hi = url ? hostInfo(url, ref) : null
  const hostAsks = !!hi && !hi.safe
  if (!hostAsks && !isProd(env)) return true
  let text = `${method.toUpperCase()} so'rovi (${count} marta) `
  text += hostAsks ? `«${hostLabel(hi!.host)}» ga yuboriladi — bu test/dev host emas, ma'lumot o'zgarishi mumkin. ` : ''
  if (isProd(env)) text += `Faol muhit: «${env!.name}» (Prod). `
  return askConfirm(text.trim() + ' Yuborilsinmi?', 'Yuborish')
}

