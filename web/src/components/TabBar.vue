<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useTabs, type Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { askClose } from '../lib/ui'
import { saveTab } from '../lib/actions'

const tabs = useTabs()
const tree = useTree()
const menu = ref<{ x: number; y: number; id: string } | null>(null)
const list = ref(false)
const dragId = ref<string | null>(null)
const overId = ref<{ id: string; side: 'l' | 'r' } | null>(null)
const scroller = ref<HTMLElement>()

const confirm = (t: Tab) => askClose(`"${t.title}" saqlanmagan. Saqlansinmi?`)
const save = async (t: Tab) => { await saveTab(t) }
const closeTab = (id: string) => tabs.close(id, confirm, save)

function onDrop(id: string) {
  if (!dragId.value || dragId.value === id) return
  const to = tabs.tabs.findIndex(t => t.id === id) + (overId.value?.side === 'r' ? 1 : 0)
  const from = tabs.tabs.findIndex(t => t.id === dragId.value)
  tabs.reorder(dragId.value, from < to ? to - 1 : to)
  dragId.value = overId.value = null
}
function overTab(e: DragEvent, id: string) {
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  overId.value = { id, side: e.clientX < r.left + r.width / 2 ? 'l' : 'r' }
}
function ctx(e: MouseEvent, id: string) { menu.value = { x: e.clientX, y: e.clientY, id } }
async function act(a: string) {
  const id = menu.value!.id; menu.value = null
  const t = tabs.tabs.find(x => x.id === id)!
  if (a === 'dup') tabs.duplicate(id)
  else if (a === 'close') await closeTab(id)
  else if (a === 'others') await tabs.closeOthers(id, confirm, save)
  else if (a === 'right') await tabs.closeRight(id, confirm, save)
  else if (a === 'all') await tabs.closeAll(confirm, save)
  else if (a === 'reveal' && t.ref?.includes(':')) { const [c, i] = t.ref.split(':'); tree.reveal(c, i) }
}
async function pick(id: string) {
  tabs.activate(id); list.value = false
  await nextTick()
  scroller.value?.querySelector(`[data-tab="${id}"]`)?.scrollIntoView({ inline: 'nearest' })
}
</script>

<template>
  <div class="tabbar" data-testid="tabbar" @click="menu = null">
    <div class="tabs-scroll" ref="scroller">
      <div v-for="t in tabs.tabs" :key="t.id" class="tab" :data-tab="t.id" data-testid="tab"
           :class="{ active: t.id === tabs.activeId, preview: t.preview, 'drop-l': overId?.id === t.id && overId.side === 'l', 'drop-r': overId?.id === t.id && overId.side === 'r' }"
           draggable="true" @dragstart="dragId = t.id" @dragover.prevent="overTab($event, t.id)" @dragleave="overId = null" @drop.prevent="onDrop(t.id)" @dragend="dragId = overId = null"
           @click.stop="tabs.activate(t.id)" @dblclick="t.preview = false" @contextmenu.prevent="ctx($event, t.id)" @auxclick.middle="closeTab(t.id)">
        <span class="title">{{ t.title }}</span>
        <span v-if="t.dirty" class="dot" data-testid="dirty-dot">●</span>
        <button class="x" data-testid="tab-close" title="Yopish" @click.stop="closeTab(t.id)">×</button>
      </div>
    </div>
    <button class="ghost" title="Yangi tab" data-testid="new-tab" @click="tabs.openNew()">＋</button>
    <div style="position:relative">
      <button class="ghost" title="Barcha tablar" data-testid="all-tabs" @click.stop="list = !list">▾</button>
      <div v-if="list" class="menu" style="position:absolute;right:0;top:34px;max-height:60vh;overflow:auto" data-testid="all-tabs-list">
        <button v-for="t in tabs.tabs" :key="t.id" @click="pick(t.id)">{{ t.dirty ? '● ' : '' }}{{ t.title }}</button>
        <div v-if="!tabs.tabs.length" class="muted" style="padding:6px">Tab yo'q</div>
      </div>
    </div>
    <div v-if="menu" class="menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }" data-testid="tab-menu" @click.stop>
      <button data-act="dup" @click="act('dup')">Dublikat</button>
      <button data-act="close" @click="act('close')">Yopish</button>
      <button data-act="others" :disabled="tabs.tabs.length < 2" @click="act('others')">Boshqalarini yopish</button>
      <button data-act="right" :disabled="tabs.tabs.at(-1)?.id === menu.id" @click="act('right')">O'ngdagilarni yopish</button>
      <button data-act="all" @click="act('all')">Hammasini yopish</button>
      <button data-act="reveal" :disabled="!tabs.tabs.find(t => t.id === menu!.id)?.ref?.includes(':')" @click="act('reveal')">Collection'da ko'rsatish</button>
    </div>
  </div>
</template>
