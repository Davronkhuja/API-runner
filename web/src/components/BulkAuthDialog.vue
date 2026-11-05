<script setup lang="ts">
import Dialog from './Dialog.vue'
/** Papka/collection'ga auth qo'yilgach: ichidagi o'z auth'i bor so'rovlarni "Meros"ga o'tkazishni taklif qiladi (zaxira bilan). */
import { computed, ref } from 'vue'
import { post } from '../api/client'
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { emptyAuth } from '../lib/auth'
import { authName } from '../lib/nodes'
import { showToast } from '../lib/ui'

export interface Candidate { id: string; name: string; path: string; auth: any; same: boolean; noauth: boolean }
const props = defineProps<{ cid: string; label: string; scopeLabel: string; candidates: Candidate[]; newAuth: any }>()
const emit = defineEmits<{ close: [] }>()
const tree = useTree(), tabs = useTabs()
const checked = ref<Record<string, boolean>>(Object.fromEntries(props.candidates.map(c => [c.id, c.same && !c.noauth])))   // bir xil tokenlilar avtomatik tanlanadi
const sameCount = computed(() => props.candidates.filter(c => c.same).length)
const picked = computed(() => props.candidates.filter(c => checked.value[c.id]))
const busy = ref(false)
const setAll = (v: boolean) => props.candidates.forEach(c => { checked.value[c.id] = v })

async function apply() {
  if (!picked.value.length) return emit('close')
  busy.value = true
  try {
    const r = await post(`/api/collections/${props.cid}/inherit-auth`, { ids: picked.value.map(c => c.id) })
    await tree.reloadCollection(props.cid)
    for (const t of tabs.tabs) {                                    // ochiq tablardagi qoralamalar ham "Meros"ga o'tadi
      const id = t.ref?.split(':')[1]
      if (t.kind === 'request' && t.draft && t.ref?.startsWith(props.cid + ':') && id && picked.value.some(c => c.id === id)) t.draft.auth = emptyAuth('inherit')
    }
    showToast(`${r.changed} ta so'rov «Meros»ga o'tkazildi · zaxira: ${r.backup}`, 'success', 6000)
    emit('close')
  } catch (e: any) { showToast(e.message, 'error') } finally { busy.value = false }
}
</script>

<template>
  <Dialog :title="`«${label}» ${scopeLabel}ga auth qo'yildi: ${authName(newAuth)}`" testid="bulk-auth-dialog" width="min(720px,92vw)" @close="emit('close')">
            <p style="margin:8px 0">Ichidagi <b data-testid="bulk-auth-count">{{ candidates.length }}</b> ta so'rovning o'z auth'i bor, shuning uchun bu auth ularga ta'sir qilmaydi. Ularni <b>«Meros»</b>ga o'tkazaymi?
        <template v-if="sameCount"> <span class="muted">{{ sameCount }} tasida token/sozlama aynan shu bilan bir xil (ko'chirishdan qolgan) — ular avtomatik tanlandi.</span></template></p>
      <div class="scroll panel-box" style="overflow:auto;padding:4px;max-height:44vh" role="list">
        <label v-for="c in candidates" :key="c.id" class="row" style="height:auto;min-height:34px;padding:4px 8px" role="listitem" data-testid="bulk-auth-row">
          <input v-model="checked[c.id]" type="checkbox" :aria-label="`${c.name} — Meros'ga o'tkazish`" data-testid="bulk-auth-check">
          <span class="name"><span class="muted">{{ c.path }}</span>{{ c.name }}</span>
          <span class="badge" data-testid="bulk-auth-type">{{ authName(c.auth) }}</span>
          <span v-if="c.same" class="badge" style="background:var(--ok-bg);color:var(--ok)" data-testid="bulk-auth-same">bir xil</span>
        </label>
      </div>
      <p class="muted" style="font-size:var(--fs-sm);margin:8px 0" data-testid="bulk-auth-backup-note">O'zgartirishdan oldin ish maydonining zaxira nusxasi avtomatik olinadi (Sozlamalar → Zaxiralar'dan tiklash mumkin). «Auth yo'q» deb belgilangan so'rovlar sukut bo'yicha tanlanmaydi.</p>
    <template #footer>
      <span style="display:flex;gap:6px;margin-right:auto"><button class="sm" data-testid="bulk-auth-all" @click="setAll(true)">Hammasini tanlash</button><button class="sm" data-testid="bulk-auth-none" @click="setAll(false)">Hech birini</button></span>
      <button data-testid="bulk-auth-skip" @click="emit('close')">O'zgarishsiz qoldirish</button>
      <button class="primary" data-testid="bulk-auth-apply" :disabled="busy || !picked.length" @click="apply">Meros'ga o'tkazish ({{ picked.length }})</button>
    </template>
  </Dialog>
</template>
