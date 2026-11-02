<script setup lang="ts">
/** So'rov sozlamalari formasi. `fallback` berilsa (so'rov darajasi) "Sukut" shu global qiymatni ko'rsatadi. */
import type { ReqSettings } from '../lib/settings'

const props = defineProps<{ model: ReqSettings; fallback?: ReqSettings; prefix?: string }>()
const emit = defineEmits<{ change: [] }>()
const DEFAULTS: ReqSettings = { follow_redirects: true, ssl_verify: true, http2: false, use_cookies: true }
type BoolKey = 'follow_redirects' | 'http2' | 'ssl_verify' | 'use_cookies'
const BOOLS: [BoolKey, string][] = [['follow_redirects', 'Redirect\'larga ergashish'], ['http2', 'HTTP/2'], ['ssl_verify', 'SSL sertifikatni tekshirish'], ['use_cookies', 'Cookie jar (saqlash va yuborish)']]
const TEXTS: [keyof ReqSettings, string, string][] = [['proxy', 'Proxy URL', 'http://127.0.0.1:8080'], ['ca_bundle', 'CA sertifikat fayli (.pem)', '/yo\'l/ca.pem'], ['cert', 'Mijoz sertifikati (.pem)', '/yo\'l/client.pem'], ['cert_key', 'Mijoz kaliti (.key)', '/yo\'l/client.key']]
const id = (k: string) => `${props.prefix ?? 'set'}-${k}`
const eff = (k: BoolKey) => (props.fallback?.[k] ?? DEFAULTS[k]) ? 'yoqilgan' : 'o\'chirilgan'
const bget = (k: BoolKey) => (props.model[k] === undefined ? '' : String(props.model[k]))
function bset(k: BoolKey, v: string) { if (v === '') delete props.model[k]; else props.model[k] = v === 'true'; emit('change') }
function tset(k: keyof ReqSettings, v: string) { if (v === '') delete props.model[k]; else (props.model as any)[k] = v; emit('change') }
function mset(v: string) { if (v === '' || Number.isNaN(Number(v))) delete props.model.max_redirects; else props.model.max_redirects = Math.max(0, Math.floor(Number(v))); emit('change') }
</script>

<template>
  <table class="kv" style="max-width:720px" :data-testid="id('form')"><tbody>
    <tr v-for="[k, label] in BOOLS" :key="k">
      <td style="width:260px" class="muted">{{ label }}</td>
      <td><select :value="bget(k)" :data-testid="id(k)" @change="bset(k, ($event.target as HTMLSelectElement).value)">
        <option value="">Sukut ({{ eff(k) }})</option><option value="true">Yoqilgan</option><option value="false">O'chirilgan</option></select></td>
    </tr>
    <tr>
      <td class="muted">Maks. redirect'lar</td>
      <td><input type="number" min="0" max="50" :value="model.max_redirects ?? ''" :placeholder="String(fallback?.max_redirects ?? 20)" :data-testid="id('max_redirects')" style="width:100px" @input="mset(($event.target as HTMLInputElement).value)"></td>
    </tr>
    <tr v-for="[k, label, ph] in TEXTS" :key="k">
      <td class="muted">{{ label }}</td>
      <td><input :value="(model as any)[k] ?? ''" :placeholder="(fallback as any)?.[k] || ph" :data-testid="id(k)" style="width:100%" @input="tset(k, ($event.target as HTMLInputElement).value)"></td>
    </tr>
  </tbody></table>
</template>
