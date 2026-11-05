/** JSON xatosini aniqlash (body muharriri): {{o'zgaruvchi}} placeholder'lari xato hisoblanmaydi; xato joyi va qator raqami qaytariladi. */
export interface JsonError { pos: number; line: number; col: number; message: string }

/** `{{var}}` ni bir xil uzunlikdagi raqam (`1000…`, bosh nolsiz) bilan almashtiradi (qator ichida ham, qiymat o'rnida ham to'g'ri JSON bo'lib qoladi, pozitsiyalar saqlanadi). */
export const maskVars = (text: string) => text.replace(/\{\{[^}\n]*\}\}/g, m => '1' + '0'.repeat(m.length - 1))

export function lineCol(text: string, pos: number) {
  const before = text.slice(0, Math.max(0, pos)).split('\n')
  return { line: before.length, col: before[before.length - 1].length + 1 }
}

export function jsonError(text: string): JsonError | null {
  if (!text.trim()) return null
  try { JSON.parse(maskVars(text)); return null } catch (e: any) {
    const msg = String(e?.message ?? e)
    let pos = Number(/position (\d+)/.exec(msg)?.[1])
    if (Number.isNaN(pos)) {
      const lc = /line (\d+) column (\d+)/.exec(msg)
      if (lc) { const lines = text.split('\n'); pos = lines.slice(0, Number(lc[1]) - 1).reduce((n, l) => n + l.length + 1, 0) + Number(lc[2]) - 1 } else pos = text.length
    }
    pos = Math.min(pos, text.length)
    return { pos, ...lineCol(text, pos), message: msg.replace(/ in JSON at position \d+.*$/, '').replace(/\s*\(line \d+ column \d+\)/, '') }
  }
}
