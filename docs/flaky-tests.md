# Beqaror testlar: tahlil (Bosqich 8)

Kuzatilgan holat (v2.9.0 ishlab chiqish paytida bitta to'liq yurishda): `test_node_tabs::test_context_menu_remains_with_open_settings_and_runner`, `test_scripts_ui::test_console_shows_unsupported_api_warnings`, `test_multitab_spec::test_shortcut_cmd_shift_t_reopen_closed_tab`, `test_trash_ui::test_collection_delete_from_context_menu_shows_request_count_and_goes_to_trash`, `test_postman_compat::test_sample_collection_scripts_run_unchanged_with_set_next_request_flow` (+2 error). Keyingi yurishlarda hammasi o'tdi.

## Qayta hosil qilish urinishlari
| Urinish | Natija |
|---|---|
| 5 test × 6 parallel jarayon (`-n 2`) × 4 raund = 24 yurish | 24/24 o'tdi |
| xuddi shu, 8 ta `yes` CPU-yuklovchi bilan, 10 parallel × 3 raund = 30 yurish | 30/30 o'tdi |
| To'liq majmua (`-n 8`) + 6 CPU-yuklovchi | 1320/1320 o'tdi |

Ya'ni **yuklama o'zi** bu beshta testni yiqitmaydi. Sabab boshqa joyda ekanini ko'rsatuvchi dalillar:

1. **Tekshiruv paytida kod/build o'zgargan.** O'sha yurish paytida Bosqich 7 kodi tahrirlanayotgan va `npm run build` qayta ishga tushirilayotgan edi. `vite build` `apirunner/static/app/assets/` dagi eski xeshli fayllarni **o'chiradi** (git'da `D apirunner/static/app/assets/index-….js` ko'rinadi); yurayotgan serverga ulanayotgan brauzer eski xeshli bundle'ni so'rasa — sahifa yuklanmaydi (`TimeoutError … waiting for locator`). Yiqilgan xabarlarda aynan shunday imzolar bor: `Locator.dblclick/Page.click: Timeout 30000ms` hamda daraxt/kontekst menyusi elementlari soni kutilganidan farq qilgan (`count 6 … resolved to 7 elements`, `'runner' != 'settings'`) — bu Stage 7 da kontekst menyusiga «Mock server…» qo'shilgani bilan eskirgan kutilmalar edi.
2. **Testlarning o'zida poyga (haqiqiy nuqson, tuzatildi):**
   - `test_multitab_spec`: 16 joyda `assert titles(ui) == [...]` — DOM'ni bir marta o'qiydi, ⌘W/⌘⇧T dan keyin Vue yangilanishini kutmaydi. → `expect(locator).to_have_text([...])` (qayta urinadi).
   - `test_scripts_ui::…unsupported_api_warnings`: «Yuborish» + Console ochilgach `all_inner_texts()` darhol o'qiladi, yozuvlar asinxron keladi. → avval `expect(...).to_be_visible()`.
   - `test_trash_ui::…goes_to_trash`: `Escape` bilan tasdiq dialogi yopilmasdan turib keyingi o'ng-tugma bosiladi. → avval `expect(confirm-dialog).to_have_count(0)`.
   - `test_multitab_spec::test_environment_opens_as_tab`: bir martalik `titles()` o'qish → `expect(...).to_have_count(1)`.
3. **Ilova nuqsoni (tuzatildi, tadqiqot paytida topildi):** fokusdagi element (masalan «Qayta urinish») dialog ichida DOM'dan o'chsa, fokus `body`ga tushar va **Esc dialogni yopmasdi** (Dialog faqat o'z overlay'idagi `keydown`ni tinglardi). Endi eng ustki dialog Esc'ni hujjat darajasida ham ushlaydi (regressiya testlari `test_polish_ui`).

## `test_postman_compat` haqida
Bu sof backend testi (quickjs sandbox + lokal fake server). 54 ta yuklama ostidagi yurishda yiqilmadi; sandbox vaqt byudjeti (10 s devor vaqti, 2.7.2 tuzatishidan keyin faqat foydalanuvchi skripti uchun) yuklamada ham yetarli. Bitta yurishdagi yiqilish sababi **isbotlanmadi** — eng ehtimoliy izoh: shu yurish davomida `apirunner/core/*` fayllari tahrirlanayotgan edi (yarim yozilgan holat). Agar yana yiqilsa: `-n 0 -k nom`, to'liq traceback va vaqt belgisi bilan shu faylga qo'shing.

## Qoida (jarayon)
**To'liq majmua yurayotganda `npm run build`, kod tahriri yoki `UPDATE_BASELINE` yurgizilmaydi** — yurish tugagach natija "tugatishdan keyingi holat" bo'lsin. Yakuniy dalil — o'zgarishsiz daraxtda bir yurish.
