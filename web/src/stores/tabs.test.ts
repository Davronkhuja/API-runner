import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useTabs } from './tabs'

const mem = () => { const saved: any[] = []; return { saved, p: { load: async () => saved[saved.length - 1] ?? {}, save: async (s: any) => { saved.push(JSON.parse(JSON.stringify(s))) } } } }
let store: ReturnType<typeof useTabs>
let m: ReturnType<typeof mem>
beforeEach(() => { (globalThis as any).window = globalThis; setActivePinia(createPinia()); store = useTabs(); m = mem(); store.setPersistence(m.p) })

describe('preview/permanent', () => {
  it('single open creates preview tab, next open replaces it', () => {
    store.open('request', 'c:a', 'A'); store.open('request', 'c:b', 'B')
    expect(store.tabs).toHaveLength(1); expect(store.tabs[0].title).toBe('B'); expect(store.tabs[0].preview).toBe(true)
  })
  it('permanent open keeps tab, preview goes next to it', () => {
    store.open('request', 'c:a', 'A', { permanent: true }); store.open('request', 'c:b', 'B')
    expect(store.tabs.map(t => t.title)).toEqual(['A', 'B'])
  })
  it('editing makes preview permanent and dirty; dirty preview is not replaced', () => {
    const t = store.open('request', 'c:a', 'A'); store.touch(t.id)
    expect(store.tabs[0]).toMatchObject({ preview: false, dirty: true })
    store.open('request', 'c:b', 'B'); expect(store.tabs).toHaveLength(2)
  })
  it('same request opened twice activates existing tab', () => {
    const a = store.open('request', 'c:a', 'A', { permanent: true }); store.open('request', 'c:b', 'B', { permanent: true })
    store.open('request', 'c:a', 'A'); expect(store.tabs).toHaveLength(2); expect(store.activeId).toBe(a.id)
  })
  it('double click converts preview to permanent', () => {
    store.open('request', 'c:a', 'A'); store.open('request', 'c:a', 'A', { permanent: true })
    expect(store.tabs[0].preview).toBe(false)
  })
})

describe('closing', () => {
  const mk = () => ['a', 'b', 'c', 'd'].map(n => store.open('request', 'c:' + n, n.toUpperCase(), { permanent: true }))
  it('close picks neighbour as active', async () => { const [a, b, c] = mk(); store.activate(b.id); await store.close(b.id); expect(store.activeId).toBe(c.id); expect(a).toBeTruthy() })
  it('closeOthers / closeRight / closeAll', async () => {
    let [a, b, c] = mk(); await store.closeRight(b.id); expect(store.tabs.map(t => t.title)).toEqual(['A', 'B'])
    await store.closeOthers(a.id); expect(store.tabs.map(t => t.title)).toEqual(['A'])
    await store.closeAll(); expect(store.tabs).toHaveLength(0); expect(store.activeId).toBeNull(); void c
  })
  it('dirty close: cancel keeps, discard closes, save calls save', async () => {
    const [a] = mk(); store.touch(a.id)
    expect(await store.close(a.id, async () => 'cancel')).toBe(false); expect(store.tabs).toHaveLength(4)
    let saved = false
    expect(await store.close(a.id, async () => 'save', async () => { saved = true })).toBe(true); expect(saved).toBe(true)
    const b = store.tabs[0]; store.touch(b.id)
    expect(await store.close(b.id, async () => 'discard')).toBe(true); expect(store.tabs).toHaveLength(2)
  })
  it('closeOthers stops at cancel', async () => {
    const [a, b] = mk(); store.touch(b.id)
    expect(await store.closeOthers(a.id, async () => 'cancel')).toBe(false); expect(store.tabs.some(t => t.id === b.id)).toBe(true)
  })
  it('reopen closed (LIFO) and no duplicate', async () => {
    const [a, b] = mk(); await store.close(a.id); await store.close(b.id)
    expect(store.reopenClosed()!.title).toBe('B'); expect(store.reopenClosed()!.title).toBe('A'); expect(store.reopenClosed()).toBeNull()
  })
})

