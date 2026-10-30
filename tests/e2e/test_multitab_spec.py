"""Bosqich 2 — Multi-tab (MAJBURIY). Har bir band uchun alohida e2e test.
Hozircha skip; Bosqich 2 da implementatsiya bilan birga yoqiladi. Hech bir band tushib qolmasin."""
import pytest

pytestmark = pytest.mark.skip(reason="Bosqich 2: multi-tab hali yo'q")

SPEC = [
    "test_open_many_tabs_simultaneously",
    "test_single_click_opens_preview_tab_italic_replaced_by_next_click",
    "test_double_click_makes_tab_permanent",
    "test_editing_preview_tab_makes_it_permanent",
    "test_each_tab_keeps_independent_state_url_params_body_auth_scripts_response_scroll",
    "test_switching_tabs_loses_nothing",
    "test_dirty_indicator_dot_on_edit_and_cleared_on_save",
    "test_closing_dirty_tab_shows_save_dontsave_cancel_dialog",
    "test_dialog_save_saves_and_closes",
    "test_dialog_dont_save_discards_and_closes",
    "test_dialog_cancel_keeps_tab_open",
    "test_context_menu_duplicate",
    "test_context_menu_close",
    "test_context_menu_close_others",
    "test_context_menu_close_to_the_right",
    "test_context_menu_close_all",
    "test_context_menu_reveal_in_collection",
    "test_drag_and_drop_reorder_tabs",
    "test_many_tabs_horizontal_scroll",
    "test_all_tabs_dropdown_lists_and_activates",
    "test_open_tabs_and_active_tab_restored_after_page_reload",
    "test_open_tabs_and_active_tab_restored_after_server_restart",
    "test_shortcut_cmd_t_new_tab",
    "test_shortcut_cmd_w_close_tab",
    "test_shortcut_ctrl_tab_next_and_ctrl_shift_tab_previous",
    "test_shortcut_cmd_shift_t_reopen_closed_tab",
    "test_opening_same_request_twice_switches_to_existing_tab",
    "test_environment_opens_as_tab",
    "test_collection_opens_as_tab",
    "test_runner_opens_as_tab",
]


@pytest.mark.parametrize("name", SPEC)
def test_spec(name):
    raise NotImplementedError(name)
