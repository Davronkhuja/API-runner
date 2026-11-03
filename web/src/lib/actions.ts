import { post } from '../api/client'
import { useTabs, type Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { draftFromItem, extFromDraft, requestFromDraft } from './draft'
import { prepareAuth, specFor } from './scope'
import { showToast } from './ui'
import type { RequestItem } from '../types/model'

/** Saqlash dialogi kerak bo'lgan (hali saqlanmagan) tab uchun App.vue shuni to'ldiradi. */
export const saveAsHandler: { fn: ((tab: Tab) => Promise<boolean>) | null } = { fn: null }

export async function saveTab(tab: Tab): Promise<boolean> {
  const tabs = useTabs(), tree = useTree()
  await tabs.flush()
  if (tab.kind !== 'request' || !tab.draft) return true
  if (!tab.ref) return saveAsHandler.fn ? saveAsHandler.fn(tab) : false
  const [cid, id] = tab.ref.split(':')
  const request = requestFromDraft(tab.draft)
  await tree.updateItem(cid, id, { name: tab.draft.name, request, 'x-apirunner': extFromDraft(tab.draft) })
  tabs.markSaved(tab.id, { title: tab.draft.name })
  return true
}

export async function createRequestIn(tab: Tab, cid: string, parentId: string | null, name: string) {
  const tabs = useTabs(), tree = useTree()
  tab.draft!.name = name
  const id = await tree.addItem(cid, { name, request: requestFromDraft(tab.draft!), response: [], 'x-apirunner': extFromDraft(tab.draft!) }, parentId)
  tabs.markSaved(tab.id, { ref: `${cid}:${id}`, title: name })
  tree.reveal(cid, id)
}

export function openRequest(cid: string, id: string, permanent = false) {
  const tabs = useTabs(), tree = useTree()
  const item = tree.findItem(cid, id) as RequestItem | undefined
  if (!item) return null
  const ref = `${cid}:${id}`
  return tabs.open('request', ref, item.name, { permanent, draft: tabs.tabs.some(t => t.ref === ref) ? undefined : draftFromItem(item) })
}

export async function sendTab(tab: Tab) {
  if (!tab.draft || !tab.draft.url.trim()) { showToast('URL kiriting!', 'warn'); return }
  const hist = useHistory()
  await useTabs().flush()
  tab.response = { loading: true }
  try {
    await prepareAuth(tab.draft, tab.ref)
    const spec = specFor(tab.draft, tab.ref)
    spec.timeout = 30
    const r = await post('/run_one', spec)
    tab.response = r
    hist.add('request', { ...spec, env_vars: undefined, timestamp: Date.now(), status: r.status }).catch(() => {})
    hist.add('url', { method: tab.draft.method, url: tab.draft.url }).catch(() => {})
  } catch (e: any) {
    tab.response = { status: 'ERR', response: e.message, time: 0, size: 0, resp_headers: {}, url: tab.draft.url }
  }
}
