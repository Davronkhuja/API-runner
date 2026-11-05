<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { get } from '../api/client'
import { useTabs } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { checkVersion, hasNewBuild, isServerStale, NOT_MANAGED_HINT, reloadForNewBuild, restartServer, server, uiVersion } from '../lib/server'
import { consoleOpen, toggle as toggleConsole, unreadErrors } from '../lib/console'

const tabs = useTabs(), ws = useWorkspace()
const online = ref(true)
const backup = ref('')
const hint = NOT_MANAGED_HINT
const stale = computed(() => isServerStale())
const newBuild = computed(() => !stale.value && hasNewBuild())
let timer: ReturnType<typeof setInterval> | undefined, vtimer: ReturnType<typeof setInterval> | undefined

async function poll() {
  try {
    online.value = true
    const b = await get('/api/backups')
    const t = b[0]?.created
    backup.value = t ? new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
  } catch { online.value = false }
}
/** Versiya tekshiruvi (server eskirdimi / diskda yangi UI build bormi): har 60 soniyada va sahifa qayta fokus olganda. */
async function version() { try { ws.version = (await checkVersion()).version } catch { /* poll() holatni o'zi ko'rsatadi */ } }
const onVisible = () => { if (document.visibilityState === 'visible') version() }
onMounted(() => { poll(); version(); timer = setInterval(poll, 20000); vtimer = setInterval(version, 60000); document.addEventListener('visibilitychange', onVisible) })
onBeforeUnmount(() => { clearInterval(timer); clearInterval(vtimer); document.removeEventListener('visibilitychange', onVisible) })
</script>

<template>
  <footer class="statusbar" data-testid="statusbar">
    <span role="status" style="display:flex;align-items:center;gap:6px" data-testid="server-status"><span class="dot" :class="{ off: !online }" />{{ online ? 'Server ulangan' : 'Server bilan aloqa yo\'q' }}</span>
    <button :aria-pressed="consoleOpen" title="Console: so'rov/javob loglari, console.log va skript xatolari" data-testid="console-btn" @click="toggleConsole">Console<span v-if="unreadErrors" class="badge badge-err" data-testid="console-unread" style="margin-left:4px">{{ unreadErrors }}</span></button>
    <button data-testid="cookies-btn" title="Cookie Manager" @click="tabs.open('cookies', 'cookies', 'Cookie\'lar', { permanent: true })">Cookie'lar</button>
    <span v-if="stale" class="stale-warn" role="alert" data-testid="stale-server">⚠ Server eski (v{{ ws.version }}, UI v{{ uiVersion }})
      <button v-if="server.managed" class="primary" data-testid="restart-server" :disabled="server.restarting" @click="restartServer">Qayta ishga tushirish</button>
      <span v-else data-testid="restart-hint">— {{ hint }}</span></span>
    <span v-else-if="newBuild" class="new-build" role="status" data-testid="new-build">Yangi versiya tayyor (v{{ server.diskUi }}, sizda v{{ uiVersion }})
      <button class="primary" data-testid="reload-new-build" @click="reloadForNewBuild">Sahifani yangilash</button></span>
    <span style="flex:1" />
    <span v-if="backup" data-testid="backup-time">Avtomatik zaxira: {{ backup }}</span>
    <span data-testid="version">v{{ ws.version }}</span>
  </footer>
</template>
