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
