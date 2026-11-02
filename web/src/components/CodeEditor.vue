<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, placeholder as cmPlaceholder } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentLess } from '@codemirror/commands'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { json } from '@codemirror/lang-json'
import { tags as t } from '@lezer/highlight'

const props = defineProps<{ modelValue: string; lang: 'json' | 'raw'; testid?: string; placeholder?: string }>()
const emit = defineEmits<{ 'update:modelValue': [string]; beautify: [] }>()
const host = ref<HTMLElement>()
let view: EditorView | undefined

// Ranglar tema o'zgaruvchilaridan (yorug/qorong'i avtomatik)
const style = HighlightStyle.define([
  { tag: t.propertyName, color: 'var(--j-key)' },
  { tag: [t.string, t.special(t.string)], color: 'var(--j-str)' },
  { tag: [t.number], color: 'var(--j-num)' },
  { tag: [t.bool, t.null], color: 'var(--j-bool)' },
  { tag: [t.keyword, t.atom], color: 'var(--j-bool)' },
])
const theme = EditorView.theme({
  '&': { backgroundColor: 'var(--code)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '9px', height: '100%' },
  '&.cm-focused': { outline: '1px solid var(--accent)' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', fontSize: '12.5px', overflow: 'auto' },
  '.cm-content': { caretColor: 'var(--text)', padding: '6px 0' },
  '.cm-cursor': { borderLeftColor: 'var(--text)' },
})

onMounted(() => {
  view = new EditorView({
    parent: host.value!,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        history(), theme, EditorView.lineWrapping, syntaxHighlighting(style),
        ...(props.lang === 'json' ? [json()] : []),
        ...(props.placeholder ? [cmPlaceholder(props.placeholder)] : []),
        EditorView.contentAttributes.of({ 'data-testid': props.testid ?? 'code-editor' }),
        // Mod-b (Cmd) va Ctrl-b: eski UI ikkalasini qo'llagan
        keymap.of([{ key: 'Mod-b', run: () => (emit('beautify'), true) }, { key: 'Ctrl-b', run: () => (emit('beautify'), true) }, 
          // Tab: kursor o'rniga 2 probel (eski UI bilan bir xil); Shift-Tab: chekinishni kamaytirish
          { key: 'Tab', run: v => (v.dispatch(v.state.replaceSelection('  '), { scrollIntoView: true, userEvent: 'input' }), true) },
          { key: 'Shift-Tab', run: indentLess },
          ...defaultKeymap, ...historyKeymap]),
        EditorView.updateListener.of(u => { if (u.docChanged) emit('update:modelValue', u.state.doc.toString()) }),
      ],
    }),
  })
})
watch(() => props.modelValue, v => {
  if (view && v !== view.state.doc.toString()) view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: v } })
})
onBeforeUnmount(() => view?.destroy())
</script>

<template><div ref="host" class="code-editor" /></template>
