<script setup lang="ts">
/** Pre-request / Tests muharrirlari + tayyor snippet'lar. Request, papka va collection sozlamalarida ishlatiladi. */
import { computed, nextTick, ref, watch } from 'vue'
import { useWorkspace } from '../stores/workspace'
import { SNIPPETS } from '../lib/pmApi'
import type { ScriptError, ScriptSet } from '../lib/scripts'
import ScriptEditor from './ScriptEditor.vue'
import { showToast } from '../lib/ui'

const props = defineProps<{ scripts: ScriptSet; errors?: ScriptError[]; goto?: { kind: 'pre' | 'test'; line: number; nonce: number } | null; scope: 'request' | 'folder' | 'collection'; scopeId?: string }>()
const emit = defineEmits<{ change: [] }>()
const ws = useWorkspace()
const which = ref<'pre' | 'test'>('pre')
const ed = ref<InstanceType<typeof ScriptEditor>>()
const mine = (kind: 'pre' | 'test') => (props.errors ?? []).filter(e => e.origin.scope === props.scope && e.origin.kind === (kind === 'pre' ? 'prerequest' : 'test') && (props.scope === 'request' || !props.scopeId || e.origin.id === props.scopeId))
const lineErrors = computed(() => mine(which.value).map(e => ({ line: e.line, message: `${e.name}: ${e.message}` })))
const snippets = computed(() => SNIPPETS.filter(s => s.where === 'both' || s.where === which.value))
watch(() => props.goto, async g => { if (g) { which.value = g.kind; await nextTick() } }, { deep: true, immediate: true })
const goto = computed(() => (props.goto && props.goto.kind === which.value ? { line: props.goto.line, nonce: props.goto.nonce } : null))
const copyInstall = () => { navigator.clipboard?.writeText(ws.scripts.install); showToast('Nusxalandi', 'success') }
const label = { request: "so'rov", folder: 'papka', collection: 'collection' }[props.scope]
</script>

<template>
  <div data-testid="scripts-panel">
    <div v-if="!ws.scripts.available" class="script-off" role="alert" data-testid="scripts-off">
      <b>Skriptlar o'chiq.</b> <code>quickjs-ng</code> o'rnatilmagan, shuning uchun bu skriptlar saqlanadi, lekin <b>bajarilmaydi</b> (so'rovlar odatdagidek yuboriladi).
      <div style="margin-top:6px;display:flex;gap:8px;align-items:center"><code data-testid="scripts-install-cmd">{{ ws.scripts.install || 'pip install quickjs-ng' }}</code><button class="sm" @click="copyInstall">Nusxa</button></div>
    </div>
    <div class="script-layout">
      <div style="min-width:0;display:flex;flex-direction:column;gap:8px">
        <div class="seg-group" role="tablist" :aria-label="`${label} skriptlari`">
          <button class="seg" role="tab" :aria-selected="which === 'pre'" :class="{ on: which === 'pre' }" data-testid="script-tab-pre" @click="which = 'pre'">Pre-request<span v-if="scripts.pre.trim()" class="dot-mark" aria-label="skript bor" /></button>
          <button class="seg" role="tab" :aria-selected="which === 'test'" :class="{ on: which === 'test' }" data-testid="script-tab-test" @click="which = 'test'">Tests<span v-if="scripts.test.trim()" class="dot-mark" aria-label="skript bor" /></button>
        </div>
        <p class="muted" style="margin:0;font-size:12px">{{ which === 'pre' ? `So'rovdan OLDIN${scope === 'request' ? '' : ` (${label} ichidagi barcha so'rovlar uchun)`} ishlaydi.` : `Javobdan KEYIN${scope === 'request' ? '' : ` (${label} ichidagi barcha so'rovlar uchun)`} ishlaydi.` }} Tartib: collection → papka → so'rov.</p>
        <div class="script-box">
          <ScriptEditor v-if="which === 'pre'" key="pre" ref="ed" v-model="scripts.pre" testid="script-pre" :errors="lineErrors" :goto="goto" placeholder="// pm.environment.set('key', 'value')" @update:model-value="emit('change')" />
          <ScriptEditor v-else key="test" ref="ed" v-model="scripts.test" testid="script-test" :errors="lineErrors" :goto="goto" placeholder="// pm.test('Status 200', () => pm.response.to.have.status(200))" @update:model-value="emit('change')" />
        </div>
      </div>
      <aside class="snippets" aria-label="Tayyor snippetlar" data-testid="snippets">
        <div class="h-label">Tayyor snippetlar</div>
        <button v-for="s in snippets" :key="s.title" class="snip" data-testid="snippet" @click="ed?.insert(s.code); emit('change')">{{ s.title }}</button>
      </aside>
    </div>
  </div>
</template>
