<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { sendTab, saveTab } from '../lib/actions'
import { fmtBytes, fmtMs, showToast } from '../lib/ui'
import KvTable from './KvTable.vue'
import BatchPanel from './BatchPanel.vue'
import { composeUrl, paramsFromUrl } from '../lib/draft'
import { applyCurlToDraft, buildCurl, parseCurl } from '../lib/curl'
import { highlightCurl, highlightJson } from '../lib/highlight'

const props = defineProps<{ tab: Tab }>()
const tabs = useTabs(), ws = useWorkspace(), hist = useHistory()
const d = computed(() => props.tab.draft!)
const section = computed({ get: () => props.tab.activeSection ?? 'params', set: v => (props.tab.activeSection = v) })
const touch = () => tabs.touch(props.tab.id)
const curlOpen = ref(false)
const curlText = computed(() => buildCurl(d.value))
const autoCT = computed(() => ({ json: 'application/json', form: 'application/x-www-form-urlencoded', multipart: 'multipart/form-data' } as Record<string, string>)[d.value.body.mode] ?? '')
const effectiveCT = computed(() => (d.value.body.mode === 'json' || d.value.body.mode === 'raw') && d.value.body.contentType ? d.value.body.contentType : autoCT.value)
function onEsc(e: KeyboardEvent) { if (e.key === 'Escape' && curlOpen.value) curlOpen.value = false }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
// Editor / javob ajratgichi (vertikal)
const respH = ref<number | null>(null)
function startResize(e: PointerEvent) {
  const startY = e.clientY, startH = respEl.value?.offsetHeight ?? 200
  const move = (ev: PointerEvent) => { respH.value = Math.max(80, startH + (startY - ev.clientY)) }
  const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
  window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
}
function copyCurl() { navigator.clipboard?.writeText(curlText.value); showToast('Nusxalandi', 'success') }
function beautify() {
  try { d.value.body.raw = JSON.stringify(JSON.parse(d.value.body.raw), null, 2); touch() } catch { showToast('JSON noto\'g\'ri — formatlab bo\'lmadi', 'warn') }
}
const showPass = ref(false)
const showHist = ref(false)
const hideHist = () => { setTimeout(() => (showHist.value = false), 150) }
const reqEl = ref<HTMLElement>(), respEl = ref<HTMLElement>()

// URL ↔ Params ikki tomonlama sinxron
function onUrlInput() { d.value.params = paramsFromUrl(d.value.url, d.value.params); touch() }
function onParamsChange() { d.value.url = composeUrl(d.value.url, d.value.params); touch() }
// cURL paste (to'liq parser — paritet bandi; hozir minimal)
function onPaste(e: ClipboardEvent) {
  const parsed = parseCurl(e.clipboardData?.getData('text') ?? '')
  if (!parsed) return
  e.preventDefault()
  applyCurlToDraft(d.value, parsed)
  touch()
}
const bodyText = computed(() => {
  const r = props.tab.response
  if (!r || r.loading) return ''
  return typeof r.response === 'string' ? r.response : JSON.stringify(r.response, null, 2)
})
const statusClass = computed(() => { const s = props.tab.response?.status; return typeof s === 'number' && s < 400 ? 'ok' : 'err' })
const urlHist = computed(() => hist.urls.map(h => h.payload).filter((p: any) => p?.url && p.url.toLowerCase().includes(d.value.url.toLowerCase())).slice(0, 8))

// Scroll holatini tabda saqlash/tiklash
watch(() => props.tab.id, async () => { await nextTick(); if (reqEl.value) reqEl.value.scrollTop = props.tab.scroll.req; if (respEl.value) respEl.value.scrollTop = props.tab.scroll.resp }, { immediate: true })
</script>

