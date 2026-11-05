import { post } from '../api/client'
import { useTabs, type Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { draftFromItem, eventsFromDraft, extFromDraft, requestFromDraft } from './draft'
import { applyScriptResult, scriptsFor } from './scripts'
import { logRequest, logResponse } from './console'
import { prepareAuth, specFor } from './scope'
import { askConfirm, showToast } from './ui'
import { missingFilesOf } from './files'
import { confirmWrite } from './envkind'
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
  const existing = (tree.findItem(cid, id) as any)?.event
  // Nom bu yerda YOZILMAYDI: u yagona manbadan (daraxt/server, lib/rename.ts) keladi — Save qayta nomlashni bosib ketmasin
  await tree.updateItem(cid, id, { request, event: eventsFromDraft(tab.draft, existing), 'x-apirunner': extFromDraft(tab.draft) })
  tabs.markSaved(tab.id, { title: (tree.findItem(cid, id) as any)?.name ?? tab.draft.name })
  return true
}

export async function createRequestIn(tab: Tab, cid: string, parentId: string | null, name: string) {
  const tabs = useTabs(), tree = useTree()
  tab.draft!.name = name
  const id = await tree.addItem(cid, { name, request: requestFromDraft(tab.draft!), response: [], event: eventsFromDraft(tab.draft!), 'x-apirunner': extFromDraft(tab.draft!) }, parentId)
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

/** Tarixga javob natijasi: faqat havola (`response_id`) — matn serverda bitta nusxada (SQLite), dublikat saqlanmaydi. */
function historyResult(r: any) {
  return { time: r.time, size: r.size, ...(r.response_id ? { response_id: r.response_id } : {}) }
}

export async function sendTab(tab: Tab) {
  if (!tab.draft || !tab.draft.url.trim()) { showToast('URL kiriting!', 'warn'); return }
  if (!(await confirmWrite(tab.draft.method))) return
  const missing = await missingFilesOf(tab.draft)
  if (missing.length && !(await askConfirm(`Fayl topilmadi: ${missing.map(m => m.name).join(', ')}. Body'da faylni qayta tanlang. Baribir yuborilsinmi? (xato qaytadi)`, 'Baribir yuborish'))) return
  const hist = useHistory()
  await useTabs().flush()
  tab.response = { loading: true }
  try {
    await prepareAuth(tab.draft, tab.ref)
    const spec = specFor(tab.draft, tab.ref)
    spec.timeout = 30
    spec.ref = tab.ref                        // oxirgi natija serverda (SQLite last_results) — Folder Overview uchun
    spec.store_response = true               // javob serverda saqlanadi (sahifa yangilangach tiklash)
    const scripts = scriptsFor(tab.ref, tab.draft.scripts, tab.draft.name)
    if (scripts) Object.assign(spec, { scripts, ref: tab.ref, scripts_info: { requestName: tab.draft.name, requestId: tab.ref?.split(':')[1] ?? '' } })
    logRequest(spec.method, tab.draft.url, tab.id)
    const r = await post('/run_one', spec)
    tab.response = r
    useTabs().persistSoon()          // holat/o'lcham/sarlavhalar sahifa yangilanganda ham qoladi (matn emas)
    logResponse(r, tab.id)
    await applyScriptResult(r.scripts, { tabId: tab.id, ref: tab.ref })
    hist.add('request', { ...spec, store_response: undefined, env_vars: undefined, scripts: undefined, ref: undefined, scripts_info: undefined, timestamp: Date.now(), status: r.status, ...historyResult(r) }).catch(() => {})
    hist.add('url', { method: tab.draft.method, url: tab.draft.url }).catch(() => {})
  } catch (e: any) {
    tab.response = { status: 'ERR', response: e.message, time: 0, size: 0, resp_headers: {}, url: tab.draft.url }
  }
}
