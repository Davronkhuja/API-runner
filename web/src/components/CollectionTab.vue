<script setup lang="ts">
/** Collection / papka tabi (Postman kabi): Overview | Auth | Variables | Scripts | Run. ref: "cid" yoki "cid:folderId". */
import { computed, ref, watch } from 'vue'
import { put } from '../api/client'
import { useTree } from '../stores/tree'
import { useTabs, type Tab } from '../stores/tabs'
import { authFromPm, authToPm, type AuthDraft } from '../lib/auth'
import { fmtMs, showToast, sidePanel } from '../lib/ui'
import { openRequest } from '../lib/actions'
import { isOkStatus, useLastRun } from '../stores/lastrun'
import { eventsFromText, lastErrors, textFromEvents, type ScriptSet } from '../lib/scripts'
import { authSource, folderPath } from '../lib/scope'
import { authName, hasRealAuth, openNodeTab, overridableRequests, requestsIn, sameAuth, type Section } from '../lib/nodes'
import { isFolder as isFolderNode } from '../types/model'
import Icon from './Icon.vue'
import ScriptsPanel from './ScriptsPanel.vue'
import InlineName from './InlineName.vue'
import { renameNode, validateName } from '../lib/rename'
import AuthEditor from './AuthEditor.vue'
import VarsTable from './VarsTable.vue'
import BulkAuthDialog, { type Candidate } from './BulkAuthDialog.vue'

const props = defineProps<{ tab: Tab }>()
const tree = useTree(), tabs = useTabs(), last = useLastRun()
const [cid, fid] = (props.tab.ref ?? '').split(':')
const isFolder = !!fid
const node = computed<any>(() => (isFolder ? tree.findItem(cid, fid) : tree.cols[cid]))
const col = computed(() => tree.cols[cid])
const name = computed(() => node.value?.name ?? node.value?.info?.name ?? '')
const section = ref<Section>((props.tab.state?.section as Section) ?? 'overview')
watch(() => props.tab.state?.section, v => { if (v) section.value = v as Section })

interface Form { auth: AuthDraft; vars: any[]; scripts: ScriptSet; description: string }
const form = ref<Form | null>(null)
function load() {
  const n = node.value
  if (!n) { form.value = null; return }
  form.value = {
    auth: authFromPm(n.auth), vars: JSON.parse(JSON.stringify(n.variable ?? [])).map((v: any) => ({ type: 'default', ...v })),
    scripts: textFromEvents(n), description: n['x-apirunner']?.description ?? '',
  }
}
watch(() => props.tab.ref, load, { immediate: true })
const touch = () => tabs.touch(props.tab.id)
const renamingTitle = ref(false)
watch(() => tabs.renameRequest, id => { if (id === props.tab.id) { tabs.renameRequest = null; renamingTitle.value = true } })

