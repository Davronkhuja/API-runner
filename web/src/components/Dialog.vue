<script setup lang="ts">
/**
 * YAGONA dialog komponenti: sarlavha va pastki tugmalar doim ko'rinadi, faqat tana scroll bo'ladi (max-height: viewport − 64px).
 * Esc va tashqariga bosish yopadi; fokus dialog ichida aylanadi (tuzoq); ochilganda birinchi elementga, yopilganda trigger'ga qaytadi.
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ title?: string; testid?: string; width?: string; closable?: boolean; top?: boolean; bodyClass?: string }>(), { width: '520px', closable: true })
const emit = defineEmits<{ close: [] }>()
const box = ref<HTMLElement>()
let prev: HTMLElement | null = null
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"]),[contenteditable=true]'
const focusables = () => [...(box.value?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])].filter(e => e.offsetParent !== null)

onMounted(async () => {
  prev = document.activeElement as HTMLElement | null
  await nextTick()
  const el = box.value?.querySelector<HTMLElement>('[data-autofocus]') ?? focusables().find(e => !e.closest('.dlg-head')) ?? box.value
  el?.focus()
})
onBeforeUnmount(() => { if (prev && document.contains(prev)) prev.focus() })

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.closable) { e.stopPropagation(); e.preventDefault(); emit('close'); return }
  if (e.key !== 'Tab') return
  const f = focusables()
  if (!f.length) { e.preventDefault(); return }
  const first = f[0], last = f[f.length - 1], active = document.activeElement
  if (e.shiftKey && (active === first || active === box.value)) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus() }
}
const titleId = 'dlg-' + Math.random().toString(36).slice(2, 8)
</script>

<template>
  <div class="overlay" :class="{ 'overlay-top': top }" @mousedown.self="closable && emit('close')" @keydown="onKey">
    <div ref="box" class="dialog dlg" role="dialog" aria-modal="true" :aria-labelledby="title ? titleId : undefined" tabindex="-1" :data-testid="testid" :style="{ '--dlg-w': width }">
      <header v-if="title || $slots.actions" class="dlg-head">
        <h2 :id="titleId" class="dlg-title">{{ title }}</h2>
        <slot name="actions" />
        <button v-if="closable" class="ib dlg-x" aria-label="Yopish" data-testid="dlg-close" @click="emit('close')">×</button>
      </header>
      <div class="dlg-body" :class="bodyClass"><slot /></div>
      <footer v-if="$slots.footer" class="dlg-foot"><slot name="footer" /></footer>
    </div>
  </div>
</template>
