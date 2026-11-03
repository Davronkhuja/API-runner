<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { get } from '../api/client'
import { useTabs } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'

const tabs = useTabs(), ws = useWorkspace()
const online = ref(true)
const backup = ref('')
let timer: ReturnType<typeof setInterval> | undefined

async function poll() {
  try {
    await get('/api/version')
    online.value = true
    const b = await get('/api/backups')
    const t = b[0]?.created
    backup.value = t ? new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
  } catch { online.value = false }
}
onMounted(() => { poll(); timer = setInterval(poll, 20000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <footer class="statusbar" data-testid="statusbar">
    <span role="status" style="display:flex;align-items:center;gap:6px" data-testid="server-status"><span class="dot" :class="{ off: !online }" />{{ online ? 'Server ulangan' : 'Server bilan aloqa yo\'q' }}</span>
    <button disabled title="Console — skriptlar bilan birga (Bosqich 3)" data-testid="console-btn">Console</button>
    <button data-testid="cookies-btn" title="Cookie Manager" @click="tabs.open('cookies', 'cookies', 'Cookie\'lar', { permanent: true })">Cookie'lar</button>
    <span style="flex:1" />
    <span v-if="backup" data-testid="backup-time">Avtomatik zaxira: {{ backup }}</span>
    <span data-testid="version">v{{ ws.version }}</span>
  </footer>
</template>
