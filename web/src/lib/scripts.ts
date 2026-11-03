/** Pre-request / Tests skriptlari: Postman `event` ↔ matn, meros zanjiri (collection → papka → so'rov), natijani qo'llash. */
import { useTabs, type Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { isFolder, type TreeItem } from '../types/model'
import { folderPath } from './scope'
import { ref } from 'vue'
import { logScripts } from './console'

/** Oxirgi bajarilishdagi skript xatolari (collection/papka tabida qator belgilash uchun). */
export const lastErrors = ref<ScriptError[]>([])

export interface ScriptSrc { source: string; kind: 'prerequest' | 'test'; scope: 'collection' | 'folder' | 'request'; name: string; id: string }
export interface ScriptSet { pre: string; test: string }
export interface ScriptError { name: string; message: string; stack?: string; line: number | null; origin: { kind: string; scope: string; name: string; id: string } }
export interface TestResult { name: string; passed: boolean; skipped: boolean; legacy?: boolean; error: ScriptError | null; origin: ScriptError['origin'] }
export interface ScriptResult {
  available: boolean; tests: TestResult[]; console: any[]; errors: ScriptError[]; skipped?: boolean; next_set?: boolean; next_request?: string | null
  changed?: string[]; aborted?: boolean; message?: string; install?: string
}

export const emptyScripts = (): ScriptSet => ({ pre: '', test: '' })

/** Postman `event[]` (yoki eski `events`) dan matn. */
export function textFromEvents(node: any): ScriptSet {
  const pick = (listen: string) => {
    const ev = ((node?.event ?? node?.events) as any[] | undefined)?.find(e => e.listen === listen)
    const ex = ev?.script?.exec
    return Array.isArray(ex) ? ex.join('\n') : typeof ex === 'string' ? ex : ''
  }
  return { pre: pick('prerequest'), test: pick('test') }
}

/** Matndan `event[]`; boshqa (skript bo'lmagan) yozuvlar saqlanadi. */
export function eventsFromText(existing: any[] | undefined, s: ScriptSet): any[] {
  const keep = (existing ?? []).filter(e => e.listen !== 'prerequest' && e.listen !== 'test')
  const mk = (listen: string, src: string) => (src.trim() ? [{ listen, script: { type: 'text/javascript', exec: src.split('\n') } }] : [])
  return [...mk('prerequest', s.pre), ...mk('test', s.test), ...keep]
}

/** Zanjir: collection → papkalar (tashqaridan ichkariga) → so'rov (draft matni). `ref`: "cid:itemId" | null. */
export function scriptsFor(ref: string | null, own?: ScriptSet, ownName = ''): { prerequest: ScriptSrc[]; test: ScriptSrc[] } | undefined {
  const tree = useTree()
  const [cid, id] = (ref ?? '').split(':')
  const col = cid ? tree.cols[cid] : undefined
  const nodes: { scope: ScriptSrc['scope']; name: string; id: string; s: ScriptSet }[] = []
  if (col) {
    nodes.push({ scope: 'collection', name: col.info.name, id: col.info._postman_id, s: textFromEvents(col) })
    for (const f of folderPath(col, id || null)) nodes.push({ scope: 'folder', name: f.name, id: f.id, s: textFromEvents(f) })
  }
  if (own) nodes.push({ scope: 'request', name: ownName, id: id ?? '', s: own })
  const out = { prerequest: [] as ScriptSrc[], test: [] as ScriptSrc[] }
  for (const n of nodes) {
    if (n.s.pre.trim()) out.prerequest.push({ source: n.s.pre, kind: 'prerequest', scope: n.scope, name: n.name, id: n.id })
    if (n.s.test.trim()) out.test.push({ source: n.s.test, kind: 'test', scope: n.scope, name: n.name, id: n.id })
  }
  return out.prerequest.length || out.test.length ? out : undefined
}

/** Server skript natijasini qaytargach: o'zgargan scope'larni yangilash va Console'ga yozish. */
export async function applyScriptResult(sc: ScriptResult | null | undefined, ctx: { tabId?: string; ref?: string | null } = {}) {
  if (!sc) return
  lastErrors.value = [...(sc.errors ?? []), ...(sc.tests ?? []).filter(t => !t.passed && t.error).map(t => ({ ...t.error!, origin: t.origin }))]
  logScripts(sc, ctx)
  if (sc.changed?.length) {
    const ws = useWorkspace(), tree = useTree()
    await ws.load()
    if (sc.changed.includes('collection') && ctx.ref) await tree.reloadCollection(ctx.ref.split(':')[0])
  }
}

/** Xato qatoriga o'tish: so'rov skripti — shu tabdagi muharrir; collection/papka — o'sha sozlamalar tabi. */
export function openScriptAt(tab: Tab | null, err: Pick<ScriptError, 'line' | 'origin'>) {
  const tabs = useTabs(), tree = useTree()
  const goto = { kind: err.origin.kind === 'prerequest' ? 'pre' : 'test', line: err.line ?? 1, nonce: Date.now() }
  if (err.origin.scope === 'request' && tab?.kind === 'request') {
    tabs.activate(tab.id); tab.activeSection = 'scripts'; tab.state ??= {}; tab.state.scriptGoto = goto
    return
  }
  const [cid] = (tab?.ref ?? '').split(':')
  const col = tree.cols[cid]
  if (!col) return
  let ref = cid, title = col.info.name
  if (err.origin.scope === 'folder') {
    const f = findFolder(col.item, err.origin.id)
    if (f) { ref = `${cid}:${f.id}`; title = f.name }
  }
  const t = tabs.open('collection', ref, title, { permanent: true })
  t.state ??= {}; t.state.section = 'scripts'; t.state.scriptGoto = goto
}
function findFolder(items: TreeItem[], id: string): TreeItem | undefined {
  for (const x of items) { if (isFolder(x)) { if (x.id === id) return x; const r = findFolder(x.item, id); if (r) return r } }
}
