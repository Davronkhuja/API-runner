<script setup lang="ts">
/** Console paneli (status bardan ochiladi): so'rov/javob loglari, skriptdagi console.* va skript xatolari. */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { drag } from '../lib/resize'
import { clampConsole, CONSOLE_DEFAULT, clear, consoleHeight, saveConsoleHeight, consoleOpen, entries, filters, visible, type Entry } from '../lib/console'
import { openScriptAt } from '../lib/scripts'
import { useTabs } from '../stores/tabs'
import Icon from './Icon.vue'

const tabs = useTabs()
const q = ref('')
const box = ref<HTMLElement>()
const shown = computed(() => visible.value.filter(e => !q.value || (e.text + (e.origin?.name ?? '')).toLowerCase().includes(q.value.toLowerCase())))
const FILTERS: [string, string][] = [['log', 'Log'], ['info', 'Info'], ['warn', 'Ogohlantirish'], ['error', 'Xato'], ['request', "So'rov/javob"]]
const time = (ts: number) => new Date(ts).toLocaleTimeString([], { hour12: false })
const icon = (e: Entry) => ({ request: '→', response: '←', 'script-error': '✗', error: '✗', warn: '⚠', info: 'ℹ', debug: '·', log: '›' } as Record<string, string>)[e.level]
const originLabel = (e: Entry) => (e.origin?.scope ? `${({ collection: 'Collection', folder: 'Papka', request: "So'rov" } as Record<string, string>)[e.origin.scope]}${e.origin.name ? ' «' + e.origin.name + '»' : ''} · ${e.origin.kind === 'prerequest' ? 'Pre-request' : e.origin.kind === 'test' ? 'Tests' : ''}` : '')
function jump(e: Entry) {
  if (!e.line || !e.origin) return
  const tab = tabs.tabs.find(t => t.id === e.tabId) ?? tabs.active
  openScriptAt(tab ?? null, { line: e.line, origin: e.origin as any })
}
watch(() => entries.value.length, async () => {
  const el = box.value; if (!el) return
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  await nextTick(); if (atBottom) el.scrollTop = el.scrollHeight
})
function startResize(e: PointerEvent) { const h0 = consoleHeight.value; drag(e, 'y', d => { consoleHeight.value = clampConsole(h0 - d) }, saveConsoleHeight) }
const nudgeConsole = (d: number) => { consoleHeight.value = clampConsole(consoleHeight.value + d); saveConsoleHeight() }
const resetConsole = () => { consoleHeight.value = clampConsole(CONSOLE_DEFAULT); saveConsoleHeight() }
const onWinResize = () => { consoleHeight.value = clampConsole(consoleHeight.value) }
onMounted(() => { onWinResize(); window.addEventListener('resize', onWinResize) })
onBeforeUnmount(() => window.removeEventListener('resize', onWinResize))
</script>

<template>
  <section v-if="consoleOpen" class="console" :style="{ height: consoleHeight + 'px' }" aria-label="Console" data-testid="console">
    <div class="v-resizer" role="separator" aria-orientation="horizontal" aria-label="Console balandligi" tabindex="0" data-testid="console-resizer" :aria-valuenow="consoleHeight" @pointerdown="startResize" @dblclick="resetConsole" @keydown.up.prevent="nudgeConsole(24)" @keydown.down.prevent="nudgeConsole(-24)" />
    <div class="console-bar">
      <b>Console</b><span class="muted" data-testid="console-count">{{ shown.length }} / {{ entries.length }}</span>
      <div class="seg-group" role="group" aria-label="Filtr">
        <button v-for="f in FILTERS" :key="f[0]" class="seg" :class="{ on: filters[f[0]] }" :aria-pressed="filters[f[0]]" :data-filter="f[0]" @click="filters[f[0]] = !filters[f[0]]; if (f[0] === 'request') filters.response = filters.request">{{ f[1] }}</button>
      </div>
      <input v-model="q" class="sm" placeholder="Qidirish…" aria-label="Console'da qidirish" data-testid="console-search" style="width:160px;height:26px">
      <span style="flex:1" />
      <button class="sm" data-testid="console-clear" @click="clear">Tozalash</button>
      <button class="ib" aria-label="Console'ni yopish" data-testid="console-close" @click="consoleOpen = false"><Icon name="x" :size="15" /></button>
    </div>
    <div ref="box" class="console-body" role="log" aria-live="off" tabindex="0" data-testid="console-body">
      <div v-for="e in shown" :key="e.id" class="cl" :class="'cl-' + e.level" data-testid="console-entry" :data-level="e.level">
        <span class="ct">{{ time(e.ts) }}</span><span class="ci2" aria-hidden="true">{{ icon(e) }}</span>
        <span class="cx"><span data-testid="console-text">{{ e.text }}</span>
          <span v-if="e.origin?.scope" class="muted co" data-testid="console-origin">{{ originLabel(e) }}</span>
          <button v-if="e.line && e.origin?.scope" class="ghost sm" style="height:20px" data-testid="console-goto" @click="jump(e)">qator {{ e.line }} ↗</button>
          <details v-if="e.stack && e.level === 'script-error'"><summary class="muted" style="cursor:pointer;font-size:var(--fs-sm)">stack trace</summary><pre>{{ e.stack }}</pre></details></span>
      </div>
      <div v-if="!shown.length" class="muted" style="padding:14px;text-align:center" data-testid="console-empty">{{ entries.length ? 'Filtr bo\'yicha yozuv yo\'q' : "Hali yozuv yo'q — so'rov yuboring yoki skriptda console.log() chaqiring" }}</div>
    </div>
  </section>
</template>