<template>
  <div style="display:flex;flex-direction:column;flex:1;min-height:0" data-testid="request-editor">
    <div class="urlbar" style="position:relative">
      <select v-model="d.method" data-testid="method" :class="'m-' + d.method" @change="touch">
        <option v-for="m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']" :key="m" :class="'m-' + m">{{ m }}</option>
      </select>
      <input v-model="d.url" data-testid="url" placeholder="https://api.example.com/endpoint/{{id}}  yoki  curl '...' ni bu yerga joylashtiring"
             @input="onUrlInput" @paste="onPaste" @focus="showHist = true; hist.load()" @blur="hideHist"
             @keydown.enter="sendTab(tab)">
      <div v-if="showHist && urlHist.length" class="menu" style="position:absolute;left:90px;top:44px;right:130px" data-testid="url-history">
        <button v-for="(h, i) in urlHist" :key="i" @mousedown.prevent="d.method = h.method; d.url = h.url; touch()"><b>{{ h.method }}</b> {{ h.url }}</button>
      </div>
      <button class="primary" data-testid="send" :disabled="tab.response?.loading" @click="sendTab(tab)">▶ Yuborish</button>
      <button data-testid="curl-btn" title="Copy as cURL" @click="curlOpen = true">cURL</button>
      <button data-testid="save" :disabled="!tab.dirty && !!tab.ref" @click="saveTab(tab)">Saqlash</button>
    </div>
    <div class="sections" data-testid="sections">
      <button v-for="s in ['params', 'headers', 'auth', 'body', 'batch']" :key="s" :class="{ on: section === s }" :data-section="s" @click="section = s">
        {{ { params: 'Params', headers: 'Headers', auth: 'Auth', body: 'Body', batch: 'Batch / Runner' }[s] }}
      </button>
    </div>
    <div class="editor" ref="reqEl" @scroll="tab.scroll.req = ($event.target as HTMLElement).scrollTop">
      <KvTable v-if="section === 'params'" :rows="d.params" files testid="params-table" @change="onParamsChange" />
      <KvTable v-else-if="section === 'headers'" :rows="d.headers" testid="headers-table" @change="touch" />
      <div v-else-if="section === 'auth'" data-testid="auth-panel">
        <select v-model="d.auth.type" data-testid="auth-type" @change="touch">
          <option value="none">Auth yo'q</option><option value="bearer">Bearer Token</option><option value="basic">Basic Auth</option><option value="custom">Custom</option>
        </select>
        <p v-if="d.auth.type === 'bearer'"><input v-model="d.auth.token" placeholder="Token" style="width:100%" data-testid="auth-token" @input="touch"></p>
        <p v-if="d.auth.type === 'basic'"><input v-model="d.auth.user" placeholder="Username" @input="touch"> <input v-model="d.auth.pass" :type="showPass ? 'text' : 'password'" placeholder="Password" data-testid="auth-pass" @input="touch"> <button class="ghost" data-testid="auth-eye" @click="showPass = !showPass">👁</button> <span class="muted" data-testid="auth-preview">Authorization: Basic {{ (d.auth.user || d.auth.pass) ? '••••' : '' }}</span></p>
        <p v-if="d.auth.type === 'custom'"><input v-model="d.auth.custom" placeholder="Authorization qiymati" style="width:100%" @input="touch"></p>
      </div>
      <BatchPanel v-else-if="section === 'batch'" :tab="tab" />
      <div v-else data-testid="body-panel">
        <select v-model="d.body.mode" data-testid="body-mode" @change="touch">
          <option value="none">none</option><option value="json">JSON</option><option value="raw">Raw</option><option value="form">x-www-form-urlencoded</option><option value="multipart">form-data</option>
        </select>
        <button v-if="d.body.mode === 'json'" data-testid="beautify" style="margin-left:8px" @click="beautify" title="Cmd/Ctrl+B">Beautify</button>
        <input v-if="d.body.mode !== 'none' && d.body.mode !== 'form' && d.body.mode !== 'multipart'" v-model="d.body.contentType" :placeholder="autoCT || 'Content-Type'" style="margin-left:8px;width:220px" data-testid="content-type" @input="touch">
        <span v-if="effectiveCT" class="muted" style="margin-left:8px" data-testid="content-type-auto">Content-Type: {{ effectiveCT }}</span>
        <textarea v-if="d.body.mode === 'json' || d.body.mode === 'raw'" @keydown.meta.b.prevent="beautify" @keydown.ctrl.b.prevent="beautify" v-model="d.body.raw" data-testid="body-raw" style="width:100%;height:220px;margin-top:8px;font-family:ui-monospace,monospace" @input="touch" />
        <KvTable v-else-if="d.body.mode === 'form'" :rows="d.body.fields" testid="form-table" @change="touch" />
        <KvTable v-else-if="d.body.mode === 'multipart'" :rows="d.body.fields" files testid="formdata-table" @change="touch" />
      </div>
    </div>
    <div class="v-resizer" data-testid="resp-resizer" @pointerdown.prevent="startResize" />
    <div class="resp" ref="respEl" data-testid="response" :style="respH ? { flex: 'none', height: respH + 'px' } : {}" @scroll="tab.scroll.resp = ($event.target as HTMLElement).scrollTop">
      <div v-if="!tab.response" class="empty">Javob shu yerda ko'rinadi</div>
      <div v-else-if="tab.response.loading" class="muted">Yuborilmoqda…</div>
      <template v-else>
        <div style="display:flex;gap:14px;align-items:center;margin-bottom:8px">
          <span class="status-pill" :class="statusClass" data-testid="resp-status">{{ tab.response.status }}</span>
          <span data-testid="resp-time">{{ fmtMs(tab.response.time) }}</span>
          <span data-testid="resp-size">{{ fmtBytes(tab.response.size ?? 0) }}</span>
          <span class="muted" data-testid="resp-timing" :title="'DNS / connect / TLS / TTFB'">
            DNS — · connect {{ fmtMs(tab.response.timing?.connect) }} · TLS {{ fmtMs(tab.response.timing?.tls) }} · TTFB {{ fmtMs(tab.response.timing?.ttfb) }}
          </span>
        </div>
        <pre data-testid="resp-body" v-html="highlightJson(bodyText)" />
      </template>
    </div>
  </div>
  <div v-if="curlOpen" class="overlay" @click.self="curlOpen = false"><div class="dialog" style="width:640px" data-testid="curl-drawer">
    <div style="display:flex;gap:8px"><b style="flex:1">cURL</b><button data-testid="curl-copy" @click="copyCurl">Nusxa</button><button @click="curlOpen = false">×</button></div>
    <pre style="margin-top:10px" data-testid="curl-output" v-html="highlightCurl(curlText)" /></div></div>
</template>