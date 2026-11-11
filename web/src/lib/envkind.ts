/** Muhit turi (Dev/Test/Prod) va xavfli so'rovlar tasdig'i. Server faqat `kind` va `confirm_writes` ni saqlaydi; qoida shu yerda. */
import type { Environment, EnvKind } from '../types/model'
import { useWorkspace } from '../stores/workspace'
import { askConfirm } from './ui'
import { hostInfo, hostLabel, safety } from './safety'

export const KINDS: { id: EnvKind; label: string }[] = [{ id: 'dev', label: 'Dev' }, { id: 'test', label: 'Test' }, { id: 'prod', label: 'Prod' }]
export const WRITE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
export const isWrite = (method: string) => WRITE_METHODS.includes((method || '').toUpperCase())
export const isProd = (env: Environment | null | undefined) => env?.kind === 'prod'
/** Yozuvchi so'rovlardan oldin tasdiq: muhitda yoqilgan bo'lsa; aniq qiymat berilmagan bo'lsa Prod uchun sukut bo'yicha yoqiq. */
export const needsWriteConfirm = (env: Environment | null | undefined) => !!env && (env.confirm_writes ?? env.kind === 'prod')
export const kindLabel = (k?: string) => KINDS.find(x => x.id === k)?.label ?? ''

export function writeConfirmText(env: Environment, method: string) {
  return `«${env.name}» (${kindLabel(env.kind) || 'muhit'}) faol. ${method.toUpperCase()} so'rovi ma'lumotni o'zgartirishi mumkin. Yuborilsinmi?`
}

/**
 * Yozuvchi metod yuborishdan oldin tasdiq: (1) faol muhit talab qilsa; (2) host bo'yicha — test/dev ro'yxatida bo'lmagan har qanday host (sozlamada o'chirish mumkin).
 * `url` berilmasa faqat muhit qoidasi. `count` > 1 — ketma-ket yuboriladigan so'rovlar soni (Batch). false — foydalanuvchi bekor qildi.
 */
export async function confirmWrite(method: string, url?: string, ref: string | null = null, count = 1): Promise<boolean> {
  if (!isWrite(method)) return true
  const env = useWorkspace().activeEnv
  const envAsks = !!env && needsWriteConfirm(env)
  const hi = url ? hostInfo(url, ref) : null
  const hostAsks = safety().host_confirm && !!hi && !hi.safe
  if (!envAsks && !hostAsks) return true
  const times = count > 1 ? ` (${count} marta)` : ''
  let text = ''
  if (hostAsks) text += `${method.toUpperCase()} so'rovi${times} «${hostLabel(hi!.host)}» ga yuboriladi — bu test/dev host emas, ma'lumot o'zgarishi mumkin. `
  if (envAsks) text += hostAsks ? `Faol muhit: «${env!.name}» (${kindLabel(env!.kind) || 'muhit'}). ` : writeConfirmText(env!, method) + ' '
  return askConfirm(text.trim() + ' Yuborilsinmi?', 'Yuborish')
}

