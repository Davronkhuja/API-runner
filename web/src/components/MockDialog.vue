<script setup lang="ts">
/** Mock server: collection Example'lari asosida; port tanlash, kechikish, ishga tushirish/to'xtatish, yo'nalishlar va so'rovlar jurnali. */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Dialog from './Dialog.vue'
import { get, post } from '../api/client'
import { showToast } from '../lib/ui'
import { fmtTime } from '../lib/protocols'

const props = defineProps<{ cid: string; name: string }>()
const emit = defineEmits<{ close: [] }>()
interface Route { method: string; path: string; name: string; example: string; code: number; query: string[]; headers: string[] }
interface Mock { id: string; url: string; port: number; delay_ms: number; routes: Route[]; collection_id: string }
interface Entry { seq: number; ts: number; method: string; path: string; query: string; status: number; delay: number; ms: number; matched: string | null }
const mock = ref<Mock | null>(null), port = ref<number | null>(null), delay = ref(0), err = ref(''), busy = ref(false)
const log = ref<Entry[]>([])
let timer: ReturnType<typeof setInterval> | undefined, next = 0
async function refresh() {
  try {
    if (!mock.value) { const all: Mock[] = await get('/api/mocks'); mock.value = all.find(m => m.collection_id === props.cid) ?? null; if (mock.value) { next = 0; log.value = [] } }
    if (mock.value) {
      const d = await get(`/api/mocks/${mock.value.id}/log?from=${next}`)
      if (!d.running) { mock.value = null; return }
      if (d.entries.length) { log.value.push(...d.entries); next = d.next; if (log.value.length > 300) log.value.splice(0, log.value.length - 300) }
    }
  } catch { /* server vaqtincha javob bermadi */ }
}
onMounted(() => { refresh(); timer = setInterval(refresh, 1000) })
onBeforeUnmount(() => clearInterval(timer))
async function start() {
  busy.value = true; err.value = ''
  try { mock.value = await post('/api/mocks', { collection_id: props.cid, port: port.value ?? 0, delay_ms: delay.value || 0 }); next = 0; log.value = [] } catch (e: any) { err.value = e.message } finally { busy.value = false }
}
async function stop() { if (mock.value) { await post(`/api/mocks/${mock.value.id}/stop`); mock.value = null; showToast('Mock server to\'xtatildi', 'info') } }
const copy = () => { navigator.clipboard?.writeText(mock.value!.url); showToast('Manzil nusxalandi', 'success') }
</script>

<template>
  <Dialog :title="`Mock server — ${name}`" testid="mock-dialog" width="min(860px,94vw)" @close="emit('close')">
    <div v-if="!mock" class="mock-form">
      <p class="muted" style="margin:0">Collection'dagi Example'lar (javob namunalari) asosida ishlaydi: metod + yo'l (<code>:id</code>, <code>{{ '{' + '{var}' + '}' }}</code>) va ixtiyoriy query / <code>x-mock-*</code> sarlavhalari bo'yicha moslanadi.</p>
      <label class="bf"><span class="bl">Port (bo'sh — avtomatik)</span><input type="number" min="0" max="65535" v-model.number="port" placeholder="3000" data-testid="mock-port" aria-label="Port"></label>
      <label class="bf"><span class="bl">Qo'shimcha kechikish, ms</span><input type="number" min="0" v-model.number="delay" data-testid="mock-delay" aria-label="Kechikish"></label>
      <p v-if="err" class="state-error" role="alert" data-testid="mock-error" style="margin:0;padding:6px 10px">{{ err }}</p>
    </div>
    <template v-else>
      <div class="mock-head"><span class="status-pill ok" role="status" data-testid="mock-status">Ishlayapti</span><code data-testid="mock-url">{{ mock.url }}</code><button class="sm" data-testid="mock-copy" @click="copy">Nusxa</button><span class="muted">{{ mock.routes.length }} ta yo'nalish{{ mock.delay_ms ? ` · +${mock.delay_ms} ms` : '' }}</span></div>
      <table class="kv mock-routes" data-testid="mock-routes"><thead><tr><th>Metod</th><th>Yo'l</th><th>Example</th><th>Kod</th><th>Shartlar</th></tr></thead>
        <tbody><tr v-for="(r, i) in mock.routes" :key="i"><td><b class="m" :class="'m-' + r.method">{{ r.method }}</b></td><td><code>{{ r.path }}</code></td><td>{{ r.name }} · {{ r.example }}</td><td>{{ r.code }}</td><td class="muted">{{ [...r.query, ...r.headers].join(' · ') || '—' }}</td></tr></tbody></table>
      <h4 style="margin:var(--sp-3) 0 var(--sp-1)">So'rovlar jurnali <small class="muted">({{ log.length }})</small></h4>
      <div class="mock-log scroll" data-testid="mock-log"><p v-if="!log.length" class="muted" data-testid="mock-log-empty" style="margin:var(--sp-3)">Hali so'rov kelmadi — <code>{{ mock.url }}</code> ga so'rov yuboring.</p>
        <div v-for="e in [...log].reverse()" :key="e.seq" class="mock-row" data-testid="mock-entry"><span class="muted">{{ fmtTime(e.ts) }}</span><b class="m" :class="'m-' + e.method">{{ e.method }}</b><span class="mp">{{ e.path }}{{ e.query ? '?' + e.query : '' }}</span><span class="status-pill" :class="e.status < 400 ? 'ok' : 'err'">{{ e.status }}</span><span class="muted">{{ e.ms }} ms</span><span class="muted mm">{{ e.matched ?? 'moslik yo\'q' }}</span></div></div>
    </template>
    <template #footer>
      <button @click="emit('close')">Yopish</button>
      <button v-if="!mock" class="primary" data-testid="mock-start" :disabled="busy" @click="start">Ishga tushirish</button>
      <button v-else data-testid="mock-stop" @click="stop">To'xtatish</button>
    </template>
  </Dialog>
</template>
