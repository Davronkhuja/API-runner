<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { sendTab, saveTab } from '../lib/actions'
import { fmtBytes, fmtMs } from '../lib/ui'
import KvTable from './KvTable.vue'

const props = defineProps<{ tab: Tab }>()
const tabs = useTabs(), ws = useWorkspace(), hist = useHistory()
const d = computed(() => props.tab.draft!)
const section = computed({ get: () => props.tab.activeSection ?? 'params', set: v => (props.tab.activeSection = v) })
const touch = () => tabs.touch(props.tab.id)
const showHist = ref(false)
const hideHist = () => { setTimeout(() => (showHist.value = false), 150) }
const reqEl = ref<HTMLElement>(), respEl = ref<HTMLElement>()

// URL ?query <-> Params jadvali
function onUrlInput() {
  const raw = d.value.url
  const q = raw.indexOf('?')
  if (q >= 0) {
    const sp = new URLSearchParams(raw.slice(q + 1))
    d.value.url = raw.slice(0, q)
    const rows = [...sp.entries()].map(([key, value]) => ({ key, value, enabled: true }))
    d.value.params = [...rows, { key: '', value: '', enabled: true }]
  }
  touch()
}
// cURL paste (to'liq parser — paritet bandi; hozir minimal)
function onPaste(e: ClipboardEvent) {
  const text = e.clipboardData?.getData('text') ?? ''
  if (!/^\s*curl\b/i.test(text)) return
  e.preventDefault()
  const m = text.match(/(?:'|")?(https?:\/\/[^\s'"]+)/)
  const meth = text.match(/-X\s+(\w+)/)
  if (m) { d.value.url = m[1].split('?')[0]; onUrlInput(); d.value.url = m[1].split('?')[0] }
  if (meth) d.value.method = meth[1].toUpperCase()
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
      <select v-model="d.method" data-testid="method" @change="touch">
        <option v-for="m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']" :key="m">{{ m }}</option>
      </select>
      <input v-model="d.url" data-testid="url" placeholder="https://api.example.com/endpoint/{{id}}  yoki  curl '...' ni bu yerga joylashtiring"
             @input="onUrlInput" @paste="onPaste" @focus="showHist = true; hist.load()" @blur="hideHist"
             @keydown.enter="sendTab(tab)">
      <div v-if="showHist && urlHist.length" class="menu" style="position:absolute;left:90px;top:44px;right:130px" data-testid="url-history">
        <button v-for="(h, i) in urlHist" :key="i" @mousedown.prevent="d.method = h.method; d.url = h.url; touch()"><b>{{ h.method }}</b> {{ h.url }}</button>
      </div>
      <button class="primary" data-testid="send" :disabled="tab.response?.loading" @click="sendTab(tab)">▶ Yuborish</button>
      <button data-testid="save" :disabled="!tab.dirty && !!tab.ref" @click="saveTab(tab)">Saqlash</button>
    </div>
    <div class="sections" data-testid="sections">
      <button v-for="s in ['params', 'headers', 'auth', 'body']" :key="s" :class="{ on: section === s }" :data-section="s" @click="section = s">
        {{ { params: 'Params', headers: 'Headers', auth: 'Auth', body: 'Body' }[s] }}
      </button>
    </div>
    <div class="editor" ref="reqEl" @scroll="tab.scroll.req = ($event.target as HTMLElement).scrollTop">
      <KvTable v-if="section === 'params'" :rows="d.params" files testid="params-table" @change="touch" />
      <KvTable v-else-if="section === 'headers'" :rows="d.headers" testid="headers-table" @change="touch" />
      <div v-else-if="section === 'auth'" data-testid="auth-panel">
        <select v-model="d.auth.type" data-testid="auth-type" @change="touch">
          <option value="none">Auth yo'q</option><option value="bearer">Bearer Token</option><option value="basic">Basic Auth</option><option value="custom">Custom</option>
        </select>
        <p v-if="d.auth.type === 'bearer'"><input v-model="d.auth.token" placeholder="Token" style="width:100%" data-testid="auth-token" @input="touch"></p>
        <p v-if="d.auth.type === 'basic'"><input v-model="d.auth.user" placeholder="Username" @input="touch"> <input v-model="d.auth.pass" type="password" placeholder="Password" @input="touch"></p>
        <p v-if="d.auth.type === 'custom'"><input v-model="d.auth.custom" placeholder="Authorization qiymati" style="width:100%" @input="touch"></p>
      </div>
      <div v-else data-testid="body-panel">
        <select v-model="d.body.mode" data-testid="body-mode" @change="touch">
          <option value="none">none</option><option value="json">JSON</option><option value="raw">Raw</option><option value="form">x-www-form-urlencoded</option><option value="multipart">form-data</option>
        </select>
        <textarea v-if="d.body.mode === 'json' || d.body.mode === 'raw'" v-model="d.body.raw" data-testid="body-raw" style="width:100%;height:220px;margin-top:8px;font-family:ui-monospace,monospace" @input="touch" />
        <KvTable v-else-if="d.body.mode === 'form'" :rows="d.body.fields" testid="form-table" @change="touch" />
        <KvTable v-else-if="d.body.mode === 'multipart'" :rows="d.body.fields" files testid="formdata-table" @change="touch" />
      </div>
    </div>
    <div class="resp" ref="respEl" data-testid="response" @scroll="tab.scroll.resp = ($event.target as HTMLElement).scrollTop">
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
        <pre data-testid="resp-body">{{ bodyText }}</pre>
      </template>
    </div>
  </div>
</template>
