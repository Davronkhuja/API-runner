import { defineStore } from 'pinia'
import { reactive, watch } from 'vue'
import { eventSource, get, post } from '../api/client'
import { useTabs, type Tab } from './tabs'
import { useHistory } from './history'
import { prepareAuth, specFor } from '../lib/scope'
import { scriptsFor } from '../lib/scripts'
import { logScripts } from '../lib/console'
import { showToast } from '../lib/ui'

export interface ProtoEvent { seq: number; ts: number; type: string; dir?: 'in' | 'out'; kind?: 'text' | 'binary'; data?: string; size?: number; event?: string; id?: string | null; message?: string; code?: number; reason?: string; attempt?: number; delay?: number; subprotocol?: string | null; status?: number; headers?: Record<string, string>; warning?: string | null; content_type?: string; last_event_id?: string }
export interface Conn { sessionId: string | null; status: 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'; events: ProtoEvent[]; counts: Record<string, number>; url: string; error: string; lost: boolean }
export const MAX_UI_EVENTS = 5000

const blank = (): Conn => ({ sessionId: null, status: 'idle', events: [], counts: { in: 0, out: 0, bytes_in: 0, bytes_out: 0, errors: 0 }, url: '', error: '', lost: false })

/** WebSocket / SSE ulanishlari (tab bo'yicha): server sessiyasi + SSE oqimi. Tab almashganda oqim uzilmaydi. */
export const useProtocols = defineStore('protocols', () => {
  const conns = reactive<Record<string, Conn>>({})
  const sources: Record<string, EventSource> = {}
  const get_ = (tabId: string) => (conns[tabId] ??= blank())

  function apply(c: Conn, e: ProtoEvent) {
    if (c.events.length && e.seq <= c.events[c.events.length - 1].seq) return          // takror (qayta ulangan oqim)
    c.events.push(e)
    if (c.events.length > MAX_UI_EVENTS) c.events.splice(0, c.events.length - MAX_UI_EVENTS)
    if (e.type === 'message' || e.type === 'event') { const k = e.dir === 'out' ? 'out' : 'in'; c.counts[k]++; c.counts['bytes_' + k] += e.size ?? 0 }
    if (e.type === 'error') { c.counts.errors++; c.error = e.message ?? '' }
    if (e.type === 'connecting') c.status = 'connecting'
    else if (e.type === 'open') { c.status = 'open'; c.error = '' }
    else if (e.type === 'reconnecting') c.status = 'reconnecting'
    else if (e.type === 'closed') c.status = 'closed'
  }

  function attach(tabId: string, sessionId: string, from = 0) {
    sources[tabId]?.close()
    const c = get_(tabId)
    c.sessionId = sessionId; c.lost = false
    const es = eventSource(`/api/protocols/${sessionId}/stream?from=${from}`)
    sources[tabId] = es
    es.onmessage = m => { try { apply(c, JSON.parse(m.data)) } catch { /* buzuq hodisa */ } if (c.status === 'closed') { es.close(); delete sources[tabId] } }
    es.onerror = () => { if (c.status !== 'closed') { es.close(); delete sources[tabId]; c.lost = true; if (c.status !== 'idle') c.error = c.error || "Server bilan oqim uzildi" } }
  }

  /** Sahifa yangilangach: saqlangan sessiyaga qayta ulanadi (server qayta ishga tushgan bo'lsa — "sessiya topilmadi"). */
  async function restore(tab: Tab) {
    const sid = tab.state?.protoSession as string | undefined
    if (!sid || conns[tab.id]?.sessionId === sid) return
    const c = get_(tab.id)
    try {
      const d = await get(`/api/protocols/${sid}/events`)
      c.sessionId = sid; c.url = d.url; c.counts = { ...c.counts, ...d.counts }; c.events = []; c.counts = { in: 0, out: 0, bytes_in: 0, bytes_out: 0, errors: 0 }
      for (const e of d.events) apply(c, e)
      c.status = d.status === 'closed' ? 'closed' : c.status
      if (d.status !== 'closed') attach(tab.id, sid, d.next_seq)
    } catch { delete tab.state!.protoSession; c.sessionId = null }
  }

  async function connect(tab: Tab) {
    const d = tab.draft!, tabs = useTabs()
    const c = get_(tab.id)
    c.error = ''
    if (!d.url.trim()) { c.error = 'URL kiriting'; showToast('URL kiriting!', 'warn'); return }
    await tabs.flush()
    if (c.sessionId && c.status !== 'closed' && c.status !== 'idle') await disconnect(tab)
    try {
      await prepareAuth(d, tab.ref)
      const spec = specFor(d, tab.ref)
      const scripts = scriptsFor(tab.ref, d.scripts, d.name)
      const p = d.proto
      spec.name = d.name
      if (d.protocol === 'sse') { spec.method = p.sseMethod }
      const r = await post('/api/protocols/connect', {
        kind: d.protocol, spec, ref: tab.ref,
        scripts: scripts ? { prerequest: scripts.prerequest, test: [] } : undefined,
        info: { requestName: d.name, requestId: tab.ref?.split(':')[1] ?? '' },
        options: { subprotocols: p.subprotocols.split(',').map(x => x.trim()).filter(Boolean), reconnect: p.reconnect, ping_interval: p.pingInterval || undefined, last_event_id: p.lastEventId },
      })
      if (r.scripts) logScripts({ ...r.scripts, tests: [] }, { tabId: tab.id, ref: tab.ref })
      c.events = []; c.counts = { in: 0, out: 0, bytes_in: 0, bytes_out: 0, errors: 0 }; c.url = r.url; c.status = 'connecting'
      tab.state ??= {}; tab.state.protoSession = r.id
      tabs.persistSoon()
      attach(tab.id, r.id, 0)
      useHistory().add('request', { method: d.protocol === 'ws' ? 'WS' : 'SSE', url: d.url, headers: spec.headers, params: [], protocol: d.protocol, proto: d.proto, name: d.name || undefined, timestamp: Date.now(), status: 'ulandi' }).catch(() => {})
    } catch (e: any) { c.status = 'idle'; c.error = e.message; showToast(e.message, 'error') }
  }

  async function disconnect(tab: Tab) {
    const c = conns[tab.id]
    if (!c?.sessionId) return
    try { await post(`/api/protocols/${c.sessionId}/close`) } catch { /* allaqachon yopilgan */ }
  }

  async function send(tab: Tab, msg: { kind: 'text' | 'json' | 'binary'; data: string; encoding?: 'base64' | 'hex' }) {
    const c = conns[tab.id]
    if (!c?.sessionId) throw new Error('Ulanish yo\'q')
    await post(`/api/protocols/${c.sessionId}/send`, msg)
  }

  const clear = (tabId: string) => { const c = conns[tabId]; if (c) { c.events = []; c.counts = { in: 0, out: 0, bytes_in: 0, bytes_out: 0, errors: 0 } } }

  // tab yopilsa — ulanish ham yopiladi
  const tabs = useTabs()
  watch(() => tabs.tabs.map(t => t.id), ids => {
    for (const id of Object.keys(conns)) {
      if (ids.includes(id)) continue
      const sid = conns[id].sessionId
      sources[id]?.close(); delete sources[id]
      if (sid && conns[id].status !== 'closed') post(`/api/protocols/${sid}/close`).catch(() => {})
      delete conns[id]
    }
  })
  return { conns, get: get_, connect, disconnect, send, restore, attach, clear }
})
