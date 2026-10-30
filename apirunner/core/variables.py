import re

_VAR_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def replace_variables(text, variables):
    """`{{name}}` ni qiymat bilan almashtiradi. Noma'lum nom o'zgarishsiz qoladi."""
    if text is None:
        return ""

    def replacer(match):
        key = match.group(1).strip()
        if key in variables:
            v = variables[key]
            return "" if v is None else str(v)
        return match.group(0)

    return _VAR_RE.sub(replacer, str(text))
