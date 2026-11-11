<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get, post } from '../api/client'
import { askConfirm, fmtBytes, importOpen, showToast, wsExportOpen } from '../lib/ui'
import { downloadFrom } from '../lib/exporter'
import { useWorkspace } from '../stores/workspace'
import SettingsForm from './SettingsForm.vue'
import { dense, layout } from '../lib/view'
import Icon from './Icon.vue'
import StateBlock from './StateBlock.vue'
import { exportLegacy, importLocalStorage } from '../lib/migrate'
import type { ReqSettings } from '../lib/settings'

interface Backup { name: string; version: string | null; created: number | null; suffix: string; has_saved_requests: boolean }
const backups = ref<Backup[]>([])
const status = ref<any>(null)
const busy = ref(false)

const fstat = ref<{ count: number; size: number; unused_count: number; unused_size: number } | null>(null)
async function loadFiles() { try { fstat.value = await get('/api/files/usage') } catch { fstat.value = null } }
async function cleanFiles() {
  const u = fstat.value
  if (!u?.unused_count || !(await askConfirm(`${u.unused_count} ta ishlatilmayotgan fayl (${fmtBytes(u.unused_size)}) o'chiriladi. Hech bir so'rov, muhit yoki ochiq tab ularga havola qilmaydi. Davom etilsinmi?`, "Tozalash"))) return
  try { const r = await post('/api/files/cleanup'); showToast(`${r.removed} ta fayl o'chirildi (${fmtBytes(r.freed)})`, 'success'); await loadFiles() }
  catch (e: any) { showToast(e.message, 'error') }
}
const loadErr = ref('')
async function load() {
  loadFiles()
  try { backups.value = await get('/api/backups'); status.value = await get('/api/status'); loadErr.value = '' } catch (e: any) { loadErr.value = e.message || 'Server javob bermadi' }
}
async function create() {
  busy.value = true
  try { const r = await post('/api/backups'); showToast(`Zaxira yaratildi: ${r.name}`, 'success'); await load() }
  catch (e: any) { showToast(e.message, 'error') } finally { busy.value = false }
}
async function restore(b: Backup) {
  if (!(await askConfirm(`"${b.name}" zaxirasidan tiklansinmi? Joriy holat avval alohida zaxiraga olinadi.`, 'Tiklash'))) return
  busy.value = true
  try {
    const r = await post('/api/backups/restore', { name: b.name })
    showToast(`Tiklandi. Oldingi holat: ${r.pre_restore}`, 'success')
    setTimeout(() => location.reload(), 600)
  } catch (e: any) { showToast(e.message, 'error'); busy.value = false }
}
const fmt = (t: number | null) => (t ? new Date(t * 1000).toLocaleString() : '—')
const ws = useWorkspace()
const sf = ref({ hosts: ws.safety.test_hosts.join('\n'), host_confirm: ws.safety.host_confirm, dev_runner_writes: ws.safety.dev_runner_writes }), sfSaved = ref(false)
async function saveSafetyNow() {
  try {
    await ws.saveSafety({ test_hosts: sf.value.hosts.split(/[\n,]+/).map(x => x.trim()).filter(Boolean), host_confirm: sf.value.host_confirm, dev_runner_writes: sf.value.dev_runner_writes })
    sf.value.hosts = ws.safety.test_hosts.join('\n'); sfSaved.value = true
  } catch (e: any) { showToast(e.message, 'error') }
}

