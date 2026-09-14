"""
GSM-7 safety net for outbound SMS bodies.

Twilio bills SMS per segment, and segment size depends entirely on encoding:
GSM-7 gets 160 chars/segment (153 when concatenated across multiple
segments); the moment a body contains even one character outside the GSM-7
character set, Twilio silently re-encodes the *entire* message as UCS-2,
cutting the limit to 70 chars/segment (67 concatenated) — often 2x+ the
segment count, and therefore 2x+ the cost, for the same visible text.

The usual offenders are typographic characters a writer reaches for
automatically and never notices: em/en dashes, curly quotes, ellipses, and
emoji. gsm7_safe() normalizes those to their GSM-7-safe equivalents before a
body ever reaches Twilio, so a stray em dash in a template can't silently
double the bill.
"""

_REPLACEMENTS = {
    "—": "-",   # em dash —
    "–": "-",   # en dash –
    "‘": "'",   # left single quote '
    "’": "'",   # right single quote '
    "“": '"',   # left double quote "
    "”": '"',   # right double quote "
    "…": "...", # ellipsis …
    "\U0001f44d": "a thumbs up",  # 👍
}


def gsm7_safe(text: str) -> str:
    if not text:
        return text
    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text
