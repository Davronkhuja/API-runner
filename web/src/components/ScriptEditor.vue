<script setup lang="ts">
/** JavaScript muharriri (CodeMirror 6): pm.* avtoto'ldirish, qator raqamlari, xato qatorlarini belgilash va qatorga o'tish. */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { EditorState, StateEffect, StateField, type Extension } from '@codemirror/state'
import { Decoration, EditorView, drawSelection, highlightActiveLine, keymap, lineNumbers, placeholder as cmPlaceholder, type DecorationSet } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap, type CompletionContext } from '@codemirror/autocomplete'
import { HighlightStyle, bracketMatching, syntaxHighlighting } from '@codemirror/language'
import { javascript } from '@codemirror/lang-javascript'
import { tags as t } from '@lezer/highlight'
import { PM_API } from '../lib/pmApi'

export interface LineError { line: number | null; message: string }
const props = defineProps<{ modelValue: string; testid: string; errors?: LineError[]; goto?: { line: number; nonce: number } | null; placeholder?: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const host = ref<HTMLElement>()
let view: EditorView | undefined

const style = HighlightStyle.define([
  { tag: t.comment, color: 'var(--muted)', fontStyle: 'italic' },
  { tag: [t.keyword, t.controlKeyword, t.definitionKeyword, t.moduleKeyword, t.operatorKeyword], color: 'var(--accent-text)' },
  { tag: [t.string, t.special(t.string), t.regexp], color: 'var(--j-str)' },
  { tag: [t.number, t.bool, t.null, t.atom], color: 'var(--j-num)' },
  { tag: [t.propertyName], color: 'var(--j-key)' },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: 'var(--m-put)' },
])
const theme = EditorView.theme({
  '&': { backgroundColor: 'var(--code)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '9px', height: '100%' },
  '&.cm-focused': { outline: '2px solid var(--focus)', outlineOffset: '0' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', fontSize: '12.5px', lineHeight: '20px', overflow: 'auto' },
  '.cm-content': { caretColor: 'var(--text)', padding: '6px 0' },
  '.cm-cursor': { borderLeftColor: 'var(--text)' },
  '.cm-gutters': { backgroundColor: 'transparent', color: 'var(--muted)', border: 'none' },
  '.cm-activeLine': { backgroundColor: 'transparent' }, '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--text)' },
  '.cm-err-line': { backgroundColor: 'var(--err-bg)', boxShadow: 'inset 3px 0 0 var(--err)' },
  '.cm-tooltip': { backgroundColor: 'var(--panel)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '8px', boxShadow: 'var(--shadow)', fontFamily: 'var(--font-mono)' },
  '.cm-tooltip-autocomplete ul li[aria-selected]': { backgroundColor: 'var(--accent-weak)', color: 'var(--text)' },
  '.cm-completionDetail': { color: 'var(--muted)', fontStyle: 'normal', marginLeft: '10px' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: 'var(--accent-weak)' },
})

const setErr = StateEffect.define<LineError[]>()
const errField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(deco, tr) {
    deco = deco.map(tr.changes)
    for (const e of tr.effects) if (e.is(setErr)) {
      const ranges = e.value.filter(x => x.line && x.line >= 1 && x.line <= tr.state.doc.lines).map(x => Decoration.line({ class: 'cm-err-line', attributes: { title: x.message } }).range(tr.state.doc.line(x.line!).from))
      deco = Decoration.set(ranges, true)
    }
    return deco
  },
  provide: f => EditorView.decorations.from(f),
})

function complete(ctx: CompletionContext) {
  const w = ctx.matchBefore(/[\w$.]*/)
  if (!w || (w.from === w.to && !ctx.explicit)) return null
  if (w.text.length < 2 && !ctx.explicit) return null
  return { from: w.from, options: PM_API.map(a => ({ label: a.label, type: a.type, detail: a.detail })), validFor: /^[\w$.]*$/ }
}

const extensions = (): Extension[] => [
  history(), drawSelection(), lineNumbers(), highlightActiveLine(), bracketMatching(), closeBrackets(), theme, syntaxHighlighting(style), javascript(), errField,
  autocompletion({ override: [complete], maxRenderedOptions: 60, activateOnTyping: true }),
  EditorView.contentAttributes.of({ 'data-testid': props.testid, 'aria-label': 'Skript muharriri', role: 'textbox', 'aria-multiline': 'true' }),
  ...(props.placeholder ? [cmPlaceholder(props.placeholder)] : []),
  keymap.of([indentWithTab, ...closeBracketsKeymap, ...completionKeymap, ...defaultKeymap, ...historyKeymap]),
  EditorView.updateListener.of(u => { if (u.docChanged) emit('update:modelValue', u.state.doc.toString()) }),
]
onMounted(() => {
  view = new EditorView({ parent: host.value!, state: EditorState.create({ doc: props.modelValue, extensions: extensions() }) })
  view.dispatch({ effects: setErr.of(props.errors ?? []) })
})
watch(() => props.modelValue, v => { if (view && v !== view.state.doc.toString()) view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: v } }) })
watch(() => props.errors, e => view?.dispatch({ effects: setErr.of(e ?? []) }), { deep: true })
watch(() => props.goto, g => {
  if (!view || !g) return
  const line = view.state.doc.line(Math.max(1, Math.min(g.line, view.state.doc.lines)))
  view.dispatch({ selection: { anchor: line.from }, effects: EditorView.scrollIntoView(line.from, { y: 'center' }) })
  view.focus()
}, { deep: true, immediate: false })
onBeforeUnmount(() => view?.destroy())

/** Kursor o'rniga matn qo'yish (snippet'lar). */
function insert(text: string) {
  if (!view) return
  const { from, to } = view.state.selection.main
  view.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from + text.length }, scrollIntoView: true })
  view.focus()
}
defineExpose({ insert, focus: () => view?.focus() })
</script>

<template><div ref="host" class="script-editor" /></template>
