<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AuthDraft } from '../lib/auth'

const props = defineProps<{ auth: AuthDraft; allowInherit?: boolean; inheritNote?: string }>()
const emit = defineEmits<{ change: [] }>()
const showPass = ref(false)
const touch = () => emit('change')
const preview = computed(() => (props.auth.user || props.auth.pass ? '••••' : ''))
</script>

<template>
  <div data-testid="auth-panel">
    <select v-model="auth.type" data-testid="auth-type" @change="touch">
      <option v-if="allowInherit" value="inherit">Meros (Inherit)</option>
      <option value="none">Auth yo'q</option><option value="bearer">Bearer Token</option><option value="basic">Basic Auth</option><option value="custom">Custom</option>
    </select>
    <p v-if="auth.type === 'inherit'" class="muted" data-testid="auth-inherit-note">{{ inheritNote || 'Ota papka / collection auth\'idan olinadi.' }}</p>
    <p v-if="auth.type === 'bearer'"><input v-model="auth.token" placeholder="Token" style="width:100%" data-testid="auth-token" @input="touch"></p>
    <p v-if="auth.type === 'basic'"><input v-model="auth.user" placeholder="Username" @input="touch"> <input v-model="auth.pass" :type="showPass ? 'text' : 'password'" placeholder="Password" data-testid="auth-pass" @input="touch"> <button class="ghost" data-testid="auth-eye" @click="showPass = !showPass">👁</button> <span class="muted" data-testid="auth-preview">Authorization: Basic {{ preview }}</span></p>
    <p v-if="auth.type === 'custom'"><input v-model="auth.custom" placeholder="Authorization qiymati" style="width:100%" data-testid="auth-custom" @input="touch"></p>
  </div>
</template>
