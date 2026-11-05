<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, placeholder as cmPlaceholder } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentLess } from '@codemirror/commands'
import { HighlightStyle, bracketMatching, foldGutter, foldKeymap, syntaxHighlighting } from '@codemirror/language'
import { tagHighlighter } from '@lezer/highlight'
import { curlLang } from '../lib/curlLang'
import { highlightSelectionMatches, search, searchKeymap } from '@codemirror/search'
import { linter, lintGutter, type Diagnostic } from '@codemirror/lint'
import { jsonError } from '../lib/jsonlint'
import { json } from '@codemirror/lang-json'
import { html } from '@codemirror/lang-html'
import { javascript } from '@codemirror/lang-javascript'
import { tags as t } from '@lezer/highlight'

const props = withDefaults(defineProps<{ modelValue: string; lang: 'json' | 'raw' | 'html' | 'javascript' | 'curl'; testid?: string; placeholder?: string; readonly?: boolean; wrap?: boolean; label?: string }>(), { wrap: true })
const emit = defineEmits<{ 'update:modelValue': [string]; beautify: [] }>()
const host = ref<HTMLElement>()
let view: EditorView | undefined

const curlClasses = tagHighlighter([{ tag: t.keyword, class: 'hl-cmd' }, { tag: t.attributeName, class: 'hl-flag' }, { tag: t.string, class: 'hl-str' }, { tag: t.comment, class: 'hl-com' }])
// Ranglar tema o'zgaruvchilaridan (yorug/qorong'i avtomatik)
const style = HighlightStyle.define([
  { tag: t.propertyName, color: 'var(--j-key)' },
  { tag: [t.string, t.special(t.string)], color: 'var(--j-str)' },
  { tag: [t.number], color: 'var(--j-num)' },
  { tag: [t.bool, t.null], color: 'var(--j-bool)' },
  { tag: [t.keyword, t.atom], color: 'var(--j-bool)' },
  { tag: [t.tagName, t.angleBracket], color: 'var(--j-key)' },
  { tag: t.attributeName, color: 'var(--j-num)' },
  { tag: t.attributeValue, color: 'var(--j-str)' },
  { tag: [t.comment, t.docComment], color: 'var(--muted)' },
  { tag: [t.function(t.variableName), t.definition(t.variableName)], color: 'var(--j-key)' },
])
const theme = EditorView.theme({
  '&': { backgroundColor: 'var(--code)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '9px', height: '100%' },
  '&.cm-focused': { outline: '1px solid var(--accent)' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', fontSize: '12.5px', overflow: 'auto' },
  '.cm-content': { caretColor: 'var(--text)', padding: '6px 0', minHeight: '100%' },
  '.cm-cursor': { borderLeftColor: 'var(--text)' },
  '.cm-gutters': { backgroundColor: 'var(--code)', color: 'var(--muted)', border: 'none', borderRight: '1px solid var(--border)', borderRadius: '9px 0 0 9px' },
  '.cm-activeLine': { backgroundColor: 'transparent' }, '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--text)' },
  '.cm-foldGutter span': { cursor: 'pointer' },
  '.cm-matchingBracket': { backgroundColor: 'var(--accent-weak)', outline: '1px solid var(--focus)' },
  '.cm-searchMatch': { backgroundColor: 'var(--mark)', color: 'var(--mark-text)' }, '.cm-searchMatch.cm-searchMatch-selected': { backgroundColor: 'var(--mark-cur)' },
  '.cm-placeholder': { color: 'var(--muted)' },
  '.cm-panels': { backgroundColor: 'var(--panel)', color: 'var(--text)', borderColor: 'var(--border)' },
  '.cm-panel.cm-search input, .cm-panel.cm-search button': { fontSize: '12px' },
  '.cm-lintRange-error': { backgroundImage: 'none', textDecoration: 'underline wavy var(--err)', textUnderlineOffset: '3px' },
  '.cm-diagnostic-error': { borderLeft: '3px solid var(--err)' },
  '.cm-tooltip': { backgroundColor: 'var(--panel)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '8px', boxShadow: 'var(--shadow)' },
})

/** JSON body xatosini qizil chiziq bilan belgilaydi ({{var}} placeholder'lari xato emas). */
const jsonLinter = linter((v): Diagnostic[] => {
  const text = v.state.doc.toString(), err = jsonError(text)
  if (!err) return []
  const from = Math.min(err.pos, text.length), to = Math.min(from + 1, text.length)
  return [{ from: Math.max(0, to > from ? from : from - 1), to: Math.max(to, from), severity: 'error', message: `JSON xatosi (${err.line}-qator, ${err.col}-ustun): ${err.message}` }]
}, { delay: 300 })

onMounted(() => {
  view = new EditorView({
    parent: host.value!,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        history(), theme, ...(props.wrap ? [EditorView.lineWrapping] : []), syntaxHighlighting(style),
        lineNumbers(), foldGutter(), bracketMatching(), highlightActiveLine(), highlightSelectionMatches(), search({ top: true }),
        ...(props.lang === 'json' && !props.readonly ? [jsonLinter, lintGutter()] : []),
        ...(props.readonly ? [EditorState.readOnly.of(true)] : []),
        ...(props.lang === 'json' ? [json()] : props.lang === 'html' ? [html()] : props.lang === 'javascript' ? [javascript()] : props.lang === 'curl' ? [curlLang, syntaxHighlighting(curlClasses)] : []),
        ...(props.placeholder ? [cmPlaceholder(props.placeholder)] : []),
        EditorView.contentAttributes.of({ 'data-testid': props.testid ?? 'code-editor', 'aria-label': props.label ?? 'Kod muharriri', tabindex: '0' }),
        // Mod-b (Cmd) va Ctrl-b: eski UI ikkalasini qo'llagan
        keymap.of([{ key: 'Mod-b', run: () => (emit('beautify'), true) }, { key: 'Ctrl-b', run: () => (emit('beautify'), true) }, 
          // Tab: kursor o'rniga 2 probel (eski UI bilan bir xil); Shift-Tab: chekinishni kamaytirish
          { key: 'Tab', run: v => (v.dispatch(v.state.replaceSelection('  '), { scrollIntoView: true, userEvent: 'input' }), true) },
          { key: 'Shift-Tab', run: indentLess },
          ...searchKeymap, ...foldKeymap, ...defaultKeymap, ...historyKeymap]),
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
