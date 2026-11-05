/** Ko'rinish sozlamalari (Sozlamalar → Ko'rinish): so'rov/javob joylashuvi va zich rejim. Brauzerda saqlanadi (tema kabi). */
import { ref, watch } from 'vue'

export type Layout = 'stack' | 'side'
const KEY = 'apirunner.view.v1'

function load(): { layout: Layout; dense: boolean } {
  try { const d = JSON.parse(localStorage.getItem(KEY) ?? 'null'); return { layout: d?.layout === 'side' ? 'side' : 'stack', dense: !!d?.dense } } catch { return { layout: 'stack', dense: false } }
}
const init = load()
export const layout = ref<Layout>(init.layout)
export const dense = ref<boolean>(init.dense)

export function applyView() {
  const c = document.documentElement.classList
  c.toggle('view-side', layout.value === 'side')
  c.toggle('dense', dense.value)
}
watch([layout, dense], () => {
  applyView()
  try { localStorage.setItem(KEY, JSON.stringify({ layout: layout.value, dense: dense.value })) } catch { /* bloklangan — sessiya davomida ishlaydi */ }
}, { flush: 'sync' })
export const toggleLayout = () => { layout.value = layout.value === 'side' ? 'stack' : 'side' }
