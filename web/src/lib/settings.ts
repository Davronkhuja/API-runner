/** So'rov sozlamalari: global (workspace) + so'rov darajasidagi qayta belgilash. Faqat berilgan kalitlar yuboriladi. */
export interface ReqSettings {
  follow_redirects?: boolean; max_redirects?: number; http2?: boolean; ssl_verify?: boolean
  proxy?: string; cert?: string; cert_key?: string; ca_bundle?: string; use_cookies?: boolean
}
export const SETTING_KEYS: (keyof ReqSettings)[] = ['follow_redirects', 'max_redirects', 'http2', 'ssl_verify', 'proxy', 'cert', 'cert_key', 'ca_bundle', 'use_cookies']

const present = (v: unknown) => v !== undefined && v !== null && v !== '' && !(typeof v === 'number' && Number.isNaN(v))
export function cleanSettings(s: ReqSettings | undefined | null): ReqSettings {
  const out: Record<string, unknown> = {}
  for (const k of SETTING_KEYS) if (present((s as any)?.[k])) out[k] = (s as any)[k]
  return out as ReqSettings
}
/** So'rov sozlamalari globalni bosadi. */
export const mergeSettings = (global: ReqSettings | undefined, own: ReqSettings | undefined): ReqSettings => ({ ...cleanSettings(global), ...cleanSettings(own) })
