/** `{{` avtoto'ldirish: scope bo'yicha o'zgaruvchilar + dinamik `$…` (Postman). Toza funksiyalar + CodeMirror manbasi. */
import { autocompletion, type Completion, type CompletionContext, type CompletionResult } from '@codemirror/autocomplete'
import { EditorView } from '@codemirror/view'
import { useTabs } from '../stores/tabs'
import { scopedVars } from './scope'

export const DYNAMIC_VARS = ['$guid', '$randomUUID', '$timestamp', '$isoTimestamp', '$randomInt', '$randomBoolean', '$randomAlphaNumeric', '$randomFirstName', '$randomLastName', '$randomEmail']
export interface VarSuggestion { name: string; scope: string; value: string; dynamic: boolean }

/** `{{` dan keyin yozilayotgan nom: matn va kursor bo'yicha `{ from, query }` (from — nom boshlanadigan indeks). */
export function triggerAt(text: string, caret: number): { from: number; query: string } | null {
  const m = /\{\{\s*([\w$.\-]*)$/.exec(text.slice(0, caret))
  return m ? { from: caret - m[1].length, query: m[1] } : null
}

/** Tanlangan nomni qo'yish: allaqachon `}}` bo'lsa qo'shmaydi. Qaytaradi: almashtiriladigan oraliq va matn. */
export function completionEdit(text: string, caret: number, from: number, name: string): { from: number; to: number; insert: string; cursor: number } {
  const after = /^[\w$.\-]*/.exec(text.slice(caret))![0]                 // kursor ichidagi nom qoldig'i ham almashtiriladi
  const to = caret + after.length
  const closed = /^\s*\}\}/.test(text.slice(to))
  const insert = closed ? name : name + '}}'
  return { from, to, insert, cursor: from + insert.length + (closed ? 0 : 0) }
}

export function suggest(ref: string | null, query: string): VarSuggestion[] {
  const q = query.toLowerCase()
  const known = Object.entries(scopedVars(ref)).map(([name, v]) => ({ name, scope: v.scope, value: v.secret ? '••••' : v.value, dynamic: false }))
  const dyn = DYNAMIC_VARS.filter(n => !known.some(k => k.name === n)).map(name => ({ name, scope: 'Dinamik', value: '', dynamic: true }))
  const rank = (s: VarSuggestion) => (s.name.toLowerCase().startsWith(q) ? 0 : s.name.toLowerCase().includes(q) ? 1 : 2)
  return [...known, ...dyn].filter(s => rank(s) < 2).sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
}

/** Joriy (faol) tab ref'i — scope'lar shu bo'yicha yig'iladi. */
export const activeRef = () => useTabs().active?.ref ?? null

export function varCompletionSource(getRef: () => string | null = activeRef) {
  return (ctx: CompletionContext): CompletionResult | null => {
    const t = triggerAt(ctx.state.doc.sliceString(Math.max(0, ctx.pos - 120), ctx.pos), Math.min(120, ctx.pos))
    if (!t) return null
    const base = Math.max(0, ctx.pos - 120)
    const from = base + t.from
    const opts: Completion[] = suggest(getRef(), t.query).map(s => ({
      label: s.name, type: s.dynamic ? 'function' : 'variable', detail: s.scope, info: s.value ? s.value.slice(0, 200) : undefined,
      apply: (view: EditorView, _c: Completion, f: number, to: number) => {
        const doc = view.state.doc.toString()
        const e = completionEdit(doc, to, f, s.name)
        view.dispatch({ changes: { from: e.from, to: e.to, insert: e.insert }, selection: { anchor: e.cursor }, userEvent: 'input.complete' })
      },
    }))
    return opts.length ? { from, options: opts, filter: false } : null
  }
}

export const varCompletion = (getRef?: () => string | null) => autocompletion({ override: [varCompletionSource(getRef)], icons: false, activateOnTyping: true, defaultKeymap: true, aboveCursor: false })

/** Avtoto'ldirish tooltip'i uchun umumiy tema (tokenlar). */
export const completionTheme = EditorView.theme({
  '.cm-tooltip': { backgroundColor: 'var(--panel)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '8px', boxShadow: 'var(--shadow)' },
  '.cm-tooltip-autocomplete ul': { fontFamily: 'var(--font-mono)', fontSize: '12.5px', maxHeight: '240px' },
  '.cm-tooltip-autocomplete ul li': { padding: '4px 10px', display: 'flex', gap: '10px', alignItems: 'baseline' },
  '.cm-tooltip-autocomplete ul li[aria-selected]': { backgroundColor: 'var(--accent-weak)', color: 'var(--text)' },
  '.cm-completionDetail': { marginLeft: 'auto', color: 'var(--muted)', fontStyle: 'normal', fontFamily: 'var(--font-ui)', fontSize: '11px' },
  '.cm-completionInfo': { backgroundColor: 'var(--panel)', color: 'var(--muted)', border: '1px solid var(--border)', borderRadius: '6px', padding: '4px 8px', fontFamily: 'var(--font-mono)' },
})
