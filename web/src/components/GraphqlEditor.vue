<script setup lang="ts">
/** GraphQL so'rov muharriri: sintaksis, sxemaga asoslangan avtoto'ldirish va validatsiya (cm6-graphql). */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, placeholder as cmPlaceholder } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { bracketMatching } from '@codemirror/language'
import { autocompletion, closeBrackets, type CompletionContext } from '@codemirror/autocomplete'
import { linter, type Diagnostic } from '@codemirror/lint'
import { graphqlLanguageSupport } from 'cm6-graphql'
import { getAutocompleteSuggestions } from 'graphql-language-service'
import { GraphQLError, parse, validate, type GraphQLSchema } from 'graphql'
import { completionTheme } from '../lib/varcomplete'

const props = defineProps<{ modelValue: string; schema: GraphQLSchema | null; testid?: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const host = ref<HTMLElement>()
let view: EditorView | undefined
let schema: GraphQLSchema | null = props.schema
const offsetOf = (doc: string, line: number, col: number) => { const lines = doc.split('\n'); let o = 0; for (let i = 0; i < line - 1 && i < lines.length; i++) o += lines[i].length + 1; return Math.min(doc.length, o + col - 1) }

function complete(ctx: CompletionContext) {
  if (!schema) return null
  const word = ctx.matchBefore(/[\w$@.]*/)
  if (!word || (word.from === word.to && !ctx.explicit)) return null
  const line = ctx.state.doc.lineAt(ctx.pos)
  const items = getAutocompleteSuggestions(schema, ctx.state.doc.toString(), { line: line.number - 1, character: ctx.pos - line.from, setLine() {}, setCharacter() {}, lessThanOrEqualTo: () => true } as any)
  if (!items.length) return null
  return { from: word.from, options: items.map(i => ({ label: i.label, detail: String(i.type ?? i.detail ?? ''), info: i.documentation || undefined, type: i.kind === 5 ? 'property' : 'variable' })), validFor: /^[\w$@.]*$/ }
}

const gqlLint = linter((v): Diagnostic[] => {
  const text = v.state.doc.toString()
  if (!text.trim()) return []
  const toDiag = (e: GraphQLError): Diagnostic => { const l = e.locations?.[0]; const from = l ? offsetOf(text, l.line, l.column) : 0; return { from, to: Math.min(text.length, from + 1 + (/^\w/.test(text[from] ?? '') ? (/^\w+/.exec(text.slice(from))?.[0].length ?? 1) - 1 : 0)), severity: 'error', message: e.message } }
  try {
    const doc = parse(text)
    return schema ? validate(schema, doc).map(toDiag) : []
  } catch (e: any) { return e instanceof GraphQLError ? [toDiag(e)] : [] }
}, { delay: 250 })
const theme = EditorView.theme({
  '&': { backgroundColor: 'var(--code)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '9px', height: '100%' },
  '&.cm-focused': { outline: '1px solid var(--accent)' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', fontSize: '12.5px', overflow: 'auto' },
  '.cm-gutters': { backgroundColor: 'var(--code)', color: 'var(--muted)', border: 'none', borderRight: '1px solid var(--border)' },
  '.cm-content': { caretColor: 'var(--text)' },
  '.cm-placeholder': { color: 'var(--muted)' },
  '.cm-lintRange-error': { textDecoration: 'underline wavy var(--err)', backgroundImage: 'none' },
  '.cm-diagnostic-error': { borderLeft: '3px solid var(--err)' },
})
onMounted(() => {
  view = new EditorView({
    parent: host.value!,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [history(), theme, completionTheme, lineNumbers(), bracketMatching(), closeBrackets(), cmPlaceholder('query { users { id name } }'), graphqlLanguageSupport(), autocompletion({ override: [complete], icons: false }), gqlLint,
        EditorView.contentAttributes.of({ 'data-testid': props.testid ?? 'gql-query', 'aria-label': 'GraphQL query', tabindex: '0' }),
        keymap.of([...defaultKeymap, ...historyKeymap]), EditorView.updateListener.of(u => { if (u.docChanged) emit('update:modelValue', u.state.doc.toString()) })],
    }),
  })
})
watch(() => props.schema, s => { schema = s })
watch(() => props.modelValue, v => { if (view && v !== view.state.doc.toString()) view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: v } }) })
onBeforeUnmount(() => view?.destroy())
</script>

<template><div ref="host" class="code-editor gql-editor" /></template>
