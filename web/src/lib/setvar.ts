/** "Set as variable": belgilangan matndan o'zgaruvchi yaratish (toza yordamchilar). */
export const VAR_NAME = /^[A-Za-z_$][\w.\-]*$/

/** Belgilangan matndan taklif nomi: kichik harf, so'zlar `_` bilan, 32 belgigacha. */
export function suggestVarName(text: string, hint = ''): string {
  const base = (hint || text).trim().toLowerCase().replace(/^https?:\/\//, '').replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 32).replace(/_+$/, '')
  return /^[a-z_]/.test(base) ? base : base ? 'v_' + base : 'value'
}

export function validateVarName(name: string): string | null {
  if (!name) return 'Nom kiriting'
  if (!VAR_NAME.test(name)) return "Nom harf/_ bilan boshlanib, faqat harf, raqam, _ . - dan iborat bo'lsin"
  return null
}

export type VarScope = 'environment' | 'globals' | 'collection'
export interface VarRow { key: string; value: string; current?: string | null; enabled?: boolean; type?: string; disabled?: boolean }

/** Qatorlarga yangi qiymatni qo'shadi/yangilaydi. `existed` — shu nom oldin bor edi. */
export function upsertVar<T extends VarRow>(rows: T[], key: string, value: string, make: (k: string, v: string) => T): { rows: T[]; existed: boolean } {
  const i = rows.findIndex(r => r.key === key)
  if (i < 0) return { rows: [...rows, make(key, value)], existed: false }
  const next = rows.slice()
  next[i] = { ...next[i], value, ...(next[i].current != null ? { current: value } : {}) }
  return { rows: next, existed: true }
}
