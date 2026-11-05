<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Annotation, EditorState, StateEffect, type Range } from '@codemirror/state'
import { Decoration, EditorView, ViewPlugin, keymap, placeholder as cmPlaceholder, type DecorationSet, type ViewUpdate } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { completionTheme, varCompletion } from '../lib/varcomplete'

export interface VarInfo { ok: boolean; title: string }
const props = defineProps<{ modelValue: string; placeholder?: string; vars: (name: string) => VarInfo }>()
const emit = defineEmits<{
  'update:modelValue': [string]; input: []; enter: []; focus: []; blur: []
  paste: [text: string, prevent: () => void]; tip: [info: { text: string; x: number; y: number } | null]
}>()
const host = ref<HTMLElement>()
let view: EditorView | undefined
const external = Annotation.define<boolean>()
const refresh = StateEffect.define<null>()

// {{var}} chiplari va so'rov qismi (?…) — hujjatdan hisoblanadigan dekoratsiyalar
function build(v: EditorView): DecorationSet {
  const doc = v.state.doc.toString(), out: Range<Decoration>[] = []
  const qi = doc.indexOf('?')
  if (qi >= 0) out.push(Decoration.mark({ class: 'cm-url-q' }).range(qi, doc.length))
  for (const m of doc.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)) {
    const name = m[1], info = props.vars(name)
    out.push(Decoration.mark({
      class: 'chip ' + (info.ok ? 'var-ok' : 'var-undef undef'),
      attributes: { 'data-testid': 'var-chip', 'data-tip': info.title, 'aria-label': info.title },
    }).range(m.index!, m.index! + m[0].length))
  }
  return Decoration.set(out, true)
}
const chips = ViewPlugin.fromClass(class {
  decorations: DecorationSet
  constructor(v: EditorView) { this.decorations = build(v) }
  update(u: ViewUpdate) { if (u.docChanged || u.transactions.some(t => t.effects.some(e => e.is(refresh)))) this.decorations = build(u.view) }
}, { decorations: p => p.decorations })

const theme = EditorView.theme({
  '&': { flex: '1', minWidth: '0', height: '100%', backgroundColor: 'transparent', color: 'var(--text)' },
  '&.cm-focused': { outline: 'none' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: '36px', overflowX: 'auto', overflowY: 'hidden', scrollbarWidth: 'none' },
  '.cm-scroller::-webkit-scrollbar': { display: 'none' },
  '.cm-content': { caretColor: 'var(--text)', padding: '0 12px', whiteSpace: 'pre', minHeight: '36px' },
  '.cm-line': { padding: 0 },
  '.cm-cursor': { borderLeftColor: 'var(--text)' },
  '.cm-content ::selection': { backgroundColor: 'var(--sel)' },
  '.cm-placeholder': { color: 'var(--muted)' },
})

const oneLine = (s: string) => s.replace(/[\r\n]+/g, '')
const filter = EditorState.transactionFilter.of(tr => {
  if (!tr.docChanged || tr.newDoc.lines === 1) return tr
  return { changes: { from: 0, to: tr.startState.doc.length, insert: oneLine(tr.newDoc.toString()) }, selection: { anchor: Math.min(tr.newSelection.main.head, oneLine(tr.newDoc.toString()).length) }, annotations: tr.annotation(external) ? external.of(true) : undefined }
})

function tipFrom(e: MouseEvent) {
  const el = (e.target as HTMLElement).closest?.('[data-testid=var-chip]') as HTMLElement | null
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { text: el.dataset.tip ?? '', x: Math.max(8, r.left), y: r.bottom + 6 }
}

onMounted(() => {
  view = new EditorView({
    parent: host.value!,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        history(), theme, filter, chips, varCompletion(), completionTheme,
        ...(props.placeholder ? [cmPlaceholder(props.placeholder)] : []),
        EditorView.contentAttributes.of({ 'data-testid': 'url', 'aria-label': "So'rov URL", spellcheck: 'false', autocapitalize: 'off', autocorrect: 'off' }),
        keymap.of([
          { key: 'Enter', run: () => (emit('enter'), true) },
          ...historyKeymap, ...defaultKeymap.filter(k => k.key !== 'Enter' && k.key !== 'Mod-Enter' && k.key !== 'Shift-Enter'),
        ]),
        EditorView.domEventHandlers({
          paste(e) {
            const text = e.clipboardData?.getData('text') ?? ''
            let prevented = false
            emit('paste', text, () => { prevented = true })
            if (prevented) { e.preventDefault(); return true }
            if (/[\r\n]/.test(text)) { e.preventDefault(); view!.dispatch(view!.state.replaceSelection(oneLine(text)), { userEvent: 'input.paste', scrollIntoView: true }); return true }
            return false
          },
          mouseover(e) { const t = tipFrom(e); if (t) emit('tip', t) },
          mouseout(e) { if ((e.target as HTMLElement).closest?.('[data-testid=var-chip]')) emit('tip', null) },
          focus() { emit('focus') },
          blur() { emit('blur'); emit('tip', null) },
        }),
        EditorView.updateListener.of(u => {
          if (!u.docChanged || u.transactions.every(t => t.annotation(external))) return
          emit('update:modelValue', u.state.doc.toString()); emit('input')
        }),
      ],
    }),
  })
})
watch(() => props.modelValue, v => {
  if (view && v !== view.state.doc.toString()) view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: v }, annotations: [external.of(true)] })
})
// o'zgaruvchilar ta'rifi o'zgarganda chiplarni qayta hisoblash
function rebuild() { view?.dispatch({ effects: refresh.of(null) }) }
defineExpose({ focus: () => view?.focus(), rebuild })
onBeforeUnmount(() => view?.destroy())
</script>

<template><div ref="host" class="url-editor" /></template>
