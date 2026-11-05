<script setup lang="ts">
import { acceptVar, varPopup } from '../directives/varComplete'
</script>

<template>
  <div v-if="varPopup.open" class="var-popup" role="listbox" aria-label="O'zgaruvchilar" data-testid="var-popup" :style="{ left: varPopup.x + 'px', top: varPopup.y + 'px', minWidth: varPopup.w + 'px' }">
    <button v-for="(s, i) in varPopup.items" :key="s.name" role="option" type="button" :aria-selected="i === varPopup.index" :class="{ on: i === varPopup.index }" data-testid="var-option" @mousedown.prevent="acceptVar(s)">
      <span class="vn">{{ s.name }}</span><span class="vv" v-if="s.value">{{ s.value.slice(0, 40) }}</span><span class="vs">{{ s.scope }}</span>
    </button>
  </div>
</template>
