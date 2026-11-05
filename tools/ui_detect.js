() => {
  const out = [], vw = innerWidth, vh = innerHeight
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0' }
  const sel = e => e.getAttribute('data-testid') ? `[data-testid=${e.getAttribute('data-testid')}]` : (e.className && typeof e.className === 'string' ? e.tagName.toLowerCase() + '.' + e.className.trim().split(/\s+/)[0] : e.tagName.toLowerCase())
  if (document.documentElement.scrollWidth > vw + 1) out.push({ kind: 'page-hscroll', detail: `scrollWidth ${document.documentElement.scrollWidth} > ${vw}` })
  document.querySelectorAll('.dialog,[role=dialog],.menu,.cmdk,.hist-drawer,.tip-pop').forEach(e => {
    if (!vis(e)) return
    const r = e.getBoundingClientRect()
    if (r.top < -1 || r.left < -1 || r.bottom > vh + 1 || r.right > vw + 1) out.push({ kind: 'overlay-outside-viewport', detail: `${sel(e)} rect(${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)}) viewport ${vw}x${vh}` })
  })
  const small = {}
  document.querySelectorAll('button,a[href],select,textarea,input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]),[role=button],[role=tab]').forEach(e => {
    if (!vis(e)) return
    const r = e.getBoundingClientRect()
    if (r.width < 24 || r.height < 24) { const k = sel(e) + ` ${Math.round(r.width)}x${Math.round(r.height)}`; small[k] = (small[k] || 0) + 1 }
  })
  for (const [k, n] of Object.entries(small)) out.push({ kind: 'small-target', detail: `${k} (×${n})` })
  const clipped = {}
  document.querySelectorAll('body *').forEach(e => {
    if (!vis(e) || e.children.length > 3 || !(e.textContent || '').trim()) return
    const s = getComputedStyle(e)
    if (e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0 && (s.overflowX === 'hidden' || s.overflowX === 'clip') && s.textOverflow !== 'ellipsis' && !e.closest('.cm-editor,.hx-diff,pre,.tabs-scroll,.urlfield')) {
      const k = sel(e); clipped[k] = (clipped[k] || 0) + 1
    }
  })
  for (const [k, n] of Object.entries(clipped)) out.push({ kind: 'clipped-text', detail: `${k} (×${n})` })
  const ed = document.querySelector('.editor.fill'), cm = ed && ed.querySelector('.cm-editor')
  if (ed && cm) { const gap = ed.getBoundingClientRect().bottom - cm.getBoundingClientRect().bottom; if (gap > 24) out.push({ kind: 'editor-dead-space', detail: `${Math.round(gap)}px` }) }
  const btns = [...document.querySelectorAll('.cm-editor')].filter(vis)
  btns.forEach(c => { if (c.closest('.url-editor')) return; const r = c.getBoundingClientRect(); if (r.height < 60) out.push({ kind: 'editor-too-short', detail: `${sel(c.parentElement)} height ${Math.round(r.height)}` }) })
  return out
}
