<script setup lang="ts">
import { ref } from 'vue'
import { post as apiPost } from '../api/client'
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { cmdkOpen, showToast } from '../lib/ui'
import { theme, toggleTheme } from '../lib/theme'
import Icon from './Icon.vue'
import { isProd } from '../lib/envkind'

const tabs = useTabs(), tree = useTree(), ws = useWorkspace()
const importInput = ref<HTMLInputElement>()
async function onImportFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
  try { const r = await apiPost('/api/import', { content: await f.text() }); await tree.load(); showToast(`Import qilindi: ${r.name}`, 'success') } catch (err: any) { showToast(err.message, 'error') }
  ;(e.target as HTMLInputElement).value = ''
}
function openVars() {
  const e = ws.activeEnv
  if (e) tabs.open('environment', e.id, e.name, { permanent: true })
  else tabs.open('environment', 'globals', 'Globals', { permanent: true })
}
</script>

<template>
  <header class="header" data-testid="header">
    <div style="display:flex;align-items:center;gap:10px;min-width:200px">
      <div class="logo"><Icon name="bolt" :size="15" /></div>
      <span class="brand">API Runner</span>
      <span class="sep" aria-hidden="true">/</span>
      <span style="font-weight:500;font-size:12.5px;padding:0 6px">Shaxsiy workspace</span>
    </div>
    <div style="flex:1;display:flex;justify-content:center">
      <div class="search">
        <span class="ico"><Icon name="search" :size="16" /></span>
        <input readonly placeholder="So'rov, papka yoki o'zgaruvchini qidirish" aria-label="Hamma joydan qidirish (⌘K)" aria-haspopup="dialog" data-testid="cmdk-open" @click="cmdkOpen = true" @keydown.enter.prevent="cmdkOpen = true" @keydown.space.prevent="cmdkOpen = true">
        <span class="kbd" aria-hidden="true">⌘K</span>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:6px">
      <button aria-label="Import (Postman, OpenAPI)" title="Postman/OpenAPI import" data-testid="import-btn" @click="importInput?.click()"><Icon name="download" :size="15" />Import</button>
      <input ref="importInput" type="file" accept=".json" hidden data-testid="import-file" tabindex="-1" aria-hidden="true" @change="onImportFile">
      <label class="envsel"><span class="dot" :class="{ on: ws.activeEnvId }" aria-hidden="true" />
        <span v-if="ws.activeEnv?.kind" class="kind-dot" :class="'kind-' + ws.activeEnv.kind" aria-hidden="true" />
        <select :value="ws.activeEnvId ?? ''" data-testid="env-select" aria-label="Faol muhit" @change="ws.setActive(($event.target as HTMLSelectElement).value || null)">
          <option value="">Muhit yo'q</option><option v-for="e in ws.environments" :key="e.id" :value="e.id">{{ e.name }}</option>
        </select>
      </label>
      <span v-if="isProd(ws.activeEnv)" class="prod-badge" role="status" data-testid="prod-badge" :title="`Faol muhit: ${ws.activeEnv!.name} — Prod`"><Icon name="alert" :size="13" />PROD</span>
      <button class="ib" aria-label="Muhit o'zgaruvchilari" title="Muhit o'zgaruvchilari" data-testid="env-vars-btn" @click="openVars"><Icon name="eye" :size="17" /></button>
      <button class="ib" :aria-label="theme === 'dark' ? 'Yorug temaga o\'tish' : 'Qorong\'i temaga o\'tish'" :title="theme === 'dark' ? 'Yorug tema' : 'Qorong\'i tema'" data-testid="theme" @click="toggleTheme"><Icon :name="theme === 'dark' ? 'sun' : 'moon'" :size="17" /></button>
      <button class="ib" aria-label="Sozlamalar" title="Sozlamalar" data-testid="settings-btn" @click="tabs.open('settings', 'settings', 'Sozlamalar', { permanent: true })"><Icon name="settings" :size="17" /></button>
    </div>
  </header>
</template>
