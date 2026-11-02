import { ref } from 'vue'

export const toast = ref<{ msg: string; kind: string } | null>(null)
let tt: ReturnType<typeof setTimeout>
export function showToast(msg: string, kind = 'info', ms = 3000) {
  toast.value = { msg, kind }
  clearTimeout(tt)
  tt = setTimeout(() => (toast.value = null), ms)
}

export type CloseAnswer = 'save' | 'discard' | 'cancel'
export const closeDialog = ref<{ title: string; resolve: (a: CloseAnswer) => void } | null>(null)
export const askClose = (title: string) => new Promise<CloseAnswer>(res => { closeDialog.value = { title, resolve: a => { closeDialog.value = null; res(a) } } })

export const confirmDialog = ref<{ msg: string; ok: string; resolve: (b: boolean) => void } | null>(null)
export const askConfirm = (msg: string, ok = 'Ha') => new Promise<boolean>(res => { confirmDialog.value = { msg, ok, resolve: b => { confirmDialog.value = null; res(b) } } })

export const fmtBytes = (n: number) => (n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB')
export const fmtMs = (s: number | null | undefined) => (s == null ? '—' : s < 1 ? Math.round(s * 1000) + ' ms' : s.toFixed(2) + ' s')
