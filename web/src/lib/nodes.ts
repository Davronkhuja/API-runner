/** Collection / papka tablari, ular orasida o'tish va auth'ni aniqlash yordamchilari. */
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { isFolder, type RequestItem, type TreeItem } from '../types/model'
import { folderPath } from './scope'

export const AUTH_NAMES: Record<string, string> = {
  bearer: 'Bearer Token', basic: 'Basic Auth', apikey: 'API Key', oauth2: 'OAuth 2.0', digest: 'Digest Auth', awsv4: 'AWS Signature V4', jwt: 'JWT Bearer', hawk: 'Hawk', ntlm: 'NTLM', 'x-custom': 'Custom', noauth: "Auth yo'q",
}
export const authName = (pm: { type?: string } | null | undefined) => (pm?.type ? AUTH_NAMES[pm.type] ?? pm.type : '')
/** O'z auth'i bor (meros emas) va haqiqiy auth (noauth emas). */
export const hasRealAuth = (pm: { type?: string } | null | undefined) => !!pm && !!pm.type && pm.type !== 'noauth'

export type Section = 'overview' | 'auth' | 'vars' | 'scripts' | 'run'
/** Collection (`id` bo'sh) yoki papka tabini ochadi (Postman kabi: Overview | Auth | Variables | Scripts | Run). */
export function openNodeTab(cid: string, id: string | null, section: Section = 'overview', preview = false) {
  const tabs = useTabs(), tree = useTree()
  const col = tree.cols[cid]
  if (!col) return null
  const node = id ? tree.findItem(cid, id) : undefined
  const t = tabs.open('collection', id ? `${cid}:${id}` : cid, id ? node?.name ?? '' : col.info.name, { permanent: !preview })
  t.state ??= {}
  t.state.section = section
  return t
}

/** Tugun ichidagi (rekursiv) so'rovlar. */
export function requestsIn(items: TreeItem[]): { item: RequestItem; path: string }[] {
  const out: { item: RequestItem; path: string }[] = []
  const walk = (xs: TreeItem[], path: string) => { for (const x of xs) { if (isFolder(x)) walk(x.item, path + x.name + ' / '); else out.push({ item: x as RequestItem, path }) } }
  walk(items, '')
  return out
}

/** `pm` auth obyektlarini kalit tartibidan qat'i nazar solishtirish. */
export function sameAuth(a: any, b: any): boolean {
  const norm = (v: any): any => (Array.isArray(v) ? v.map(norm) : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v).sort().filter(k => v[k] !== undefined).map(k => [k, norm(v[k])])) : v)
  // `type: 'string'` kabi yordamchi maydonlar farqi hisobga olinmaydi (bearer[].type)
  const strip = (v: any): any => (Array.isArray(v) ? v.map(strip) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).filter(([k]) => k !== 'type' || typeof v.type !== 'string' || 'key' in v === false).map(([k, x]) => [k, strip(x)])) : v)
  return JSON.stringify(norm(strip(a))) === JSON.stringify(norm(strip(b)))
}

/**
 * Tugunga auth qo'yilganda o'zgarishi mumkin bo'lgan so'rovlar: ichida (rekursiv) o'z auth'i bor, lekin yaqinroq ota-papkasining
 * o'z auth'i yo'q (aks holda ular baribir shu tugunning auth'ini ishlatmasdi). `same` — yangi auth bilan bir xil (masalan, tokenlar bir xil).
 */
export function overridableRequests(cid: string, nodeId: string | null, newAuth: any) {
  const tree = useTree()
  const col = tree.cols[cid]
  if (!col) return []
  const items = nodeId ? (tree.findItem(cid, nodeId) as any)?.item ?? [] : col.item
  const out: { id: string; name: string; path: string; auth: any; same: boolean; noauth: boolean }[] = []
  const walk = (xs: TreeItem[], path: string, blocked: boolean) => {
    for (const x of xs) {
      if (isFolder(x)) { walk(x.item, path + x.name + ' / ', blocked || ((x as any).auth && (x as any).auth.type !== undefined && !!(x as any).auth)); continue }
      const a = (x as RequestItem).request?.auth
      if (!blocked && a && a.type) out.push({ id: x.id, name: x.name, path, auth: a, same: sameAuth(a, newAuth), noauth: a.type === 'noauth' })
    }
  }
  walk(items, '', false)
  return out
}
void folderPath
