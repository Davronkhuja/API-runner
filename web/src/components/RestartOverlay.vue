<script setup lang="ts">
import { server } from '../lib/server'
const location = window.location
</script>

<template>
  <div v-if="server.restarting" class="restart-overlay" role="alertdialog" aria-modal="true" aria-labelledby="ro-title" data-testid="restarting">
    <div class="ro-box">
      <h2 id="ro-title">Server yangilanmoqda…</h2>
      <p v-if="!server.restartError" class="muted">Server qayta ko'tarilgach sahifa o'zi yangilanadi.</p>
      <template v-else>
        <p class="state-error" role="alert" data-testid="restart-error">{{ server.restartError }}</p>
        <button class="primary" data-testid="restart-reload" @click="location.reload()">Sahifani yangilash</button>
      </template>
    </div>
  </div>
</template>
