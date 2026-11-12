import { reactive, ref } from 'vue'

/** Davom etayotgan ishlar (tab id → matn): brauzer tab sarlavhasida "● Runner 12/18 — API Runner" ko'rinadi. */
export const activity = reactive<Record<string, string>>({})

/** Chap panel (rail bilan boshqariladi) va ⌘K palitrasi holati. */
export type SidePanel = 'collections' | 'environments' | 'history' | 'runner'
export const sidePanel = ref<SidePanel>('collections')
export const cmdkOpen = ref(false)
export const importOpen = ref(false)
export const findOpen = ref(false)
export const mockOf = ref<{ cid: string; name: string } | null>(null)
export const wsExportOpen = ref(false)
export const exportOf = ref<{ cid: string; name: string; requests?: number } | null>(null)
export const trashOpen = ref(false)
export const monitorOpen = ref(false)
export const proxyOpen = ref(false)
export const shortcutsOpen = ref(false)

export const toast = ref<{ msg: string; kind: string; action?: { label: string; run: () => void } } | null>(null)
let tt: ReturnType<typeof setTimeout>
/** `action` — toast ichidagi tugma (masalan «Meros'ga o'tkazish»); bosilsa toast yopiladi. */
export function showToast(msg: string, kind = 'info', ms = 3000, action?: { label: string; run: () => void }) {
  toast.value = { msg, kind, action }
  clearTimeout(tt)
  tt = setTimeout(() => (toast.value = null), ms)
}

export type CloseAnswer = 'save' | 'discard' | 'cancel'
export const closeDialog = ref<{ title: string; resolve: (a: CloseAnswer) => void } | null>(null)
export const askClose = (title: string) => new Promise<CloseAnswer>(res => { closeDialog.value = { title, resolve: a => { closeDialog.value = null; res(a) } } })

export const confirmDialog = ref<{ msg: string; ok: string; checks?: { id: string; label: string }[]; checked?: Record<string, boolean>; resolve: (b: boolean) => void } | null>(null)
export const askConfirm = (msg: string, ok = 'Ha') => new Promise<boolean>(res => { confirmDialog.value = { msg, ok, resolve: b => { confirmDialog.value = null; res(b) } } })
/** Tasdiq + belgilar («Bu host uchun boshqa so'ramaslik» va h.k.). Qaytaradi: {ok, checked: belgilangan id'lar} (bekor qilinsa checked bo'sh). */
export const askConfirmChecks = (msg: string, ok: string, checks: { id: string; label: string }[]) => new Promise<{ ok: boolean; checked: string[] }>(res => {
  const checked: Record<string, boolean> = Object.fromEntries(checks.map(c => [c.id, false]))
  confirmDialog.value = { msg, ok, checks, checked, resolve: b => { const picked = b ? Object.keys(checked).filter(k => checked[k]) : []; confirmDialog.value = null; res({ ok: b, checked: picked }) } }
})

/** Prod'da Runner ishga tushirishdan oldingi dialog (RunGuard): 'get' — faqat GET, 'all' — hammasi, null — bekor. */
export type GuardAnswer = 'get' | 'all' | null
export interface GuardHost { host: string | null; count: number; writes: number; safe: boolean }
export const runGuard = ref<{ envName: string; envKind: string; counts: Record<string, number>; hosts: GuardHost[]; total: number; resolve: (a: GuardAnswer) => void } | null>(null)
export const askRunGuard = (envName: string, envKind: string, counts: Record<string, number>, hosts: GuardHost[]) => new Promise<GuardAnswer>(res => {
  runGuard.value = { envName, envKind, counts, hosts, total: Object.values(counts).reduce((a, b) => a + b, 0), resolve: a => { runGuard.value = null; res(a) } }
})

export const fmtBytes = (n: number) => (n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB')
export const fmtMs = (s: number | null | undefined) => (s == null ? '—' : s < 1 ? Math.round(s * 1000) + ' ms' : s.toFixed(2) + ' s')
