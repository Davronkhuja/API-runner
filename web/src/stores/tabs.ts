import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { get, put } from '../api/client'
import { newDraft, type RequestDraft } from '../lib/draft'

export type TabKind = 'request' | 'environment' | 'collection' | 'runner'

export interface Tab {
  id: string
  kind: TabKind
  /** Bog'langan element: request/collection -> "collectionId:itemId" yoki collectionId; environment -> envId. Yangi (saqlanmagan) tabda null. */
  ref: string | null
  title: string
  preview: boolean          // kursiv; keyingi bosishda almashadi
  dirty: boolean
  draft: RequestDraft | null
  /** Oxirgi javob va scroll — tab almashganda yo'qolmasligi uchun tabning o'zida. */
  response: any | null
  scroll: { req: number; resp: number }
  activeSection?: string    // Params/Headers/Auth/Body...
}

export interface Persistence { load(): Promise<any>; save(state: any): Promise<void> }
export const serverPersistence: Persistence = {
  load: () => get('/api/ui-state'),
  save: s => put('/api/ui-state', s).then(() => undefined),
}

let seq = 0
const uid = () => `t${Date.now().toString(36)}${(seq++).toString(36)}`

export const useTabs = defineStore('tabs', () => {
  const tabs = ref<Tab[]>([])
  const activeId = ref<string | null>(null)
  const closed = ref<Tab[]>([])           // Cmd+Shift+T uchun stek
  let persistence: Persistence = serverPersistence
  let timer: ReturnType<typeof setTimeout> | null = null

  const active = computed(() => tabs.value.find(t => t.id === activeId.value) ?? null)
  const indexOf = (id: string) => tabs.value.findIndex(t => t.id === id)

  // ── saqlash / tiklash (server tomonda: sahifa yangilanganda ham, server qayta ishga tushganda ham) ──
  function snapshot() {
    return {
      v: 1, activeId: activeId.value,
      tabs: tabs.value.map(t => ({ ...t, response: t.response ? { ...t.response, response: undefined, truncated: true } : null })),
    }
  }
  function persistNow() { return persistence.save({ ...(window as any).__uiStateExtra, tabs: snapshot() }).catch(() => {}) }
  function persistSoon() { if (timer) clearTimeout(timer); timer = setTimeout(persistNow, 300) }
  function setPersistence(p: Persistence) { persistence = p }
  async function restore() {
    try {
      const st = await persistence.load()
      ;(window as any).__uiStateExtra = { ...st, tabs: undefined }
      const s = st?.tabs
      if (s?.tabs?.length) {
        tabs.value = s.tabs
        activeId.value = tabs.value.some(t => t.id === s.activeId) ? s.activeId : tabs.value[0].id
      }
    } catch { /* birinchi ishga tushish */ }
  }

  function add(t: Partial<Tab> & { kind: TabKind }, at?: number): Tab {
    const tab: Tab = {
      id: uid(), ref: null, title: 'Yangi', preview: false, dirty: false, draft: null,
      response: null, scroll: { req: 0, resp: 0 }, ...t,
    }
    if (at === undefined) tabs.value.push(tab); else tabs.value.splice(at, 0, tab)
    activeId.value = tab.id
    persistSoon()
    return tab
  }

  /** Bir marta bosish -> preview, ikki marta/tahrir -> doimiy. Bir xil element ikkinchi marta ochilsa — mavjud tabga o'tiladi. */
  function open(kind: TabKind, ref: string, title: string, opts: { permanent?: boolean; draft?: RequestDraft | null } = {}) {
    const same = tabs.value.find(t => t.kind === kind && t.ref === ref)
    if (same) {
      activeId.value = same.id
      if (opts.permanent) same.preview = false
      persistSoon()
      return same
    }
    const previewIdx = tabs.value.findIndex(t => t.preview && !t.dirty)
    const base = { kind, ref, title, preview: !opts.permanent, draft: opts.draft ?? null }
    if (previewIdx >= 0) {
      const tab: Tab = { ...tabs.value[previewIdx], ...base, id: uid(), response: null, scroll: { req: 0, resp: 0 }, dirty: false }
      tabs.value.splice(previewIdx, 1, tab)
      activeId.value = tab.id
      persistSoon()
      return tab
    }
    return add(base)
  }

  function openNew(): Tab { return add({ kind: 'request', title: 'Yangi so\'rov', draft: newDraft() }) }

  function activate(id: string) { if (indexOf(id) >= 0) { activeId.value = id; persistSoon() } }
  function next(dir = 1) {
    if (!tabs.value.length) return
    const i = indexOf(activeId.value ?? '')
    activate(tabs.value[(i + dir + tabs.value.length) % tabs.value.length].id)
  }

  /** Tahrirlash tabni doimiy qiladi va dirty belgilaydi. */
  function touch(id: string) {
    const t = tabs.value.find(x => x.id === id)
    if (!t) return
    t.preview = false
    t.dirty = true
    persistSoon()
  }
  function markSaved(id: string, patch: Partial<Tab> = {}) {
    const t = tabs.value.find(x => x.id === id)
    if (t) { Object.assign(t, patch, { dirty: false }); persistSoon() }
  }

  /** Dirty tabni yopish `confirm` orqali: 'save' | 'discard' | 'cancel'. Yopilsa true. */
  async function close(id: string, confirm?: (t: Tab) => Promise<'save' | 'discard' | 'cancel'>, save?: (t: Tab) => Promise<void>): Promise<boolean> {
    const i = indexOf(id)
    if (i < 0) return true
    const t = tabs.value[i]
    if (t.dirty && confirm) {
      const ans = await confirm(t)
      if (ans === 'cancel') return false
      if (ans === 'save' && save) await save(t)
    }
    tabs.value.splice(i, 1)
    closed.value.push({ ...t, dirty: false })
    if (closed.value.length > 20) closed.value.shift()
    if (activeId.value === id) activeId.value = (tabs.value[i] ?? tabs.value[i - 1])?.id ?? null
    persistSoon()
    return true
  }
  async function closeMany(ids: string[], confirm?: Parameters<typeof close>[1], save?: Parameters<typeof close>[2]) {
    for (const id of ids) if (!(await close(id, confirm, save))) return false
    return true
  }
  const closeOthers = (id: string, c?: Parameters<typeof close>[1], s?: Parameters<typeof close>[2]) => closeMany(tabs.value.filter(t => t.id !== id).map(t => t.id), c, s)
  const closeRight = (id: string, c?: Parameters<typeof close>[1], s?: Parameters<typeof close>[2]) => closeMany(tabs.value.slice(indexOf(id) + 1).map(t => t.id), c, s)
  const closeAll = (c?: Parameters<typeof close>[1], s?: Parameters<typeof close>[2]) => closeMany(tabs.value.map(t => t.id), c, s)

  function reopenClosed(): Tab | null {
    const t = closed.value.pop()
    if (!t) return null
    const dupe = tabs.value.find(x => x.kind === t.kind && x.ref && x.ref === t.ref)
    if (dupe) { activate(dupe.id); return dupe }
    return add({ ...t, id: uid() })
  }

  function duplicate(id: string): Tab | null {
    const i = indexOf(id)
    if (i < 0) return null
    const t = tabs.value[i]
    return add({
      kind: t.kind, ref: null, title: t.title + ' Copy', draft: t.draft ? JSON.parse(JSON.stringify(t.draft)) : null,
      dirty: true, preview: false,
    }, i + 1)
  }

  /** Drag&drop tartiblash: `from` tabni `to` indeksiga qo'yadi. */
  function reorder(fromId: string, toIndex: number) {
    const from = indexOf(fromId)
    if (from < 0) return
    const [t] = tabs.value.splice(from, 1)
    tabs.value.splice(Math.max(0, Math.min(toIndex, tabs.value.length)), 0, t)
    persistSoon()
  }

  /** Daraxtdagi o'zgarishlar tabga ta'sir qiladi (o'chirish / nom o'zgarishi). */
  function retitle(ref: string, title: string) { tabs.value.filter(t => t.ref === ref).forEach(t => (t.title = title)); persistSoon() }
  function dropRef(ref: string) { tabs.value = tabs.value.filter(t => t.ref !== ref); if (!tabs.value.some(t => t.id === activeId.value)) activeId.value = tabs.value[0]?.id ?? null; persistSoon() }

  return { tabs, activeId, active, closed, restore, persistNow, setPersistence, add, open, openNew, activate, next, touch, markSaved, close, closeMany, closeOthers, closeRight, closeAll, reopenClosed, duplicate, reorder, retitle, dropRef }
})
