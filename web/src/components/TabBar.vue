<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useTabs, type Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { askClose } from '../lib/ui'
import { saveTab } from '../lib/actions'
import Icon from './Icon.vue'

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
/** ←/→/Home/End tablar orasida (avtomatik faollashadi); Delete — yopish. */
function onKey(e: KeyboardEvent) {
  const ids = tabs.tabs.map(t => t.id), i = ids.indexOf(tabs.activeId ?? '')
  const to = e.key === 'ArrowRight' ? ids[(i + 1) % ids.length] : e.key === 'ArrowLeft' ? ids[(i - 1 + ids.length) % ids.length] : e.key === 'Home' ? ids[0] : e.key === 'End' ? ids[ids.length - 1] : null
  if (to) { e.preventDefault(); tabs.activate(to); nextTick(() => scroller.value?.querySelector<HTMLElement>(`[data-tab="${to}"]`)?.focus()) }
  else if (e.key === 'Delete' && tabs.activeId) { e.preventDefault(); closeTab(tabs.activeId) }
}
async function pick(id: string) {
  tabs.activate(id); list.value = false
  await nextTick()
  scroller.value?.querySelector(`[data-tab="${id}"]`)?.scrollIntoView({ inline: 'nearest' })
}
</script>

<template>
  <div class="tabbar" data-testid="tabbar" @click="menu = null">
    <div class="tabs-scroll" ref="scroller" role="tablist" aria-label="Ochiq tablar" @keydown="onKey">
      <div v-for="t in tabs.tabs" :key="t.id" class="tab" :data-tab="t.id" data-testid="tab" role="tab" :aria-selected="t.id === tabs.activeId" :tabindex="t.id === tabs.activeId ? 0 : -1"
           :class="{ active: t.id === tabs.activeId, preview: t.preview, 'drop-l': overId?.id === t.id && overId.side === 'l', 'drop-r': overId?.id === t.id && overId.side === 'r' }"
           draggable="true" @dragstart="dragId = t.id" @dragover.prevent="overTab($event, t.id)" @dragleave="overId = null" @drop.prevent="onDrop(t.id)" @dragend="dragId = overId = null"
           @click.stop="tabs.activate(t.id)" @dblclick="t.preview = false" @contextmenu.prevent="ctx($event, t.id)" @auxclick.middle="closeTab(t.id)">
        <span v-if="t.kind === 'request' && t.draft" class="m" :class="'m-' + t.draft.method">{{ t.draft.method }}</span>
        <span class="title">{{ t.title }}</span>
        <span v-if="t.dirty" class="dot" data-testid="dirty-dot" role="img" aria-label="Saqlanmagan o'zgarishlar" title="Saqlanmagan o'zgarishlar" />
        <button class="x" data-testid="tab-close" :aria-label="`${t.title} tabini yopish`" title="Yopish" tabindex="-1" @click.stop="closeTab(t.id)"><Icon name="x" :size="13" /></button>
      </div>
    </div>
    <button class="ib" aria-label="Yangi tab" title="Yangi tab (⌘T)" data-testid="new-tab" style="margin:3px 4px;flex-shrink:0" @click="tabs.openNew()"><Icon name="plus" :size="16" /></button>
    <div style="position:relative;margin:3px 0">
      <button class="ib" aria-label="Barcha tablar" title="Barcha tablar" data-testid="all-tabs" aria-haspopup="menu" :aria-expanded="list" @click.stop="list = !list"><Icon name="chevron-down" :size="16" /></button>
      <div v-if="list" class="menu" style="position:absolute;right:0;top:34px;max-height:60vh;overflow:auto" data-testid="all-tabs-list" role="menu">
        <button v-for="t in tabs.tabs" :key="t.id" role="menuitem" @click="pick(t.id)">{{ t.dirty ? '● ' : '' }}{{ t.title }}</button>
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
