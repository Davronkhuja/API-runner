<script setup lang="ts">
import { computed, ref } from 'vue'
import { defaultCfg, type AuthDraft } from '../lib/auth'
import { clearToken, getNewToken, isCodeFlow, isExpired, tokenFor } from '../lib/oauth'
import { flatVars } from '../lib/scope'
import { showToast } from '../lib/ui'

const props = defineProps<{ auth: AuthDraft; allowInherit?: boolean; inheritNote?: string; scopeRef?: string | null }>()
const emit = defineEmits<{ change: [] }>()
const showPass = ref(false)
const touch = () => emit('change')
const preview = computed(() => (props.auth.user || props.auth.pass ? '••••' : ''))
function onType() { props.auth.cfg = { ...defaultCfg(props.auth.type), ...props.auth.cfg }; touch() }

interface Field { k: string; label: string; secret?: boolean; options?: [string, string][]; area?: boolean; show?: (c: Record<string, string>) => boolean; ph?: string }
const OAUTH_GRANTS: [string, string][] = [['client_credentials', 'Client Credentials'], ['password', 'Password Credentials'], ['authorization_code', 'Authorization Code'], ['authorization_code_pkce', 'Authorization Code (PKCE)'], ['implicit', 'Implicit']]
const FIELDS: Record<string, Field[]> = {
  apikey: [{ k: 'key', label: 'Key' }, { k: 'value', label: 'Value' }, { k: 'in', label: 'Qo\'shish', options: [['header', 'Header'], ['query', 'Query params']] }],
  digest: [{ k: 'username', label: 'Username' }, { k: 'password', label: 'Password', secret: true }],
  awsv4: [{ k: 'accessKey', label: 'AccessKey' }, { k: 'secretKey', label: 'SecretKey', secret: true }, { k: 'region', label: 'Region' }, { k: 'service', label: 'Service' }, { k: 'sessionToken', label: 'Session token', secret: true }],
  jwt: [{ k: 'algorithm', label: 'Algoritm', options: [['HS256', 'HS256'], ['HS384', 'HS384'], ['HS512', 'HS512']] }, { k: 'secret', label: 'Secret', secret: true },
        { k: 'payload', label: 'Payload (JSON)', area: true }, { k: 'addTo', label: 'Qo\'shish', options: [['header', 'Header'], ['query', 'Query params']] },
        { k: 'headerPrefix', label: 'Header prefiksi', show: c => c.addTo !== 'query' }, { k: 'queryParamKey', label: 'Query kaliti', ph: 'token', show: c => c.addTo === 'query' }],
  oauth2: [
    { k: 'grant_type', label: 'Grant turi', options: OAUTH_GRANTS },
    { k: 'authUrl', label: 'Auth URL', show: c => isCodeFlow(c.grant_type) },
    { k: 'accessTokenUrl', label: 'Access Token URL', show: c => c.grant_type !== 'implicit' },
    { k: 'clientId', label: 'Client ID' },
    { k: 'clientSecret', label: 'Client Secret', secret: true, show: c => c.grant_type !== 'implicit' && c.grant_type !== 'authorization_code_pkce' },
    { k: 'scope', label: 'Scope' },
    { k: 'username', label: 'Username', show: c => c.grant_type === 'password' },
    { k: 'password', label: 'Password', secret: true, show: c => c.grant_type === 'password' },
    { k: 'redirect_uri', label: 'Redirect URI', ph: 'sukut: /oauth/callback', show: c => isCodeFlow(c.grant_type) },
    { k: 'client_authentication', label: 'Client autentifikatsiyasi', options: [['header', 'Basic Auth header'], ['body', 'Body\'da'] ], show: c => c.grant_type !== 'implicit' },
    { k: 'addTokenTo', label: 'Tokenni qo\'shish', options: [['header', 'Header'], ['queryParams', 'Query params']] },
    { k: 'headerPrefix', label: 'Header prefiksi', show: c => c.addTokenTo !== 'queryParams' },
  ],
}
const fields = computed(() => (FIELDS[props.auth.type] ?? []).filter(f => !f.show || f.show(props.auth.cfg)))