const lim = ref({ ...ws.scripts.limits })
const limDirty = ref(false)
const limSaved = ref(false)
let limTimer: ReturnType<typeof setTimeout> | undefined
function queueLimits() { limDirty.value = true; limSaved.value = false; clearTimeout(limTimer); limTimer = setTimeout(saveLimits, 600) }
async function saveLimits() { try { await ws.saveScriptLimits(lim.value); lim.value = { ...ws.scripts.limits }; limDirty.value = false; limSaved.value = true } catch (e: any) { showToast(e.message, 'error') } }
function resetLimits() { lim.value = { ...ws.scripts.defaults }; queueLimits() }
const copyCmd = () => { navigator.clipboard?.writeText(ws.scripts.install); showToast('Nusxalandi', 'success') }
const gs = ref<ReqSettings>({ ...ws.settings })
const gsDirty = ref(false)
const gsSaved = ref(false)
let gsTimer: ReturnType<typeof setTimeout> | undefined
async function saveGlobal() { try { await ws.saveSettings(gs.value); gsDirty.value = false; gsSaved.value = true } catch (e: any) { showToast(e.message, 'error') } }
function queueGlobal() { gsDirty.value = true; gsSaved.value = false; clearTimeout(gsTimer); gsTimer = setTimeout(saveGlobal, 500) }
const NAV = [['s-view', "Ko'rinish"], ['s-request', "So'rov"], ['s-safety', 'Xavfsizlik'], ['s-scripts', 'Skriptlar'], ['s-files', 'Fayllar'], ['s-data', "Ma'lumotlar"], ['s-io', 'Import / Eksport'], ['s-backups', 'Zaxiralar']] as const
const sec = ref<string>('s-view'), mainEl = ref<HTMLElement>()
function go(id: string) { sec.value = id; mainEl.value?.querySelector('#' + id)?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }
onMounted(load)
</script>