describe('navigation / reorder / duplicate', () => {
  it('next/prev wrap around', () => {
    const [a, b, c] = ['a', 'b', 'c'].map(n => store.open('request', n, n, { permanent: true }))
    store.next(1); expect(store.activeId).toBe(a.id); store.next(-1); expect(store.activeId).toBe(c.id); expect(b).toBeTruthy()
  })
  it('reorder moves tab', () => {
    const [a, , c] = ['a', 'b', 'c'].map(n => store.open('request', n, n, { permanent: true }))
    store.reorder(c.id, 0); expect(store.tabs.map(t => t.title)).toEqual(['c', 'a', 'b']); store.reorder(a.id, 99); expect(store.tabs.at(-1)!.title).toBe('a')
  })
  it('duplicate inserts right after, deep-copies draft, dirty', () => {
    const t = store.openNew(); t.draft!.url = 'http://x'; const d = store.duplicate(t.id)!
    d.draft!.url = 'http://y'; expect(t.draft!.url).toBe('http://x'); expect(store.tabs[1].id).toBe(d.id); expect(d.dirty).toBe(true)
  })
  it('independent state per tab', () => {
    const a = store.openNew(), b = store.openNew()
    a.draft!.url = 'A'; a.scroll.resp = 50; a.response = { status: 200 }
    store.activate(b.id); store.activate(a.id)
    expect(store.active!.draft!.url).toBe('A'); expect(store.active!.scroll.resp).toBe(50); expect(b.draft!.url).toBe('')
  })
  it('environment/collection/runner kinds open as tabs', () => {
    store.open('environment', 'e1', 'Dev', { permanent: true }); store.open('collection', 'c1', 'Col', { permanent: true }); store.open('runner', 'c1', 'Runner', { permanent: true })
    expect(store.tabs.map(t => t.kind)).toEqual(['environment', 'collection', 'runner'])
  })
})

describe('persistence', () => {
  it('persists and restores tabs + active (server restart)', async () => {
    const a = store.open('request', 'c:a', 'A', { permanent: true }); store.open('request', 'c:b', 'B', { permanent: true }); store.activate(a.id)
    await store.persistNow()
    setActivePinia(createPinia()); const fresh = useTabs(); fresh.setPersistence(m.p); await fresh.restore()
    expect(fresh.tabs.map(t => t.title)).toEqual(['A', 'B']); expect(fresh.activeId).toBe(a.id)
  })
  it('restore with empty state is harmless', async () => { await store.restore(); expect(store.tabs).toEqual([]) })
  it('retitle and dropRef follow tree changes', () => {
    store.open('request', 'c:a', 'A', { permanent: true }); store.retitle('c:a', 'Z'); expect(store.tabs[0].title).toBe('Z')
    store.dropRef('c:a'); expect(store.tabs).toHaveLength(0)
  })
})

describe('flush (ma\'lumot yo\'qolmasligi)', () => {
  it('edits are debounced but flush() sends immediately; nothing pending -> no request', async () => {
    const a = store.openNew(); await Promise.resolve()
    const base = m.saved.length
    a.draft!.url = 'http://changed'; store.touch(a.id)
    expect(m.saved.length).toBe(base)                       // debounce: hali yozilmadi
    await store.flush()
    expect(m.saved.length).toBe(base + 1)
    expect(m.saved.at(-1).tabs.tabs[0].draft.url).toBe('http://changed')
    await store.flush(); expect(m.saved.length).toBe(base + 1)   // kutilayotgani yo'q
  })
  it('structural changes (activate/open/close) persist immediately', async () => {
    const a = store.open('request', 'c:a', 'A', { permanent: true }); const b = store.open('request', 'c:b', 'B', { permanent: true })
    await Promise.resolve(); const n = m.saved.length
    store.activate(a.id); expect(m.saved.length).toBe(n + 1)
    await store.close(b.id); expect(m.saved.length).toBe(n + 2)
  })
  it('flushOnUnload uses the keepalive path with the pending edit', () => {
    const unload: any[] = []
    store.setPersistence({ ...m.p, saveUnload: s => unload.push(JSON.parse(JSON.stringify(s))) })
    const a = store.openNew(); a.draft!.url = 'http://last-keystroke'; store.touch(a.id)
    store.flushOnUnload()
    expect(unload).toHaveLength(1); expect(unload[0].tabs.tabs[0].draft.url).toBe('http://last-keystroke')
    store.flushOnUnload(); expect(unload).toHaveLength(1)         // ikki marta yuborilmaydi
  })
})
