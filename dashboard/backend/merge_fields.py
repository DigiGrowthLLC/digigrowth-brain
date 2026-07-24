import re

_BRACE_TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")
_BRACKET_TOKEN_RE = re.compile(r"\[([^\[\]]+)\]")

# Maps a normalized token (lowercased, whitespace-collapsed) to a merge-value
# key. Supports both {{double-brace}} tokens and [Square Bracket] tokens
# (the latter matching how the user already writes scripts elsewhere) —
# both point at the same value set below.
_ALIASES = {
    "name": "name",
    "custom opener": "opener",
    "opener": "opener",
    "business": "business",
}


def apply_merge_fields(text: str, contact: dict | None) -> str:
    """Substitutes merge tokens using the given contact row. Two token
    syntaxes are supported and resolve to the same values:
      {{name}} / [Name]                 -> first token of contact.owner
      {{business}} / [Business]         -> contact.business
      {{opener}} / [Opener] / [Custom Opener] -> contact.opener
    Double-brace tokens are matched separately from the app's existing
    single-brace {first_name} convention (sms.py/integrations.py) so the two
    systems never collide inside the same string."""
    contact = contact or {}
    owner = (contact.get("owner") or "").strip()
    first_name = owner.split()[0] if owner else "there"

    values = {
        "name": first_name,
        "business": (contact.get("business") or "").strip(),
        "opener": (contact.get("opener") or "").strip(),
    }

    def _resolve(raw_key: str) -> str | None:
        normalized = re.sub(r"\s+", " ", raw_key.strip().lower())
        value_key = _ALIASES.get(normalized)
        return values.get(value_key) if value_key else None

    def _sub_brace(m: re.Match) -> str:
        resolved = _resolve(m.group(1))
        return resolved if resolved is not None else m.group(0)

    def _sub_bracket(m: re.Match) -> str:
        resolved = _resolve(m.group(1))
        return resolved if resolved is not None else m.group(0)

    text = _BRACE_TOKEN_RE.sub(_sub_brace, text)
    text = _BRACKET_TOKEN_RE.sub(_sub_bracket, text)
    return text
