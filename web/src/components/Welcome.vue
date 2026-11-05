<script setup lang="ts">
/** Tab ochiq bo'lmagan holat: boshlash kartalari, import zonasi, oxirgi so'rovlar, yorliqlar. */
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useHistory } from '../stores/history'
import { openFromHistory } from '../lib/history'
import { applyCurlToDraft, parseCurl } from '../lib/curl'
import { syncPathVars } from '../lib/draft'
import { sidePanel, showToast } from '../lib/ui'
import Icon from './Icon.vue'

const tabs = useTabs(), tree = useTree(), hist = useHistory()
const emit = defineEmits<{ import: []; 'import-file': [File] }>()
const recent = computed(() => hist.items.slice(0, 5))
const urlParts = (url: string) => { try { const u = new URL(url); return { host: u.host, path: u.pathname + u.search } } catch { return { host: '', path: url } } }
/** Nom: so'rov nomi; eski yozuvlarda nom yo'q — yo'lning oxirgi qismi (yoki URL). */
const labelOf = (h: any) => h.payload.name || urlParts(h.payload.url).path.split('?')[0].replace(/\/+$/, '').split('/').pop() || urlParts(h.payload.url).path || h.payload.url
const hostOf = (h: any) => urlParts(h.payload.url).host
onMounted(() => { hist.load(); window.addEventListener('paste', onPaste) })
onBeforeUnmount(() => window.removeEventListener('paste', onPaste))

/** ⌘V: buferdagi cURL yangi tabni to'ldiradi (kiritish maydoni fokusda bo'lmaganda). */
function onPaste(e: ClipboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return
  const p = parseCurl(e.clipboardData?.getData('text') ?? '')
  if (!p) return
  e.preventDefault()
  const t = tabs.openNew(); applyCurlToDraft(t.draft!, p); t.draft!.pathVars = syncPathVars(t.draft!.url, []); tabs.touch(t.id)
}
function runner() {
  sidePanel.value = 'runner'
  const m = tree.metas[0]
  if (!m) return showToast('Avval collection yarating', 'warn')
  tabs.open('runner', m.id, 'Runner: ' + m.name, { permanent: true })
}
function pasteHint() { showToast('Buyruqni ⌘V bilan joylashtiring — maydonlar o\'zi to\'ladi', 'info') }
const shortcuts = [['Yangi so\'rov', '⌘ T'], ['Yuborish', '⌘ ↵'], ['Saqlash', '⌘ S'], ['Tabni yopish', '⌘ W'], ['Keyingi tab', '⌃ Tab'], ['Qidirish', '⌘ K']]
const drop = (e: DragEvent) => { const f = e.dataTransfer?.files?.[0]; if (f) { e.preventDefault(); e.stopPropagation(); emit('import-file', f) } }
</script>

<template>
  <main class="welcome scroll" data-testid="no-tabs" aria-label="Bosh sahifa">
    <div class="inner">
      <div style="display:flex;flex-direction:column;gap:8px">
        <h1>Nimadan boshlaymiz?</h1>
        <p class="muted" style="margin:0;font-size:var(--fs-lg)">Yangi so'rov yarating, cURL joylashtiring yoki mavjud collection'ni import qiling.</p>
      </div>
      <div class="cards">
        <button class="card" data-testid="wl-new" @click="tabs.openNew()"><span class="ci solid"><Icon name="plus" :size="18" /></span><span class="ct">Yangi so'rov</span><span class="cd">Bo'sh tab ochiladi</span><span style="display:flex;gap:4px;margin-top:auto"><span class="kbd">⌘</span><span class="kbd">T</span></span></button>
        <button class="card" data-testid="wl-curl" @click="pasteHint"><span class="ci">$_</span><span class="ct">cURL'dan</span><span class="cd">Buyruqni joylashtiring — maydonlar o'zi to'ladi</span><span style="display:flex;gap:4px;margin-top:auto"><span class="kbd">⌘</span><span class="kbd">V</span></span></button>
        <button class="card" data-testid="wl-import" @click="emit('import')"><span class="ci"><Icon name="download" :size="18" /></span><span class="ct">Import</span><span class="cd">Postman, OpenAPI</span><span class="cd" style="margin-top:auto;font-size:var(--fs-sm)">yoki ⌘K → «Import»</span></button>
        <button class="card" data-testid="wl-runner" @click="runner"><span class="ci"><Icon name="play" :size="18" /></span><span class="ct">Runner</span><span class="cd">Collection yoki CSV bilan ko'p marta</span><span class="cd" style="margin-top:auto;font-size:var(--fs-sm)">yoki ⌘K → «Runner»</span></button>
      </div>
      <label class="dz" data-testid="wl-dropzone" @dragover.prevent @drop="drop">
        <Icon name="upload" :size="22" />
        <span><b style="color:var(--text);font-weight:600">Faylni shu yerga tashlang</b> yoki <u style="color:var(--accent-text)">tanlang</u></span>
        <span style="font-size:var(--fs-sm)">.json · .csv</span>
        <input type="file" accept=".json,.csv" class="sr-only" aria-label="Import uchun fayl" data-testid="wl-file" @change="(e: any) => { const f = e.target.files?.[0]; if (f) emit('import-file', f); e.target.value = '' }">
      </label>
      <div class="two">
        <section aria-labelledby="wl-recent">
          <h2 id="wl-recent">Oxirgi so'rovlar</h2>
          <div class="list-box" data-testid="wl-recent">
            <button v-for="h in recent" :key="h.id" class="row" style="height:34px" data-testid="wl-recent-row" @click="openFromHistory(h)">
              <span class="m" :class="'m-' + h.payload.method">{{ h.payload.method }}</span><span class="name" :title="h.payload.url" data-testid="wl-recent-name">{{ labelOf(h) }}</span><span class="muted wl-host" data-testid="wl-recent-host">{{ hostOf(h) }}</span>
            </button>
            <div v-if="!recent.length" class="muted" style="padding:14px;text-align:center" data-testid="wl-recent-empty">Hali so'rov yuborilmagan</div>
          </div>
        </section>
        <section aria-labelledby="wl-keys">
          <h2 id="wl-keys">Klaviatura yorliqlari</h2>
          <div class="list-box" style="padding:2px 12px">
            <div v-for="s in shortcuts" :key="s[0]" class="sc-row"><span>{{ s[0] }}</span><span class="kbd">{{ s[1] }}</span></div>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>
