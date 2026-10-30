/** O'zgaruvchi scope'lari (Postman tartibi, past → yuqori): Global < Collection < Papka(lar) < Environment [< Data < Local — bajarilish paytida]. */
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { isFolder, type Collection, type FolderItem, type TreeItem } from '../types/model'
import { resolveAuth, authHeader, type AuthDraft, type PmAuth } from './auth'
import { specFromDraft, type RequestDraft } from './draft'

export interface VarInfo { value: string; scope: string; secret: boolean }
export type VarMap = Record<string, VarInfo>

type Raw = { key?: string; value?: any; disabled?: boolean; enabled?: boolean; type?: string }
export function layer(out: VarMap, rows: Raw[] | undefined, scope: string) {
  for (const v of rows ?? []) {
    if (!v?.key || v.disabled || v.enabled === false) continue
    out[v.key] = { value: v.value == null ? '' : String(v.value), scope, secret: v.type === 'secret' }
  }
}

/** Collection'dan elementgacha papkalar (tashqaridan ichkariga). */
export function folderPath(col: Collection | undefined, id: string | null): FolderItem[] {
  if (!col || !id) return []
  const walk = (xs: TreeItem[], trail: FolderItem[]): FolderItem[] | null => {
    for (const x of xs) {
      if (x.id === id) return trail
      if (isFolder(x)) { const r = walk(x.item, [...trail, x]); if (r) return r }
    }
    return null
  }
  return walk(col.item, []) ?? []
}

/** `ref` = "collectionId:itemId" | "collectionId" | null (saqlanmagan so'rov). */
export function scopedVars(ref: string | null): VarMap {
  const tree = useTree(), ws = useWorkspace()
  const out: VarMap = {}
  layer(out, ws.globals as Raw[], 'Globals')
  const [cid, id] = (ref ?? '').split(':')
  const col = cid ? tree.cols[cid] : undefined
  if (col) {
    layer(out, col.variable as Raw[], 'Collection')
    for (const f of folderPath(col, id || null)) layer(out, (f as any).variable, 'Folder: ' + f.name)
  }
  layer(out, ws.activeEnv?.values as Raw[], 'Environment')
  return out
}
export const flatVars = (ref: string | null): Record<string, string> =>
  Object.fromEntries(Object.entries(scopedVars(ref)).map(([k, v]) => [k, v.value]))

/** Elementning (yoki papkaning) auth meros zanjiri: ichkaridan tashqariga, oxirida collection. `self` — papka bo'lsa uning o'zi ham kiradi. */
export function authChain(ref: string | null, includeSelfFolder = false): PmAuth[] {
  const [cid, id] = (ref ?? '').split(':')
  const col = cid ? useTree().cols[cid] : undefined
  if (!col) return []
  const path = folderPath(col, id || null)
  if (includeSelfFolder && id) { const self = useTree().findItem(cid, id); if (self && isFolder(self)) path.push(self) }
  return [...path.reverse().map(f => (f as any).auth as PmAuth), col.auth as PmAuth]
}

export const effectiveAuth = (a: AuthDraft, ref: string | null) => resolveAuth(a, authChain(ref))

/** Qoralama + meros auth + scope'li o'zgaruvchilar → engine spec. */
export function specFor(d: RequestDraft, ref: string | null, extraVars: Record<string, string> = {}) {
  const spec = specFromDraft(d, { ...flatVars(ref), ...extraVars })
  spec.authorization = authHeader(effectiveAuth(d.auth, ref))
  return spec
}
