/** Yengil sintaksis ranglash (v-html uchun, kirish doim escape qilinadi). Katta matnda o'chadi. */
const MAX = 200_000
export const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

export function highlightJson(text: string): string {
  if (text.length > MAX) return esc(text)
  return esc(text).replace(
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (_m, str, colon, lit, num) => str ? (colon ? `<span class="hl-key">${str}</span>${colon}` : `<span class="hl-str">${str}</span>`) : lit ? `<span class="hl-lit">${lit}</span>` : `<span class="hl-num">${num}</span>`,
  )
}

export function highlightCurl(text: string): string {
  if (text.length > MAX) return esc(text)
  // Bitta o'tishda: satr / bayroq / curl — keyin qo'yilgan span atributlari qayta ishlanmaydi
  return text.replace(/'(?:[^']|'\\'')*'|"(?:\\.|[^"\\])*"|(?<=^|\s)--?[A-Za-z][\w-]*|^curl\b/g, m =>
    m === 'curl' ? `<span class="hl-cmd">${m}</span>` : m.startsWith('-') ? `<span class="hl-flag">${esc(m)}</span>` : `<span class="hl-str">${esc(m)}</span>`,
  ).split(/(<span[^>]*>.*?<\/span>)/s).map(part => (part.startsWith('<span') ? part : esc(part))).join('')
}
