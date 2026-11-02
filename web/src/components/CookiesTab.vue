<script setup lang="ts">
/** Cookie Manager: domenlar bo'yicha guruhlangan jar (server SQLite). */
import { computed, onMounted, ref } from 'vue'
import { del, get, post } from '../api/client'
import { askConfirm, showToast } from '../lib/ui'

interface Cookie { domain: string; path: string; name: string; value: string; expires: number | null; secure: number; httponly: number; host_only: number }
const all = ref<Cookie[]>([])
const form = ref({ domain: '', name: '', value: '', path: '/' })
const groups = computed(() => {
  const m = new Map<string, Cookie[]>()
  for (const c of all.value) m.set(c.domain, [...(m.get(c.domain) ?? []), c])
  return [...m.entries()]
})
let seq = 0
async function load() { const n = ++seq; const r = await get('/api/cookies'); if (n === seq) all.value = r }   // eskirgan javob yangisini bosmasin
async function add() {
  const payload = { ...form.value }
  form.value.name = ''; form.value.value = ''          // kutmasdan tozalanadi: keyingi yozuv oldingi javobga urilmasin
  try { await post('/api/cookies', payload); await load() } catch (e: any) { form.value.name = payload.name; form.value.value = payload.value; showToast(e.message, 'error') }
}
const q = (c: Cookie) => `domain=${encodeURIComponent(c.domain)}&path=${encodeURIComponent(c.path)}&name=${encodeURIComponent(c.name)}`
async function remove(c: Cookie) { await del(`/api/cookies?${q(c)}`); await load() }
async function removeDomain(d: string) { if (await askConfirm(`${d} cookie'lari o'chirilsinmi?`, 'O\'chirish')) { await del(`/api/cookies?domain=${encodeURIComponent(d)}`); await load() } }
async function clearAll() { if (await askConfirm('Barcha cookie\'lar o\'chirilsinmi?', 'Hammasini o\'chirish')) { await del('/api/cookies'); await load() } }
async function save(c: Cookie) { await post('/api/cookies', c); showToast('Saqlandi', 'success') }
const exp = (e: number | null) => (e ? new Date(e * 1000).toLocaleString() : 'sessiya')
onMounted(load)
</script>

<template>
  <div class="editor" data-testid="cookies-tab">
    <div style="display:flex;gap:10px;align-items:center">
      <h3 style="flex:1;margin:0">Cookie Manager</h3>
      <button data-testid="cookies-refresh" @click="load">⟳ Yangilash</button>
      <button data-testid="cookies-clear" :disabled="!all.length" @click="clearAll">Hammasini o'chirish</button>
    </div>
    <p class="muted">So'rovlarda olingan cookie'lar avtomatik saqlanadi va mos domenga yuboriladi. Cookie yuborishni so'rov Sozlamalarida o'chirish mumkin.</p>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0">
      <input v-model="form.domain" placeholder="domen (127.0.0.1)" data-testid="cookie-add-domain" style="width:160px">
      <input v-model="form.name" placeholder="nom" data-testid="cookie-add-name" style="width:130px">
      <input v-model="form.value" placeholder="qiymat" data-testid="cookie-add-value" style="width:160px">
      <input v-model="form.path" placeholder="yo'l" style="width:70px">
      <button class="primary" data-testid="cookie-add" @click="add">＋ Qo'shish</button>
    </div>
    <div v-for="[domain, cs] in groups" :key="domain" style="margin-top:14px" data-testid="cookie-domain" :data-domain="domain">
      <div style="display:flex;gap:8px;align-items:center"><b style="flex:1">{{ domain }}</b><span class="muted">{{ cs.length }} ta</span><button class="ghost" data-testid="cookie-domain-del" @click="removeDomain(domain)">Domenni o'chirish</button></div>
      <table class="kv"><tbody>
        <tr v-for="c in cs" :key="c.path + c.name" data-testid="cookie-row">
          <td style="width:150px"><b>{{ c.name }}</b></td>
          <td><input v-model="c.value" data-testid="cookie-value" style="width:100%" @change="save(c)"></td>
          <td class="muted" style="width:60px">{{ c.path }}</td>
          <td class="muted" style="width:150px">{{ exp(c.expires) }}</td>
          <td class="muted" style="width:90px">{{ c.httponly ? 'HttpOnly ' : '' }}{{ c.secure ? 'Secure' : '' }}</td>
          <td style="width:26px"><button class="ghost" data-testid="cookie-del" @click="remove(c)">×</button></td>
        </tr>
      </tbody></table>
    </div>
    <div v-if="!all.length" class="empty" data-testid="cookies-empty">Cookie yo'q</div>
  </div>
</template>
