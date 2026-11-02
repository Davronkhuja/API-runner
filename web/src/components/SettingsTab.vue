<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get, post } from '../api/client'
import { askConfirm, showToast } from '../lib/ui'
import { useWorkspace } from '../stores/workspace'
import SettingsForm from './SettingsForm.vue'
import type { ReqSettings } from '../lib/settings'

interface Backup { name: string; version: string | null; created: number | null; suffix: string; has_saved_requests: boolean }
const backups = ref<Backup[]>([])
const status = ref<any>(null)
const busy = ref(false)

async function load() {
  backups.value = await get('/api/backups')
  status.value = await get('/api/status')
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
const gs = ref<ReqSettings>({ ...ws.settings })
const gsDirty = ref(false)
async function saveGlobal() { try { await ws.saveSettings(gs.value); gsDirty.value = false; showToast('Sozlamalar saqlandi', 'success') } catch (e: any) { showToast(e.message, 'error') } }
onMounted(load)
</script>

<template>
  <div class="editor" data-testid="settings-tab">
    <h3 style="margin-top:0">Sozlamalar</h3>
    <div class="muted" data-testid="settings-status" v-if="status">Versiya {{ status.version }} · sxema {{ status.schemaVersion }}</div>
    <h4>So'rov sozlamalari (global)</h4>
    <p class="muted">Barcha so'rovlar uchun sukut; har bir so'rov o'z Sozlamalar tabida qayta belgilashi mumkin.</p>
    <SettingsForm :model="gs" prefix="gset" @change="gsDirty = true" />
    <p><button class="primary" data-testid="gset-save" :disabled="!gsDirty" @click="saveGlobal">Saqlash</button></p>
    <h4>Zaxiralar</h4>
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
</template>
