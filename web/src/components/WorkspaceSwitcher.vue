<script setup lang="ts">
/** Header'dagi workspace almashtirgich: ro'yxat, almashtirish, yaratish, nomlash, o'chirish (Savatga). */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Dialog from './Dialog.vue'
import Icon from './Icon.vue'
import { ApiError, del, get, post, put } from '../api/client'
import { askConfirm, showToast } from '../lib/ui'
import { useTabs } from '../stores/tabs'

interface W { id: string; name: string; default: boolean; active: boolean }
const items = ref<W[]>([]), open = ref(false), root = ref<HTMLElement>()
const dlg = ref<{ mode: 'create' | 'rename'; id?: string; name: string; err: string } | null>(null)
const tabs = useTabs()
const active = () => items.value.find(w => w.active)
async function load() { try { items.value = (await get('/api/workspaces')).items } catch { /* server yo'q */ } }
onMounted(() => { load(); document.addEventListener('pointerdown', onDoc) })
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDoc))
function onDoc(e: Event) { if (open.value && !root.value?.contains(e.target as Node)) open.value = false }
async function toggle() { if (!open.value) await load(); open.value = !open.value }

async function switchTo(w: W, force = false) {
  open.value = false
  if (w.active) return
  try {
    await tabs.flush()
    await post(`/api/workspaces/${w.id}/activate`, force ? { force: true } : {})
    location.reload()                                              // hamma holat (daraxt, tablar, tarix, muhit) yangi workspace'dan
  } catch (e: any) {
    if (e instanceof ApiError && e.status === 409) {
      if (await askConfirm("Faol run, mock server yoki WebSocket/SSE ulanishlari bor — almashtirsangiz ular to'xtatiladi. Davom etilsinmi?", "To'xtatib, almashtirish")) await switchTo(w, true)
    } else showToast(e.message, 'error')
  }
}
function newDlg() { open.value = false; dlg.value = { mode: 'create', name: '', err: '' } }
function renameDlg(w: W) { open.value = false; dlg.value = { mode: 'rename', id: w.id, name: w.name, err: '' } }
async function submit() {
  const d = dlg.value!
  try {
    if (d.mode === 'create') { const r = await post('/api/workspaces', { name: d.name }); const w = { id: r.id, name: d.name.trim(), default: false, active: false }; dlg.value = null; await switchTo(w) }
    else { await put(`/api/workspaces/${d.id}`, { name: d.name }); dlg.value = null; await load(); showToast('Nom o\'zgartirildi', 'success') }
  } catch (e: any) { d.err = e.message }
}
async function remove(w: W) {
  open.value = false
  if (!(await askConfirm(`«${w.name}» workspace'i Savatga o'tkazilsinmi? Ichidagi hamma narsa (collection, muhit, tarix) 30 kun saqlanadi va Savatdan tiklanadi.`, "Savatga o'tkazish"))) return
  try { await del(`/api/workspaces/${w.id}`); showToast(`«${w.name}» Savatga o'tkazildi`, 'success'); await load() } catch (e: any) { showToast(e.message, 'error') }
}
</script>

<template>
  <div ref="root" class="ws-switch" @keydown.esc="open = false">
    <button class="ws-btn" data-testid="ws-switch" aria-haspopup="menu" :aria-expanded="open" title="Workspace'ni almashtirish" @click="toggle">{{ active()?.name ?? 'Shaxsiy workspace' }}<Icon name="chevron-down" :size="14" /></button>
    <div v-if="open" class="menu ws-menu" role="menu" aria-label="Workspace'lar" data-testid="ws-menu">
      <div v-for="w in items" :key="w.id" class="ws-row" :class="{ on: w.active }" data-testid="ws-item" :data-name="w.name">
        <button role="menuitemradio" :aria-checked="w.active" class="ws-pick" data-testid="ws-pick" @click="switchTo(w)"><span class="ws-chk" aria-hidden="true">{{ w.active ? '✓' : '' }}</span><span class="ws-name">{{ w.name }}</span></button>
        <button class="ib" :aria-label="`${w.name} nomini o'zgartirish`" title="Nomini o'zgartirish" data-testid="ws-rename" @click="renameDlg(w)">✎</button>
        <button v-if="!w.default && !w.active" class="ib" :aria-label="`${w.name} ni o'chirish`" title="Savatga" data-testid="ws-delete" @click="remove(w)"><Icon name="trash" :size="14" /></button>
      </div>
      <button role="menuitem" class="ws-new" data-testid="ws-new" @click="newDlg"><Icon name="plus" :size="14" />Yangi workspace</button>
    </div>
    <Dialog v-if="dlg" :title="dlg.mode === 'create' ? 'Yangi workspace' : 'Workspace nomi'" testid="ws-dialog" width="420px" @close="dlg = null">
      <label class="dlg-field"><span>Nomi</span><input v-model="dlg.name" style="width:100%" maxlength="60" data-testid="ws-name" data-autofocus @keydown.enter="submit"></label>
      <p v-if="dlg.mode === 'create'" class="muted" style="margin:0;font-size:var(--fs-sm)">Yangi workspace bo'sh va alohida papkada: o'z collection'lari, muhitlari, tarixi va run natijalari bo'ladi. Yaratilgach unga o'tiladi.</p>
      <p v-if="dlg.err" class="state-error" role="alert" data-testid="ws-error" style="margin:8px 0 0;padding:6px 10px">{{ dlg.err }}</p>
      <template #footer><button @click="dlg = null">Bekor qilish</button><button class="primary" data-testid="ws-ok" :disabled="!dlg.name.trim()" @click="submit">{{ dlg.mode === 'create' ? 'Yaratish' : 'Saqlash' }}</button></template>
    </Dialog>
  </div>
</template>
