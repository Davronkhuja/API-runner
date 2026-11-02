/** Tema: `<html>` ga `.th-light`/`.th-dark` (tokens.css) + `data-theme`; tanlov localStorage'da saqlanadi. */
import { ref } from 'vue'

const KEY = 'apiRunnerTheme'
export type Theme = 'light' | 'dark'
export const theme = ref<Theme>('light')

export function applyTheme(t: Theme) {
  theme.value = t
  const el = document.documentElement
  el.classList.remove('th-light', 'th-dark')
  el.classList.add('th-' + t)
  el.dataset.theme = t
}

/** Saqlangan tanlov; bo'lmasa tizim sozlamasi (prefers-color-scheme). main.ts mount'dan OLDIN chaqiradi — miltillash bo'lmaydi. */
export function initTheme() {
  let saved: string | null = null
  try { saved = localStorage.getItem(KEY) } catch { /* ixtiyoriy */ }
  applyTheme(saved === 'dark' || saved === 'light' ? saved : (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))
}

export function toggleTheme() {
  const next: Theme = theme.value === 'dark' ? 'light' : 'dark'
  applyTheme(next)
  try { localStorage.setItem(KEY, next) } catch { /* ixtiyoriy */ }
}
