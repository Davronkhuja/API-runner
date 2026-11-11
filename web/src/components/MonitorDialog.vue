<script setup lang="ts">
/** Rejalashtirilgan run'lar (monitor): cron ifoda, collection/papka/muhit, xatoda macOS bildirishnomasi; natijalar run tarixida. */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Dialog from './Dialog.vue'
import { del, get, post, put } from '../api/client'
import { askConfirm, showToast } from '../lib/ui'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'

const emit = defineEmits<{ close: [] }>()
interface Last { at: number; ok: boolean; failures: number; total: number; error: string | null; duration: number; run_id: string | null }
interface Mon { id: string; name: string; collection_id: string; folder: string | null; env_name: string; cron: string; enabled: boolean; notify: boolean; last: Last | null; next_at: number | null }
const tree = useTree(), ws = useWorkspace()
const items = ref<Mon[]>([]), editing = ref<Partial<Mon> | null>(null), err = ref(''), cronHint = ref(''), cronOk = ref(true)
let timer: ReturnType<typeof setInterval> | undefined
async function load() { try { items.value = (await get('/api/monitors')).items } catch { /* vaqtincha */ } }
onMounted(() => { load(); timer = setInterval(load, 3000) })
onBeforeUnmount(() => clearInterval(timer))
const fmt = (ts: number | null) => ts ? new Date(ts * 1000).toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const colName = (id: string) => tree.metas.find(m => m.id === id)?.name ?? '(o\'chirilgan)'
const presets: [string, string][] = [['Har daqiqa', '* * * * *'], ['Har 5 daqiqa', '*/5 * * * *'], ['Har soat', '0 * * * *'], ['Har kuni 09:00', '0 9 * * *'], ['Ish kunlari 09:00', '0 9 * * mon-fri']]
function folders(cid?: string): { id: string; name: string }[] {
  const out: { id: string; name: string }[] = []
  const walk = (list: any[], prefix: string) => { for (const it of list ?? []) if (it.item) { out.push({ id: it.id, name: prefix + it.name }); walk(it.item, prefix + it.name + ' / ') } }
  walk(cid ? tree.cols[cid]?.item : [], '')
  return out
}
const folderList = computed(() => folders(editing.value?.collection_id))
function add() { editing.value = { name: '', collection_id: tree.metas[0]?.id, folder: null, env_name: ws.activeEnv?.name ?? '', cron: '*/5 * * * *', enabled: true, notify: true }; err.value = ''; checkCron() }
function edit(m: Mon) { editing.value = { ...m }; err.value = ''; checkCron() }
async function checkCron() {
  const r = await post('/api/monitors/validate', { cron: editing.value?.cron ?? '' })
  cronOk.value = r.ok; cronHint.value = r.ok ? `Keyingi: ${fmt(r.next_at)}` : r.error
}
async function save() {
  const e = editing.value!; err.value = ''
  try { e.id ? await put(`/api/monitors/${e.id}`, e) : await post('/api/monitors', e); editing.value = null; await load() } catch (x: any) { err.value = x.message }
}
async function toggle(m: Mon) { await put(`/api/monitors/${m.id}`, { ...m, enabled: !m.enabled }); await load() }
async function runNow(m: Mon) { await post(`/api/monitors/${m.id}/run`); showToast('Monitor ishga tushirildi', 'info'); setTimeout(load, 1500) }
async function remove(m: Mon) { if (await askConfirm(`«${m.name}» monitori o'chirilsinmi? (Run tarixidagi natijalar saqlanadi)`, "O'chirish")) { await del(`/api/monitors/${m.id}`); await load() } }
</script>

