/** "Ghost" qator: jadval oxirida DOIM bitta bo'sh qator (Postman kabi). Yozilganda oddiy qatorga aylanadi va pastida yangisi paydo bo'ladi.
 *  Ghost saqlanmaydi, URL'ga qo'shilmaydi va o'zi "dirty" holat yaratmaydi (o'zgartirish `change` chiqarmaydi). */
export function ensureGhost<T>(rows: T[], blank: (r: T) => boolean, make: () => T): boolean {
  let end = rows.length
  while (end > 0 && blank(rows[end - 1])) end--
  if (rows.length - end === 1) return false           // allaqachon aynan bitta ghost
  rows.splice(end, rows.length - end, make())          // oxiridagi bo'shlar bittaga keltiriladi (yo'q bo'lsa qo'shiladi)
  return true
}
