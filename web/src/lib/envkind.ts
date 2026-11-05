/** Muhit turi (Dev/Test/Prod) va xavfli so'rovlar tasdig'i. Server faqat `kind` va `confirm_writes` ni saqlaydi; qoida shu yerda. */
import type { Environment, EnvKind } from '../types/model'
import { useWorkspace } from '../stores/workspace'
import { askConfirm } from './ui'

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

/** Faol muhit talab qilsa, yozuvchi metod yuborishdan oldin tasdiq so'raydi. false — foydalanuvchi bekor qildi. */
export async function confirmWrite(method: string): Promise<boolean> {
  const env = useWorkspace().activeEnv
  if (!env || !isWrite(method) || !needsWriteConfirm(env)) return true
  return askConfirm(writeConfirmText(env, method), 'Yuborish')
}

/** Runner'da "faqat GET'ni belgilash": muhitda aniq belgilanmagan bo'lsa Prod uchun yoqiq, Dev/Test uchun o'chiq. */
export const runnerGetOnly = (env: Environment | null | undefined) => (env ? (env.runner_get_only ?? env.kind === 'prod') : false)