<template>
  <Dialog title="Monitor — rejalashtirilgan run'lar" testid="monitor-dialog" width="min(860px,94vw)" @close="emit('close')">
    <div v-if="editing" class="mon-form" data-testid="monitor-form">
      <label class="bf"><span class="bl">Nomi</span><input v-model="editing.name" data-testid="mon-name" aria-label="Nomi" placeholder="Masalan: Prod sog'liq tekshiruvi"></label>
      <div class="mon-row">
        <label class="bf"><span class="bl">Collection</span><select v-model="editing.collection_id" data-testid="mon-col" aria-label="Collection" @change="editing!.folder = null"><option v-for="m in tree.metas" :key="m.id" :value="m.id">{{ m.name }}</option></select></label>
        <label class="bf"><span class="bl">Papka</span><select v-model="editing.folder" data-testid="mon-folder" aria-label="Papka"><option :value="null">Butun collection</option><option v-for="f in folderList" :key="f.id" :value="f.id">{{ f.name }}</option></select></label>
        <label class="bf"><span class="bl">Muhit</span><select v-model="editing.env_name" data-testid="mon-env" aria-label="Muhit"><option value="">(muhitsiz)</option><option v-for="e in ws.environments" :key="e.id" :value="e.name">{{ e.name }}</option></select></label>
      </div>
      <label class="bf"><span class="bl">Cron ifoda (daqiqa soat kun oy hafta-kuni)</span><input v-model="editing.cron" class="mono" data-testid="mon-cron" aria-label="Cron ifoda" @input="checkCron"></label>
      <div class="mon-presets"><button v-for="[l, c] in presets" :key="c" class="sm" :data-testid="'mon-preset'" @click="editing!.cron = c; checkCron()">{{ l }}</button></div>
      <p :class="cronOk ? 'muted' : 'state-error'" data-testid="mon-cron-hint" role="status" style="margin:0">{{ cronHint }}</p>
      <label class="mon-chk"><input type="checkbox" v-model="editing.notify" data-testid="mon-notify"> Xatoda macOS bildirishnomasi</label>
      <label class="mon-chk"><input type="checkbox" v-model="editing.enabled" data-testid="mon-enabled"> Yoqilgan</label>
      <p v-if="err" class="state-error" role="alert" data-testid="mon-error" style="margin:0;padding:6px 10px">{{ err }}</p>
    </div>
    <template v-else>
      <p class="muted" style="margin:0 0 var(--sp-3)">Ilova ochiq turganda belgilangan vaqtda collection avtomatik yuriladi. Natijalar «Tarix» / Runner tarixida <code>monitor</code> turi bilan saqlanadi.</p>
      <p v-if="!items.length" class="muted" data-testid="mon-empty">Hali monitor yo'q. «Yangi monitor» tugmasi bilan qo'shing.</p>
      <table v-else class="kv mon-table" data-testid="mon-list"><thead><tr><th>Nomi</th><th>Collection</th><th>Cron</th><th>Oxirgi natija</th><th>Keyingi</th><th></th></tr></thead>
        <tbody><tr v-for="m in items" :key="m.id" data-testid="mon-item" :class="{ off: !m.enabled }">
          <td>{{ m.name }}</td><td>{{ colName(m.collection_id) }}</td><td><code>{{ m.cron }}</code></td>
          <td><span v-if="m.last" class="status-pill" :class="m.last.ok ? 'ok' : 'err'" data-testid="mon-last">{{ m.last.ok ? 'OK' : 'Xato' }}</span> <small class="muted">{{ m.last ? `${fmt(m.last.at)} · ${m.last.total} so'rov` + (m.last.failures ? ` · ${m.last.failures} xato` : '') : '—' }}</small></td>
          <td class="muted">{{ m.enabled ? fmt(m.next_at) : 'o\'chiq' }}</td>
          <td class="mon-act"><button class="sm" data-testid="mon-run" @click="runNow(m)">Hozir</button><button class="sm" data-testid="mon-toggle" @click="toggle(m)">{{ m.enabled ? 'To\'xtatish' : 'Yoqish' }}</button><button class="sm" data-testid="mon-edit" @click="edit(m)">Tahrir</button><button class="sm" data-testid="mon-del" @click="remove(m)">O'chirish</button></td>
        </tr></tbody></table>
    </template>
    <template #footer>
      <button @click="editing ? editing = null : emit('close')">{{ editing ? 'Bekor qilish' : 'Yopish' }}</button>
      <button v-if="editing" class="primary" data-testid="mon-save" :disabled="!cronOk || !editing.collection_id" @click="save">Saqlash</button>
      <button v-else class="primary" data-testid="mon-new" :disabled="!tree.metas.length" @click="add">Yangi monitor</button>
    </template>
  </Dialog>
</template>
