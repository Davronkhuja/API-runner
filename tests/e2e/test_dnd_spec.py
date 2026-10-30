"""Bosqich 2 — Sidebar va drag&drop (MAJBURIY). Har bir band uchun alohida e2e test.
Hozircha skip; Bosqich 2 da implementatsiya bilan birga yoqiladi. Hech bir band tushib qolmasin."""
import pytest

pytestmark = pytest.mark.skip(reason="Bosqich 2: ichma-ich papka va DnD hali yo'q")

SPEC = [
    "test_nested_folders_unlimited_depth",
    "test_collapse_expand_state_persisted",
    "test_move_request_between_folders",
    "test_move_request_between_collections",
    "test_reorder_requests_within_folder",
    "test_reorder_folders_within_folder",
    "test_move_folder_into_another_folder",
    "test_drop_indicator_before_inside_after",
    "test_hover_while_dragging_auto_expands_folder",
    "test_autoscroll_near_edge_of_long_list",
    "test_dropping_folder_into_its_own_descendant_is_forbidden",
    "test_alt_option_drag_copies_instead_of_moves",
    "test_order_persisted_in_backend_after_reload",
    "test_order_preserved_in_export",
    "test_multi_select_shift_click_range",
    "test_multi_select_cmd_click_toggle",
    "test_drag_multiple_items_together",
    "test_runner_request_list_reorder_by_dnd",
    "test_params_rows_reorder_by_dnd",
    "test_headers_rows_reorder_by_dnd",
    "test_form_data_rows_reorder_by_dnd",
    "test_drop_postman_collection_file_imports",
    "test_drop_openapi_file_imports",
    "test_drop_csv_file_imports",
    "test_drop_curl_text_imports",
    "test_keyboard_move_via_context_menu_move_to",
    "test_dnd_works_while_search_filter_active",
]


@pytest.mark.parametrize("name", SPEC)
def test_spec(name):
    raise NotImplementedError(name)
