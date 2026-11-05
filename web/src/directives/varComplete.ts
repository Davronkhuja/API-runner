/** `v-var-complete` — oddiy <input>/<textarea> uchun `{{` avtoto'ldirish (CodeMirror maydonlarida `lib/varcomplete.ts` ishlatiladi). */
import { reactive } from 'vue'
import type { Directive } from 'vue'
import { activeRef, completionEdit, suggest, triggerAt, type VarSuggestion } from '../lib/varcomplete'

export const varPopup = reactive({ open: false, items: [] as VarSuggestion[], index: 0, x: 0, y: 0, w: 0, el: null as HTMLInputElement | HTMLTextAreaElement | null })

export function closeVarPopup() { varPopup.open = false; varPopup.el = null; varPopup.items = [] }

function update(el: HTMLInputElement | HTMLTextAreaElement) {
  const caret = el.selectionStart ?? 0
  const t = el.selectionEnd === caret ? triggerAt(el.value, caret) : null
  const items = t ? suggest(activeRef(), t.query).slice(0, 30) : []
  if (!items.length) return closeVarPopup()
  const r = el.getBoundingClientRect()
  Object.assign(varPopup, { open: true, items, index: 0, x: r.left, y: r.bottom + 2, w: Math.max(260, Math.min(r.width, 420)), el })
}

export function acceptVar(s: VarSuggestion) {
  const el = varPopup.el
  if (!el) return
  const caret = el.selectionStart ?? 0, t = triggerAt(el.value, caret)
  if (!t) return closeVarPopup()
  const e = completionEdit(el.value, caret, t.from, s.name)
  el.setRangeText(e.insert, e.from, e.to, 'end')
  el.dispatchEvent(new Event('input', { bubbles: true }))          // v-model va `@input` (dirty) yangilansin
  closeVarPopup()
  el.focus()
}

export const vVarComplete: Directive<HTMLInputElement | HTMLTextAreaElement> = {
  created(el) {
    el.addEventListener('keydown', (e: Event) => {
      const ev = e as KeyboardEvent
      if (!varPopup.open || varPopup.el !== el) return
      const n = varPopup.items.length
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { varPopup.index = (varPopup.index + (ev.key === 'ArrowDown' ? 1 : n - 1)) % n }
      else if (ev.key === 'Enter' || ev.key === 'Tab') { acceptVar(varPopup.items[varPopup.index]) }
      else if (ev.key === 'Escape') { closeVarPopup(); ev.stopPropagation() }
      else return
      ev.preventDefault(); ev.stopImmediatePropagation()
    }, true)
    el.addEventListener('input', () => update(el))
    el.addEventListener('blur', () => { if (varPopup.el === el) setTimeout(() => { if (varPopup.el === el) closeVarPopup() }, 0) })
  },
  beforeUnmount(el) { if (varPopup.el === el) closeVarPopup() },
}
