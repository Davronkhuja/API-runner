<script setup lang="ts">
/** YAGONA "Run sozlamalari" paneli (Runner va so'rovdagi Batch uchun): iteratsiyalar, kechikish, parallel, retry, timeout, SSL, muhit, data fayl (oldindan ko'rish bilan), tanlovlar. */
import { ref } from 'vue'
import Icon from './Icon.vue'
import DataPreview from './DataPreview.vue'
import { useWorkspace } from '../stores/workspace'
import { isDataFile } from '../lib/datafile'
import type { RunSettings } from '../lib/runs'

const props = defineProps<{ model: RunSettings; tid: string; data: { name: string; rows: Record<string, unknown>[] } | null; mode?: 'runner' | 'batch'; rowsMode?: 'all' | 'custom'; rowsCount?: number }>()
const emit = defineEmits<{ change: []; 'data-file': [file: File]; 'data-clear': []; 'update:rowsMode': [v: 'all' | 'custom']; 'update:rowsCount': [v: number] }>()
const ws = useWorkspace()
const t = (n: string) => `${props.tid}-${n}`
const fileEl = ref<HTMLInputElement>(), zone = ref(false)
const batch = props.mode === 'batch'
function onPick(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) emit('data-file', f); (e.target as HTMLInputElement).value = '' }
function onDrop(e: DragEvent) { zone.value = false; const f = e.dataTransfer?.files?.[0]; if (f && isDataFile(f)) { e.preventDefault(); e.stopPropagation(); emit('data-file', f) } }
const num = (k: 'iterations' | 'delay_ms' | 'parallel' | 'retry' | 'timeout', e: Event, lo = 0) => { const v = (e.target as HTMLInputElement).value; (props.model as any)[k] = v === '' && k === 'iterations' ? null : Math.max(lo, Number(v) || 0); emit('change') }
</script>

<template>
  <div class="run-settings" :data-testid="t('run-settings')">
    <div class="rs-grid" :data-testid="tid === 'batch' ? 'batch-grid' : t('grid')">
      <div v-if="!batch" class="bf"><span class="bl">Iteratsiyalar</span>
        <input type="number" min="1" :placeholder="String(data?.rows.length || 1)" :value="model.iterations ?? ''" :data-testid="t('iterations')" aria-label="Iteratsiyalar" @input="num('iterations', $event, 1)"></div>
      <div v-else class="bf"><span class="bl">Qatorlar</span>
        <span class="bf-row"><select :value="rowsMode" :data-testid="t('rows-mode')" aria-label="Qatorlar" @change="emit('update:rowsMode', ($event.target as HTMLSelectElement).value as 'all' | 'custom')"><option value="all">Hammasi</option><option value="custom">Soni</option></select>
          <input v-if="rowsMode === 'custom'" type="number" min="1" style="width:80px" :value="rowsCount" aria-label="Qatorlar soni" :data-testid="t('count')" @input="emit('update:rowsCount', Number(($event.target as HTMLInputElement).value) || 1)"></span></div>
      <div class="bf"><span class="bl">Kechikish, ms</span><input type="number" min="0" step="50" :value="model.delay_ms" :data-testid="t('delay')" aria-label="Kechikish, ms" @input="num('delay_ms', $event)"></div>
      <div class="bf"><span class="bl">Parallel</span><input type="number" min="1" max="10" :value="model.parallel" :data-testid="t(batch ? 'concurrency' : 'parallel')" aria-label="Parallel so'rovlar" @input="num('parallel', $event, 1)"></div>
      <div class="bf"><span class="bl">Retry</span><input type="number" min="0" max="5" :value="model.retry" :data-testid="t('retry')" aria-label="Retry" @input="num('retry', $event)"></div>
      <div class="bf"><span class="bl">Timeout, s</span><input type="number" min="1" max="600" :value="model.timeout" :data-testid="t('timeout')" aria-label="Timeout, s" @input="num('timeout', $event, 1)"></div>
      <label class="bf"><span class="bl">Muhit</span>
        <select :value="ws.activeEnvId ?? ''" :data-testid="t('env')" aria-label="Muhit" @change="ws.setActive(($event.target as HTMLSelectElement).value || null)">
          <option value="">Muhit yo'q</option><option v-for="e in ws.environments" :key="e.id" :value="e.id">{{ e.name }}{{ e.kind ? ' · ' + e.kind : '' }}</option></select></label>
    </div>

    <div class="rs-data">
      <span class="bl">Ma'lumot fayli (CSV/JSON)</span>
      <div v-if="data" class="rs-file">
        <span class="rs-badge">{{ /\.json$/i.test(data.name) ? 'JSON' : 'CSV' }}</span>
        <span class="rs-fname"><b :data-testid="t('data-info')">{{ data.name }}: {{ data.rows.length }} qator</b><small class="muted">{{ Object.keys(data.rows[0] ?? {}).slice(0, 6).join(', ') }}</small></span>
        <button class="ib" aria-label="Faylni olib tashlash" :data-testid="batch ? 'batch-file-clear' : t('data-clear')" @click="emit('data-clear')"><Icon name="x" :size="15" /></button>
      </div>
      <div v-else class="drop-zone" :class="{ over: zone }" :data-testid="t('dropzone')" @dragover.prevent="zone = true" @dragleave="zone = false" @drop="onDrop">
        <span :data-testid="t('data-info')" class="muted">{{ batch ? "faylsiz — 1 ta so'rov" : 'CSV/JSON ni shu yerga tashlang' }}</span><br>
        <button class="sm" :data-testid="t('file-btn')" @click="fileEl?.click()">Tanlash…</button>
      </div>
      <input ref="fileEl" type="file" accept=".csv,.json" hidden :data-testid="t('file')" @change="onPick">
      <DataPreview v-if="data?.rows.length" :rows="data.rows" />
    </div>

    <div class="rs-checks">
      <label><input type="checkbox" v-model="model.save_vars" :data-testid="t('save-vars')" @change="emit('change')">O'zgaruvchi qiymatlarini saqlash <small class="muted">(o'chiq: skriptlar o'zgartirgani run tugagach qaytariladi)</small></label>
      <label><input type="checkbox" v-model="model.stop_on_error" :data-testid="t('stop-on-error')" @change="emit('change')">Birinchi xatoda to'xtash</label>
      <label><input type="checkbox" v-model="model.save_responses" :data-testid="t('save-responses')" @change="emit('change')">Javoblarni saqlash</label>
      <label><input type="checkbox" v-model="model.ssl" :data-testid="t('ssl')" @change="emit('change')">SSL tekshirish</label>
    </div>
  </div>
</template>
