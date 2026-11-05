<script setup lang="ts">
/** Markdown tavsif paneli: ko'rish (xavfsiz render) va tahrirlash rejimi. So'rov (o'ng panel) va collection/papka (Overview) uchun umumiy. */
import { computed, nextTick, ref } from 'vue'
import { renderMarkdown } from '../lib/markdown'

const props = defineProps<{ modelValue: string; tid: string; placeholder?: string; title?: string; textTid?: string; startEditing?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string]; change: [] }>()
const editing = ref(!!props.startEditing && !(props.modelValue ?? '').trim())
const ta = ref<HTMLTextAreaElement>()
const html = computed(() => renderMarkdown(props.modelValue ?? ''))
async function edit() { editing.value = true; await nextTick(); ta.value?.focus() }
function onInput(e: Event) { emit('update:modelValue', (e.target as HTMLTextAreaElement).value); emit('change') }
</script>

<template>
  <section class="docs" :data-testid="tid" :aria-label="title ?? 'Hujjat'">
    <div class="docs-bar">
      <b>{{ title ?? 'Docs' }}</b><span class="muted docs-hint">Markdown</span><span style="flex:1" />
      <div class="seg-group" role="group" aria-label="Docs rejimi">
        <button class="seg" :class="{ on: !editing }" :aria-pressed="!editing" :data-testid="tid + '-view'" @click="editing = false">Ko'rish</button>
        <button class="seg" :class="{ on: editing }" :aria-pressed="editing" :data-testid="tid + '-edit'" @click="edit">Tahrirlash</button>
      </div>
    </div>
    <textarea v-if="editing" ref="ta" class="docs-ta" :value="modelValue" :placeholder="placeholder ?? '# Sarlavha\n\nTavsif **Markdown** da…'" spellcheck="false" aria-label="Markdown matni" :data-testid="textTid ?? tid + '-text'" @input="onInput" />
    <div v-else-if="modelValue.trim()" class="md" :data-testid="tid + '-html'" v-html="html" />
    <p v-else class="muted docs-empty" :data-testid="tid + '-empty'">Tavsif yo'q. <button class="linkbtn" @click="edit">Yozish</button></p>
  </section>
</template>
