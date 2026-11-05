/** Panel ajratgichlari uchun umumiy yordamchilar: clamp, sudrash (pointer capture), saqlash. */
export const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
export const MIN_PANE = 120          // javob paneli (va Console/sidebar) uchun eng kichik o'lcham
export const MIN_REQ_SIDE = 380      // yonma-yon: so'rov paneli (bo'limlar qatori va body toolbar sig'ishi uchun)
export const MIN_RESP_SIDE = 280
export const MIN_REQ = 240           // so'rov paneli: sarlavha, bo'limlar va toolbar ~110px + muharrir kamida ~120px
export const HANDLE = 12

/** Ikkinchi qism (javob) `size` bo'lsin: javob kamida `min`, birinchi (so'rov) kamida `minFirst`. Joy yetmasa — teng bo'linadi. */
export function clampPane(total: number, size: number, min = MIN_PANE, minFirst = MIN_PANE): number {
  const hi = total - minFirst
  return hi < min ? Math.round(total / 2) : clamp(Math.round(size), min, hi)
}

/**
 * Sudrashni boshlaydi: setPointerCapture (kursor sahifadan chiqib ketsa ham kuzatiladi), butun sahifada row/col-resize kursori,
 * matn belgilanmaydi (body sinfi), iframe'lar hodisani yutmaydi. `onMove(delta)` — boshlang'ich nuqtadan siljish (px).
 */
export function drag(e: PointerEvent, axis: 'x' | 'y', onMove: (delta: number) => void, onEnd?: () => void) {
  const el = e.currentTarget as HTMLElement
  e.preventDefault()
  const start = axis === 'y' ? e.clientY : e.clientX
  const cls = axis === 'y' ? 'resizing-row' : 'resizing-col'
  try { el.setPointerCapture(e.pointerId) } catch { /* sintetik hodisa */ }
  document.body.classList.add(cls)
  const move = (ev: PointerEvent) => onMove((axis === 'y' ? ev.clientY : ev.clientX) - start)
  const end = () => {
    el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', end); el.removeEventListener('pointercancel', end)
    try { el.releasePointerCapture(e.pointerId) } catch { /* allaqachon bo'shatilgan */ }
    document.body.classList.remove(cls)
    onEnd?.()
  }
  el.addEventListener('pointermove', move); el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end)
}

export function loadJSON<T>(key: string, fallback: T): T {
  try { return { ...fallback, ...JSON.parse(localStorage.getItem(key) ?? '{}') } } catch { return fallback }
}
export function saveJSON(key: string, v: unknown) { try { localStorage.setItem(key, JSON.stringify(v)) } catch { /* bloklangan */ } }