// ── Overview ma'lumotlari ──
const crumbs = computed(() => [col.value?.info.name, ...(isFolder ? folderPath(col.value, fid).map(f => f.name) : []), ...(isFolder ? [name.value] : [])].filter(Boolean) as string[])
const reqs = computed(() => requestsIn(isFolder ? node.value?.item ?? [] : col.value?.item ?? []))
const folderCount = computed(() => { let n = 0; const walk = (xs: any[]) => xs.forEach(x => { if (isFolderNode(x)) { n++; walk(x.item) } }); walk(isFolder ? node.value?.item ?? [] : col.value?.item ?? []); return n })
const parentSrc = computed(() => (isFolder ? authSource(props.tab.ref) : null))
const authSummary = computed(() => {
  const pm = node.value?.auth
  if (pm?.type && pm.type !== 'noauth') return { text: authName(pm), own: true }
  if (pm?.type === 'noauth') return { text: "Auth yo'q", own: true }
  if (isFolder) return parentSrc.value ? { text: `Meros: ${authName(parentSrc.value.pm)} («${parentSrc.value.name}»)`, own: false } : { text: "Meros (ota tugunlarda auth yo'q)", own: false }
  return { text: "Auth yo'q", own: false }
})
// So'rovlar jadvali: metod, nom, auth manbai, oxirgi status va vaqt
const filter = ref('')
const rows = computed(() => reqs.value.map(r => {
  const a = r.item.request?.auth
  const own = !!a?.type && a.type !== 'noauth'
  const res = last.results[`${cid}:${r.item.id}`]
  return {
    id: r.item.id, method: r.item.request.method, name: r.item.name, path: r.path,
    auth: a?.type === 'noauth' ? "Auth yo'q" : own ? `${authName(a)} (o'zi)` : '↑ Meros', own, none: a?.type === 'noauth',
    status: res?.status, ok: res ? isOkStatus(res.status) : null, time: res ? fmtMs(res.time) : '—',
  }
}))
const shownRows = computed(() => { const q = filter.value.trim().toLowerCase(); return q ? rows.value.filter(r => (r.name + ' ' + r.path + ' ' + r.method).toLowerCase().includes(q)) : rows.value })
const inheritCount = computed(() => rows.value.filter(r => !r.own && !r.none).length)
const sameTokenCount = computed(() => (hasRealAuth(node.value?.auth) ? overridableRequests(cid, isFolder ? fid : null, node.value.auth).filter(c => c.same).length : 0))
const scriptKinds = computed(() => [form.value?.scripts.pre.trim() ? 'Pre-request' : '', form.value?.scripts.test.trim() ? 'Tests' : ''].filter(Boolean).join(' · '))
const lastRun = computed(() => last.runs[props.tab.ref!])
const lastRunOk = computed(() => lastRun.value?.items.filter(i => isOkStatus(i.status)).length ?? 0)
const lastRunWhen = computed(() => (lastRun.value ? new Date(lastRun.value.at).toLocaleString([], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''))
const nameOf = (id: string) => reqs.value.find(r => r.item.id === id)?.item.name ?? id
function offerInherit() {
  const cands = overridableRequests(cid, isFolder ? fid : null, node.value.auth)
  if (cands.length) bulk.value = { label: name.value, candidates: cands, newAuth: node.value.auth }
}
const ownAuthRequests = computed(() => reqs.value.filter(r => r.item.request?.auth?.type && r.item.request.auth.type !== 'noauth').length)

// ── Saqlash + ommaviy "Meros" taklifi ──
const bulk = ref<{ label: string; candidates: Candidate[]; newAuth: any } | null>(null)
async function save() {
  const f = form.value!
  const newPm = authToPm(f.auth) ?? null
  const oldPm = node.value.auth ?? null
  const patch: any = { variable: f.vars.filter(v => v.key), event: eventsFromText(node.value.event, f.scripts), auth: newPm }
  try {
    if (isFolder) {
      await tree.updateItem(cid, fid, { ...patch, 'x-apirunner': { ...(node.value['x-apirunner'] ?? {}), description: f.description } })
    } else {
      const c = JSON.parse(JSON.stringify(tree.cols[cid]))
      Object.assign(c, patch, { 'x-apirunner': { ...(c['x-apirunner'] ?? {}), description: f.description } })
      await put(`/api/collections/${cid}`, c)
      await tree.reloadCollection(cid)
    }
    tabs.markSaved(props.tab.id, { title: props.tab.title })
    showToast('Saqlandi', 'success')
    if (hasRealAuth(newPm) && !sameAuth(oldPm, newPm)) {                // auth endi qo'yildi/o'zgardi: ichidagi o'z auth'i borlar haqida taklif
      const cands = overridableRequests(cid, isFolder ? fid : null, newPm)
      if (cands.length) bulk.value = { label: name.value, candidates: cands, newAuth: newPm }
    }
  } catch (e: any) { showToast(e.message, 'error') }
}
</script>

<template>
  <div v-if="form" class="page" :data-testid="isFolder ? 'tab-folder' : 'tab-collection'">
    <div class="crumbs" style="padding:0 0 8px" data-testid="node-crumbs"><template v-for="(c, i) in crumbs" :key="i"><span v-if="i">/</span><span :class="{ cur: i === crumbs.length - 1 }">{{ c }}</span></template>
      <span style="flex:1" />
      <span class="badge" data-testid="node-kind">{{ isFolder ? 'Papka' : 'Collection' }}</span></div>
    <div style="display:flex;gap:10px;align-items:center">
      <h3 style="flex:1;margin:0" data-testid="node-title"><InlineName v-model:editing="renamingTitle" testid="node-rename" :value="name" :validate="v => validateName(cid, isFolder ? fid : null, v)" :commit="v => renameNode(cid, isFolder ? fid : null, v)" :label="isFolder ? 'Papka nomi' : 'Collection nomi'" /></h3>
      <button data-testid="scope-run-header" :disabled="!reqs.length" @click="tabs.open('runner', props.tab.ref!, 'Runner: ' + name, { permanent: true })"><Icon name="play" :size="14" />{{ isFolder ? 'Papkani' : "Collection'ni" }} ishga tushirish</button>
      <button class="primary" data-testid="scope-save" :disabled="!tab.dirty" @click="save">Saqlash</button>
    </div>
    <div class="sections" data-testid="scope-sections" role="tablist" aria-label="Bo'limlar" style="margin:8px 0 0">
      <button v-for="s in (['overview', 'auth', 'vars', 'scripts', 'run'] as const)" :key="s" role="tab" :aria-selected="section === s" :class="{ on: section === s }" :data-scope-section="s" @click="section = s">
        {{ { overview: 'Overview', auth: 'Auth', vars: 'Variables', scripts: 'Scripts', run: 'Run' }[s] }}
        <span v-if="s === 'auth' && form.auth.type !== 'inherit' && form.auth.type !== 'none'" class="dot-mark" aria-label="auth bor" />
        <span v-if="s === 'vars' && form.vars.filter(v => v.key).length" class="badge">{{ form.vars.filter(v => v.key).length }}</span>
        <span v-if="s === 'scripts' && (form.scripts.pre.trim() || form.scripts.test.trim())" class="dot-mark" aria-label="skript bor" />
      </button>
    </div>
    <div style="padding-top:12px">
      <div v-if="section === 'overview'" class="ov" data-testid="node-overview">
        <div class="ov-main">
          <section class="ov-card">
            <label class="lbl" for="node-desc">Tavsif (Markdown)</label>
            <textarea id="node-desc" v-model="form.description" data-testid="scope-desc" placeholder="Bu collection/papka nima uchun…" rows="3" @input="touch" />
          </section>
          <section class="ov-card" style="padding:0;overflow:hidden" data-testid="ov-table">
            <div class="ov-head"><span class="lbl" style="flex:1">So'rovlar · <span data-testid="ov-requests">{{ reqs.length }}</span><template v-if="folderCount"> · papkalar <span data-testid="ov-folders">{{ folderCount }}</span></template></span>
              <input v-model="filter" aria-label="So'rovlarni filtrlash" placeholder="Filtr…" data-testid="ov-filter"></div>
            <div class="ov-tr ov-th"><span>Metod</span><span>Nomi</span><span>Auth</span><span>Oxirgi</span><span style="text-align:right">Vaqt</span></div>
            <button v-for="r in shownRows" :key="r.id" class="ov-tr ov-row" data-testid="ov-row" :title="r.path + r.name" @click="openRequest(cid, r.id, true)">
              <span class="m" :class="'m-' + r.method">{{ r.method }}</span>
              <span class="ov-name"><span class="muted">{{ r.path }}</span>{{ r.name }}</span>
              <span class="ov-auth" :class="{ own: r.own }" data-testid="ov-row-auth">{{ r.auth }}</span>
              <span><span v-if="r.status !== undefined" class="status-pill" :class="r.ok ? 'ok' : 'err'" data-testid="ov-row-status">{{ r.status }}</span><span v-else class="muted">—</span></span>
              <span class="ov-time">{{ r.time }}</span>
            </button>
            <div v-if="!shownRows.length" class="empty" style="padding:16px" data-testid="ov-empty">{{ reqs.length ? "Filtr bo'yicha so'rov yo'q" : "Bu yerda hali so'rov yo'q" }}</div>
          </section>
        </div>
        <aside class="ov-side">
          <section class="ov-card" data-testid="ov-auth-card">
            <div class="lbl">Avtorizatsiya</div>
            <button class="ov-authline" data-testid="ov-auth" @click="section = 'auth'"><span class="pill">{{ authSummary.text }}</span></button>
            <div class="ov-bar" role="img" :aria-label="`${inheritCount} ta meros, ${ownAuthRequests} ta o'z auth'i`"><div :style="{ width: (reqs.length ? inheritCount / reqs.length * 100 : 0) + '%' }" /><div class="own" :style="{ width: (reqs.length ? ownAuthRequests / reqs.length * 100 : 0) + '%' }" /></div>
            <div class="ov-stats"><span data-testid="ov-inherit">{{ inheritCount }} ta so'rov meros oladi</span><span>{{ ownAuthRequests }} tasida o'z auth'i</span></div>
            <p v-if="ownAuthRequests" class="muted" style="font-size:12.5px;margin:8px 0 0" data-testid="ov-own-auth">{{ ownAuthRequests }} ta so'rovning o'z auth'i bor (daraxtda 🔒 belgisi bilan ko'rinadi).</p>
            <div v-if="sameTokenCount" class="ov-warn" data-testid="ov-same-token">{{ sameTokenCount }} ta so'rovda shu {{ isFolder ? 'papkadagi' : 'collection\'dagi' }} bilan bir xil token qo'lda yozilgan.</div>
            <button v-if="hasRealAuth(node?.auth) && ownAuthRequests" class="ov-wide" data-testid="ov-to-inherit" @click="offerInherit">Ularni Meros'ga o'tkazish…</button>
          </section>
          <section class="ov-card ov-two">
            <button class="ov-stat" data-testid="ov-vars" @click="section = 'vars'"><div class="lbl">O'zgaruvchilar</div><div class="v">{{ form.vars.filter(v => v.key).length }}</div></button>
            <button class="ov-stat" data-testid="ov-scripts" @click="section = 'scripts'"><div class="lbl">Skriptlar</div><div class="v2">{{ scriptKinds || "yo'q" }}</div></button>
          </section>
          <section class="ov-card" data-testid="ov-lastrun">
            <div class="lbl">Oxirgi run</div>
            <template v-if="lastRun">
              <div class="ov-lr"><b data-testid="ov-lr-ok">{{ lastRunOk }}</b><span class="muted">/ {{ lastRun.items.length }} o'tdi</span><span class="muted" style="margin-left:auto;font-size:12px">{{ lastRunWhen }}</span></div>
              <div class="ov-dots" data-testid="ov-dots"><span v-for="(it, i) in lastRun.items" :key="i" class="dot" :class="isOkStatus(it.status) ? 'ok' : 'err'" :title="`${nameOf(it.id)}: ${isOkStatus(it.status) ? 'o\'tdi' : 'xato (' + it.status + ')'}`" /></div>
            </template>
            <p v-else class="muted" style="margin:8px 0 0;font-size:12.5px" data-testid="ov-lr-none">Hali ishga tushirilmagan.</p>
            <button class="linkbtn" style="margin-top:6px" data-testid="ov-history" @click="sidePanel = 'history'">Run tarixi →</button>
          </section>
        </aside>
      </div>
      <AuthEditor v-else-if="section === 'auth'" :auth="form.auth" :allow-inherit="isFolder" :scope-ref="props.tab.ref" :source="parentSrc" @change="touch" />
      <VarsTable v-else-if="section === 'vars'" :rows="form.vars" testid="scope-vars" @change="touch" />
      <ScriptsPanel v-else-if="section === 'scripts'" :scripts="form.scripts" :scope="isFolder ? 'folder' : 'collection'" :scope-id="isFolder ? fid : cid" :errors="lastErrors" :goto="tab.state?.scriptGoto" @change="touch" />
      <div v-else data-testid="node-run">
        <p class="muted">«{{ name }}» ichidagi <b>{{ reqs.length }}</b> ta so'rovni ketma-ket yoki CSV/JSON ma'lumotlari bilan bir necha marta ishga tushiring.</p>
        <button class="primary" data-testid="scope-run-open" :disabled="!reqs.length" @click="tabs.open('runner', props.tab.ref!, 'Runner: ' + name, { permanent: true })">Runner'ni ochish</button>
      </div>
    </div>
    <BulkAuthDialog v-if="bulk" :cid="cid" :label="bulk.label" :scope-label="isFolder ? 'papka' : 'collection'" :candidates="bulk.candidates" :new-auth="bulk.newAuth" @close="bulk = null" />
  </div>
  <div v-else class="empty">Topilmadi</div>
</template>
