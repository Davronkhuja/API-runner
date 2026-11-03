from apirunner.core.variables import replace_variables as rv


def test_replaces_known_key():
    assert rv("a/{{id}}/b", {"id": 7}) == "a/7/b"


def test_whitespace_inside_braces_is_trimmed():
    assert rv("{{  id  }}", {"id": "x"}) == "x"


def test_unknown_key_left_untouched():
    assert rv("{{nope}}", {"id": 1}) == "{{nope}}"


def test_none_value_becomes_empty():
    assert rv("[{{a}}]", {"a": None}) == "[]"


def test_none_text_becomes_empty_string():
    assert rv(None, {}) == ""


def test_multiple_and_repeated():
    assert rv("{{a}}-{{b}}-{{a}}", {"a": 1, "b": 2}) == "1-2-1"


def test_non_string_text_is_stringified():
    assert rv(123, {}) == "123"


def test_nested_variables_are_resolved():
    assert rv("{{url}}/x", {"url": "{{host}}/api", "host": "h"}) == "h/api/x"


def test_circular_variables_terminate():
    assert rv("{{a}}", {"a": "{{b}}", "b": "{{a}}"}) in ("{{a}}", "{{b}}")


def test_dynamic_variables_are_fresh_and_have_shape():
    import re
    a, b = rv("{{$guid}}", {}), rv("{{$guid}}", {})
    assert a != b and re.fullmatch(r"[0-9a-f-]{36}", a)
    assert rv("{{$timestamp}}", {}).isdigit()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.]+Z", rv("{{$isoTimestamp}}", {}))
    assert 0 <= int(rv("{{$randomInt}}", {})) <= 1000
    assert "@" in rv("{{$randomEmail}}", {})


def test_user_variable_wins_over_dynamic_and_unknown_dynamic_stays():
    assert rv("{{$guid}}", {"$guid": "fixed"}) == "fixed"
    assert rv("{{$nope}}", {}) == "{{$nope}}"


def test_path_variables_only_in_path():
    from apirunner.core.variables import apply_path_variables as ap
    pv = [{"name": "id", "value": "42"}, {"name": "port", "value": "X"}]
    assert ap("http://h:5050/users/:id/x?t=:id", pv) == "http://h:5050/users/42/x?t=:id"
    assert ap("/a/:missing", pv) == "/a/:missing"
    assert ap("http://h/a/:id", None) == "http://h/a/:id"
