/** Example'lar (Postman `item.response[]`): identifikatorlar, tab ochish, status matni. */
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import type { RequestItem } from '../types/model'
import type { Tab } from '../stores/tabs'
import { emptyKV, type KV } from './draft'
import { showToast } from './ui'

export interface Example {
  id?: string; name: string; originalRequest?: any; status?: string; code?: number; _postman_previewlanguage?: string
  header?: { key: string; value: string }[]; cookie?: unknown[]; body?: string
}
export const exId = () => 'ex' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
export const examplesOf = (it: unknown): Example[] => ((it as RequestItem | null)?.response ?? []) as Example[]

export const STATUS_TEXT: Record<number, string> = { 200: 'OK', 201: 'Created', 202: 'Accepted', 204: 'No Content', 301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 409: 'Conflict', 422: 'Unprocessable Entity', 429: 'Too Many Requests', 500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable' }

/** Id'siz example'larga id beradi (eski yozuvlar); o'zgargan bo'lsa serverga yozadi. */
export async function ensureExampleIds(cid: string, reqId: string): Promise<Example[]> {
  const tree = useTree()
  const it = tree.findItem(cid, reqId) as RequestItem | null
  const list = examplesOf(it)
  if (!list.some(e => !e.id)) return list
  const next = list.map(e => (e.id ? e : { ...e, id: exId() }))
  await tree.updateItem(cid, reqId, { response: next })
  return next
}

export async function openExample(cid: string, reqId: string, exampleId: string, name: string, permanent = true) {
  await ensureExampleIds(cid, reqId)
  const ex = examplesOf(useTree().findItem(cid, reqId)).find(e => e.id === exampleId || e.name === name)
  useTabs().open('example', `${cid}:${reqId}:${ex?.id ?? exampleId}`, name, { permanent })
}

export interface ExampleForm { name: string; code: number; status: string; lang: string; body: string; headers: KV[] }
export const exampleSnapshot = (f: ExampleForm) => JSON.stringify({ ...f, headers: f.headers.filter(h => h.key).map(h => [h.key, h.value]) })

export function formFromExample(e: Example): ExampleForm {
  return { name: e.name, code: e.code ?? (Number(e.status) || 200), status: e.status && !/^\d+$/.test(e.status) ? e.status : STATUS_TEXT[e.code ?? 0] ?? '', lang: e._postman_previewlanguage ?? 'json', body: e.body ?? '',
    headers: [...(e.header ?? []).map(h => ({ ...emptyKV(), key: h.key, value: h.value })), emptyKV()] }
}

/** Example tabini saqlaydi (forma `tab.state.form` da turadi — tab almashganda yo'qolmaydi). */
export async function saveExampleTab(tab: Tab): Promise<boolean> {
  const f = tab.state?.form as ExampleForm | undefined
  const [cid, reqId, id] = (tab.ref ?? '').split(':')
  if (!f) return true
  if (!f.name.trim()) { showToast('Nom kiriting', 'warn'); return false }
  const tree = useTree()
  const list = examplesOf(tree.findItem(cid, reqId))
  const next = list.map(e => (e.id === id ? { ...e, name: f.name.trim(), code: Number(f.code) || 0, status: f.status || STATUS_TEXT[Number(f.code)] || String(f.code), _postman_previewlanguage: f.lang, body: f.body, header: f.headers.filter(h => h.key).map(h => ({ key: h.key, value: h.value })) } : e))
  await tree.updateItem(cid, reqId, { response: next })
  tab.state!.saved = exampleSnapshot(f)
  useTabs().markSaved(tab.id, { title: f.name.trim() })
  return true
}
