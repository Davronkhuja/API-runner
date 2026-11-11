<script setup lang="ts">
/** Proxy capture: lokal HTTP proxy; ushlangan so'rovlar ro'yxati; tanlanganlarni collection'ga saqlash. */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Dialog from './Dialog.vue'
import { get, post } from '../api/client'
import { showToast } from '../lib/ui'
import { fmtTime } from '../lib/protocols'
import { useTree } from '../stores/tree'

const emit = defineEmits<{ close: [] }>()
interface Entry { seq: number; ts: number; method: string; url: string; kind: string; status: number; ms: number; error?: string }
const tree = useTree()
const running = ref(false), url = ref(''), port = ref<number | null>(null), err = ref(''), busy = ref(false)
const log = ref<Entry[]>([]), picked = ref<number[]>([]), cid = ref(tree.metas[0]?.id ?? ''), folder = ref("Ushlangan so'rovlar")
let timer: ReturnType<typeof setInterval> | undefined, next = 0
async function refresh() {
  try {
    const d = await get(`/api/proxy?from=${next}`)
    running.value = d.running; url.value = d.url ?? ''
    if (!d.running) { next = 0; return }
    if (d.entries.length) { log.value.push(...d.entries); next = d.next; if (log.value.length > 500) log.value.splice(0, log.value.length - 500) }
  } catch { /* vaqtincha */ }
}
onMounted(() => { refresh(); timer = setInterval(refresh, 1000) })
onBeforeUnmount(() => clearInterval(timer))
async function start() {
  busy.value = true; err.value = ''
  try { const d = await post('/api/proxy/start', { port: port.value ?? 0 }); running.value = true; url.value = d.url; next = 0; log.value = []; picked.value = [] } catch (e: any) { err.value = e.message } finally { busy.value = false }
}
async function stop() { await post('/api/proxy/stop'); running.value = false; showToast("Proxy to'xtatildi", 'info') }
async function clear() { await post('/api/proxy/clear'); log.value = []; picked.value = [] }
const savable = computed(() => log.value.filter(e => e.kind === 'http'))
async function save() {
  err.value = ''
  try {
    const r = await post('/api/proxy/save', { collection_id: cid.value, seqs: picked.value, folder_name: folder.value })
    await tree.reloadCollection(cid.value); showToast(`${r.saved} ta so'rov collection'ga saqlandi`, 'success')
  } catch (e: any) { err.value = e.message }
}
const copy = () => { navigator.clipboard?.writeText(url.value); showToast('Manzil nusxalandi', 'success') }
</script>

<template>
  <Dialog title="Proxy capture" testid="proxy-dialog" width="min(900px,94vw)" @close="emit('close')">
    <div v-if="!running" class="mock-form">
      <p class="muted" style="margin:0">Lokal HTTP proxy ishga tushiriladi; ilova/brauzer proxy sifatida shu manzilga sozlansa, o'tgan <b>HTTP</b> so'rovlar yozib olinadi. HTTPS faqat tunnel qilinadi (ichi ko'rinmaydi).</p>
      <label class="bf"><span class="bl">Port (bo'sh — avtomatik)</span><input type="number" min="0" max="65535" v-model.number="port" placeholder="8888" data-testid="proxy-port" aria-label="Port"></label>
      <p v-if="err" class="state-error" role="alert" data-testid="proxy-error" style="margin:0;padding:6px 10px">{{ err }}</p>
    </div>
    <template v-else>
      <div class="mock-head"><span class="status-pill ok" role="status" data-testid="proxy-status">Ishlayapti</span><code data-testid="proxy-url">{{ url }}</code><button class="sm" @click="copy">Nusxa</button><button class="sm" data-testid="proxy-clear" @click="clear">Tozalash</button></div>
      <div class="mock-log scroll" data-testid="proxy-log"><p v-if="!log.length" class="muted" data-testid="proxy-log-empty" style="margin:var(--sp-3)">Hali so'rov ushlanmadi — proxy sifatida <code>{{ url }}</code> ni ko'rsating.</p>
        <label v-for="e in [...log].reverse()" :key="e.seq" class="mock-row" data-testid="proxy-entry"><input v-if="e.kind === 'http'" type="checkbox" :value="e.seq" v-model="picked" :aria-label="`Tanlash: ${e.method} ${e.url}`" data-testid="proxy-pick"><span v-else style="width:13px" aria-hidden="true"></span><span class="muted">{{ fmtTime(e.ts) }}</span><b class="m" :class="'m-' + e.method">{{ e.method }}</b><span class="mp">{{ e.url }}</span><span class="status-pill" :class="e.status < 400 ? 'ok' : 'err'">{{ e.status }}</span><span class="muted">{{ e.ms }} ms</span></label></div>
      <div class="mon-row" style="margin-top:var(--sp-3);align-items:flex-end">
        <label class="bf"><span class="bl">Collection</span><select v-model="cid" data-testid="proxy-col" aria-label="Collection"><option v-for="m in tree.metas" :key="m.id" :value="m.id">{{ m.name }}</option></select></label>
        <label class="bf"><span class="bl">Papka nomi</span><input v-model="folder" data-testid="proxy-folder" aria-label="Papka nomi"></label>
        <button class="primary" data-testid="proxy-save" :disabled="!savable.length || !cid" @click="save">{{ picked.length ? `Tanlanganlarni saqlash (${picked.length})` : `Hammasini saqlash (${savable.length})` }}</button>
      </div>
      <p v-if="err" class="state-error" role="alert" data-testid="proxy-error" style="margin:var(--sp-2) 0 0;padding:6px 10px">{{ err }}</p>
    </template>
    <template #footer>
      <button @click="emit('close')">Yopish</button>
      <button v-if="!running" class="primary" data-testid="proxy-start" :disabled="busy" @click="start">Ishga tushirish</button>
      <button v-else data-testid="proxy-stop" @click="stop">To'xtatish</button>
    </template>
  </Dialog>
</template>