<template>
  <div class="page settings-layout" data-testid="settings-tab">
    <nav class="settings-nav" aria-label="Sozlamalar bo'limlari" data-testid="settings-nav">
      <b>Sozlamalar</b>
      <button v-for="n in NAV" :key="n[0]" :class="{ on: sec === n[0] }" :data-nav="n[0]" @click="go(n[0])">{{ n[1] }}</button>
    </nav>
    <div class="settings-main" ref="mainEl">
      <StateBlock v-if="loadErr" kind="error" :text="`Zaxira va holat ma'lumotlarini o'qib bo'lmadi: ${loadErr}`" testid="settings-load-error" @retry="load" />
    <div class="muted" data-testid="settings-status" v-if="status">Versiya {{ status.version }} · sxema {{ status.schemaVersion }}</div>
    <h4 id="s-view">Ko'rinish</h4>
    <div class="view-opts" data-testid="view-settings">
      <div role="radiogroup" aria-label="So'rov va javob joylashuvi" class="view-radio">
        <span class="lbl">So'rov va javob</span>
        <label><input v-model="layout" type="radio" value="stack" data-testid="view-stack">Ustma-ust</label>
        <label><input v-model="layout" type="radio" value="side" data-testid="view-side">Yonma-yon</label>
      </div>
      <label class="view-dense"><input v-model="dense" type="checkbox" data-testid="view-dense"><span><b>Zich rejim</b><br><span class="muted">Kichikroq qator balandligi — ekranga ko'proq qator sig'adi.</span></span></label>
    </div>
    <h4 id="s-request">So'rov sozlamalari (global)</h4>
    <p class="muted">Barcha so'rovlar uchun sukut; har bir so'rov o'z Sozlamalar tabida qayta belgilashi mumkin.</p>
    <SettingsForm :model="gs" prefix="gset" @change="queueGlobal" />
    <p class="saved-note" role="status" data-testid="gset-saved"><template v-if="gsDirty">Saqlanmoqda…</template><template v-else-if="gsSaved">✓ Saqlandi</template><template v-else>O'zgarishlar avtomatik saqlanadi</template></p>
    <h4 id="s-safety">Xavfsizlik (Runner va yuborish)</h4>
    <p class="muted" style="max-width:720px">Himoya so'rovning <b>o'ziga</b> qaraydi: Runner sukut bo'yicha faqat GET/HEAD/OPTIONS ni belgilaydi; POST/PUT/PATCH/DELETE tanlansa har doim tasdiq dialogi chiqadi. <code>localhost</code>, <code>127.0.0.1</code>, <code>*.local</code>, <code>*.test</code> va quyidagi ro'yxat «test/dev host» hisoblanadi; boshqa har qanday host (hujjat.uz, api.… ) xavfli.</p>
    <label class="bf" style="max-width:520px"><span class="bl">Test/dev host'lar (har qatorda bittadan; <code>*.staging.company.uz</code> ham mumkin)</span>
      <textarea v-model="sf.hosts" rows="4" spellcheck="false" data-testid="safety-hosts" aria-label="Test host'lar" @change="saveSafetyNow" /></label>
    <label style="display:flex;gap:8px;align-items:center;margin:8px 0"><input type="checkbox" v-model="sf.host_confirm" data-testid="safety-host-confirm" @change="saveSafetyNow"> Yozuvchi so'rovni test/dev bo'lmagan host'ga yuborishda tasdiq so'rash (muhit sozlamasiga qo'shimcha)</label>
    <label style="display:flex;gap:8px;align-items:center;margin:8px 0"><input type="checkbox" v-model="sf.dev_runner_writes" data-testid="safety-dev-writes" @change="saveSafetyNow"> Dev/Test muhitda Runner hamma metodlarni belgilangan holda ochsin (tasdiq dialogi baribir chiqadi)</label>
    <p class="saved-note" role="status" data-testid="safety-saved"><template v-if="sfSaved">✓ Saqlandi</template><template v-else>O'zgarishlar avtomatik saqlanadi.</template></p>
    <h4 id="s-scripts">Skriptlar</h4>
    <p v-if="ws.scripts.available" class="muted" data-testid="script-status">Pre-request va Tests skriptlari yoqilgan (<code>quickjs-ng {{ ws.scripts.version }}</code>). Skriptlar fayl tizimi va tarmoqqa (<code>pm.sendRequest</code> dan tashqari) kira olmaydi; workspace'ni faqat <code>pm.environment/globals/collectionVariables</code> orqali o'zgartiradi.</p>
    <div v-else class="script-off" role="alert" data-testid="script-status"><b>Skriptlar o'chiq:</b> <code>quickjs-ng</code> o'rnatilmagan. Skript tablari ko'rinadi va matn saqlanadi, lekin bajarilmaydi. O'rnatish:
      <div style="margin-top:6px;display:flex;gap:8px;align-items:center"><code data-testid="script-install-cmd">{{ ws.scripts.install }}</code><button class="sm" @click="copyCmd">Nusxa</button></div></div>
    <table class="kv" style="max-width:720px" data-testid="script-limits"><tbody>
      <tr><td style="width:260px" class="muted">Skript vaqt chegarasi (ms)</td><td><input type="number" min="100" max="300000" step="100" v-model.number="lim.timeout_ms" data-testid="script-limit-timeout" aria-label="Skript vaqt chegarasi, ms" @input="queueLimits"></td></tr>
      <tr><td class="muted">Xotira chegarasi (MB)</td><td><input type="number" min="8" max="1024" v-model.number="lim.memory_mb" data-testid="script-limit-memory" aria-label="Skript xotira chegarasi, MB" @input="queueLimits"></td></tr>
      <tr><td class="muted">pm.sendRequest soni (bir bajarishda)</td><td><input type="number" min="0" max="200" v-model.number="lim.max_requests" data-testid="script-limit-requests" aria-label="pm.sendRequest soni" @input="queueLimits"></td></tr>
    </tbody></table>
    <p class="muted" style="font-size:var(--fs-sm)">Chegaradan oshgan skript to'xtatiladi, xato Testlar tabida va Console'da ko'rinadi; so'rov baribir yuboriladi. Sukut: {{ ws.scripts.defaults.timeout_ms }} ms · {{ ws.scripts.defaults.memory_mb }} MB · {{ ws.scripts.defaults.max_requests }} so'rov.</p>
    <p style="display:flex;gap:10px;align-items:center"><button data-testid="script-limits-reset" @click="resetLimits">Sukutga qaytarish</button><span class="saved-note" role="status" data-testid="limits-saved"><template v-if="limDirty">Saqlanmoqda…</template><template v-else-if="limSaved">✓ Saqlandi</template><template v-else>Avtomatik saqlanadi</template></span></p>
    <h4 id="s-files">Fayllar</h4>
    <p class="muted">So'rovlarga biriktirilgan fayllar workspace ichida (<code>workspace/files</code>) saqlanadi — saqlangan so'rov keyin ham ishlaydi. Hech narsa havola qilmayotgan fayllarni shu yerda tozalash mumkin (yangi yuklanganlar 1 soat tegilmaydi).</p>
    <p data-testid="files-usage" v-if="fstat">Jami: <b data-testid="files-count">{{ fstat.count }}</b> ta, {{ fmtBytes(fstat.size) }} · ishlatilmayotgani: <b data-testid="files-unused">{{ fstat.unused_count }}</b> ta ({{ fmtBytes(fstat.unused_size) }})
      <button data-testid="files-cleanup" :disabled="!fstat.unused_count" @click="cleanFiles">Ishlatilmaganlarni tozalash</button></p>
    <h4 id="s-data">Ma'lumotlar</h4>
    <p class="muted">Eski brauzer (localStorage) ma'lumotlarini serverga ko'chirish yoki <code>saved_requests.json</code> formatiga eksport (orqaga qaytish uchun).</p>
    <p style="display:flex;gap:8px"><button data-testid="ls-import" @click="importLocalStorage"><Icon name="upload" :size="14" />Brauzerdan ko'chirish</button><button data-testid="export-legacy" @click="exportLegacy"><Icon name="download" :size="14" />saved_requests.json eksport</button></p>
    <h4 id="s-io">Import / Eksport</h4>
    <p class="muted" style="margin:0 0 8px">Postman, OpenAPI/Swagger, Insomnia, HAR, cURL va workspace zaxirasini import qiling; butun workspace'ni zip qilib oling.</p>
    <p style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <button data-testid="io-import" @click="importOpen = true"><Icon name="upload" :size="14" />Import…</button>
      <button data-testid="io-workspace-zip" @click="wsExportOpen = true"><Icon name="download" :size="14" />Workspace zaxirasi (.zip)…</button>
      <button data-testid="io-globals" @click="downloadFrom('/api/globals/export')"><Icon name="download" :size="14" />Globals (Postman)</button>
    </p>
    <p class="muted" style="font-size:var(--fs-sm)">Zip zaxirasi sukut bo'yicha maxfiy va Current qiymatlarsiz; ularni qo'shish va parol bilan shifrlash eksport oynasida. Avtomatik zaxiralar (Zaxiralar bo'limi) esa lokal va to'liq.</p>
    <h4 id="s-backups">Zaxiralar</h4>
    <p class="muted">Har bir migratsiyadan oldin avtomatik zaxira olinadi. Oxirgi 20 tasi saqlanadi. <code>saved_requests.json</code> tiklashda tegilmaydi.</p>
    <p><button class="primary" data-testid="backup-create" :disabled="busy" @click="create">Zaxira yaratish</button></p>
    <table class="kv" data-testid="backup-table">
      <thead><tr><th style="text-align:left">Nomi</th><th style="text-align:left">Sana</th><th style="text-align:left">Versiya</th><th /></tr></thead>
      <tbody>
        <tr v-for="b in backups" :key="b.name" data-testid="backup-row" :data-name="b.name">
          <td><code>{{ b.name }}</code></td><td>{{ fmt(b.created) }}</td><td>{{ b.version }}{{ b.suffix ? ' · ' + b.suffix : '' }}</td>
          <td style="text-align:right"><button data-testid="backup-restore" :disabled="busy" @click="restore(b)">Tiklash</button></td>
        </tr>
      </tbody>
    </table>
    <div v-if="!backups.length" class="empty" data-testid="backup-empty">Hali zaxira yo'q</div>
    </div>
  </div>
</template>