const busy = ref(false), oerr = ref('')
const tok = computed(() => (props.auth.type === 'oauth2' ? tokenFor(props.auth) : null))
const tokenInfo = computed(() => {
  const t = tok.value
  if (!t) return ''
  if (!t.expires_at) return 'muddati ko\'rsatilmagan'
  return isExpired(t, 0) ? 'muddati tugagan' : `${Math.max(0, t.expires_at - Math.floor(Date.now() / 1000))} s qoldi`
})
async function getToken() {
  busy.value = true; oerr.value = ''
  try { await getNewToken(props.auth, flatVars(props.scopeRef ?? null)); showToast('Token olindi', 'success') }
  catch (e: any) { oerr.value = e.message }
  finally { busy.value = false }
}
const copyTok = () => { navigator.clipboard?.writeText(tok.value?.access_token ?? ''); showToast('Nusxalandi', 'success') }
</script>

<template>
  <div data-testid="auth-panel">
    <select v-model="auth.type" data-testid="auth-type" @change="onType">
      <option v-if="allowInherit" value="inherit">Meros (Inherit)</option>
      <option value="none">Auth yo'q</option><option value="bearer">Bearer Token</option><option value="basic">Basic Auth</option><option value="custom">Custom</option>
      <option value="apikey">API Key</option><option value="digest">Digest Auth</option><option value="oauth2">OAuth 2.0</option><option value="awsv4">AWS Signature V4</option><option value="jwt">JWT Bearer</option>
    </select>
    <p v-if="auth.type === 'inherit'" class="muted" data-testid="auth-inherit-note">{{ inheritNote || 'Ota papka / collection auth\'idan olinadi.' }}</p>
    <p v-if="auth.type === 'bearer'"><input v-model="auth.token" placeholder="Token" style="width:100%" data-testid="auth-token" @input="touch"></p>
    <p v-if="auth.type === 'basic'"><input v-model="auth.user" placeholder="Username" @input="touch"> <input v-model="auth.pass" :type="showPass ? 'text' : 'password'" placeholder="Password" data-testid="auth-pass" @input="touch"> <button class="ghost" data-testid="auth-eye" @click="showPass = !showPass">👁</button> <span class="muted" data-testid="auth-preview">Authorization: Basic {{ preview }}</span></p>
    <p v-if="auth.type === 'custom'"><input v-model="auth.custom" placeholder="Authorization qiymati" style="width:100%" data-testid="auth-custom" @input="touch"></p>

    <table v-if="fields.length" class="kv auth-fields" data-testid="auth-fields"><tbody>
      <tr v-for="f in fields" :key="f.k">
        <td style="width:190px" class="muted">{{ f.label }}</td>
        <td>
          <select v-if="f.options" v-model="auth.cfg[f.k]" :data-testid="'auth-f-' + f.k" @change="touch"><option v-for="o in f.options" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select>
          <textarea v-else-if="f.area" v-model="auth.cfg[f.k]" :data-testid="'auth-f-' + f.k" style="width:100%;height:90px;font-family:ui-monospace,monospace" @input="touch" />
          <input v-else v-model="auth.cfg[f.k]" :type="f.secret ? 'password' : 'text'" :placeholder="f.ph" :data-testid="'auth-f-' + f.k" style="width:100%" @input="touch">
        </td>
      </tr>
    </tbody></table>

    <div v-if="auth.type === 'oauth2'" style="margin-top:10px" data-testid="oauth-box">
      <button class="primary" data-testid="oauth-get" :disabled="busy" @click="getToken">{{ busy ? 'Kutilmoqda…' : 'Get New Access Token' }}</button>
      <button v-if="tok" class="ghost" data-testid="oauth-clear" @click="clearToken(auth); touch()">Tokenni o'chirish</button>
      <p v-if="oerr" class="err" data-testid="oauth-error">{{ oerr }}</p>
      <div v-if="tok" data-testid="oauth-token" style="margin-top:8px">
        <span class="muted">Joriy token:</span> <code data-testid="oauth-token-value">{{ tok.access_token.slice(0, 6) }}••••••</code>
        <button class="ghost" data-testid="oauth-copy" @click="copyTok">Nusxa</button>
        <span class="muted" data-testid="oauth-expiry">· {{ tokenInfo }}</span>
        <span v-if="tok.refresh_token" class="muted"> · refresh bor</span>
      </div>
      <p v-else class="muted" data-testid="oauth-none">Token yo'q. Yuborishda to'g'ridan-to'g'ri grantlar (Client Credentials/Password) tokenni o'zi oladi va yangilaydi.</p>
    </div>
  </div>
</template>
