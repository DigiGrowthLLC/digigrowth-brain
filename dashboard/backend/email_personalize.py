"""Light per-prospect rewrite of an Email Handoff touch (Dylan, 2026-10-20).

Every prospect getting the byte-identical body is a bulk-mail fingerprint,
so right before a touch is delivered Claude rewrites roughly 10% of the
already-filled email for that one prospect: greeting, how the opener line
is phrased, small wording choices. The template's structure, offer
sentences, bold phrases, links and sign-off stay as written.

The rewrite is only used if it passes _valid(): every URL and **bold**
phrase survives verbatim, no number or $ amount appears that wasn't in
the original, and the text stays close to the template. Anything else
(failed check, API error, refusal, missing key) falls back to the original
body, so personalization can never block or garble a send.
"""
import difflib
import os
import random
import re

MODEL = "claude-opus-5-5"
ENABLED = True

# Similarity to the filled template the rewrite must stay within — high
# enough that it's the same email, low enough to allow real variation.
MIN_SIMILARITY = 0.65

# One picked at random per email so rewrites don't all converge on the same
# "better" phrasing, which would just be a new shared fingerprint.
_VARIATION_HINTS = [
    "Keep the greeting close to the original; put most of the variation in how the noticed detail is phrased.",
    "Use a different, short greeting line, and lightly rephrase the noticed detail.",
    "Vary the first two sentences and one small phrase in the middle; keep the rest nearly word for word.",
    "Reword the line that introduces the video and the closing question slightly; keep the opening close.",
    "Make the opening a bit more casual, and work the practice's city in naturally if it's given.",
    "Barely touch the opening; vary connective words and one or two phrases in the body instead.",
]

_URL_RE = re.compile(r"https?://[^\s<>()]+")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
_NUM_RE = re.compile(r"\$?\d[\d,.]*%?")

_SYSTEM = """You lightly personalize one cold outreach email from Dylan (DigiGrowth) to the owner of an independent physical therapy practice. The same template goes to many practices, and identical emails look like bulk mail, so each copy needs small natural differences.

Rewrite about 10% of the email. Good places to vary:
- the greeting and the first line (e.g. "Hi", "Hey", "Hope your week's going well")
- how the sentence about what you noticed at their practice is phrased, so it reads like Dylan actually looked at their site
- small connective words and phrasing elsewhere

Hard rules:
- Keep the same structure, paragraph order, meaning and length. It must still read as the same email.
- Copy every URL exactly, on its own line where it was.
- Keep every phrase wrapped in **double asterisks** word for word, asterisks included.
- Do not add or change any number, price, percentage, timeframe or guarantee, and do not add new claims or offers.
- Only use facts about the practice that are given below. Don't invent details about the practice, its staff or its results.
- Keep the sign-off ("Thanks," / "Dylan") as it is.
- Plain text only, no em dashes, no emoji.
- Write like a busy founder typing a quick email: casual, natural, not salesy.

Return only the rewritten email body, nothing else."""


def _bolds(text: str) -> list[str]:
    return [m.strip() for m in _BOLD_RE.findall(text)]


def _valid(original: str, rewrite: str) -> str | None:
    """Returns why the rewrite is rejected, or None if it's usable."""
    if not rewrite.strip():
        return "empty"
    if sorted(_URL_RE.findall(original)) != sorted(_URL_RE.findall(rewrite)):
        return "links changed"
    if sorted(_bolds(original)) != sorted(_bolds(rewrite)):
        return "bold phrases changed"
    if set(_NUM_RE.findall(rewrite)) - set(_NUM_RE.findall(original)):
        return "new numbers"
    if "—" in rewrite and "—" not in original:
        return "em dash"
    if not 0.8 <= len(rewrite) / max(len(original), 1) <= 1.25:
        return "length changed"
    ratio = difflib.SequenceMatcher(None, original, rewrite).ratio()
    if ratio < MIN_SIMILARITY:
        return f"too different ({ratio:.2f})"
    return None


async def personalize(body: str, contact: dict) -> str:
    """The rewritten body for this prospect, or `body` unchanged."""
    if not ENABLED or not os.environ.get("ANTHROPIC_API_KEY"):
        return body
    facts = "\n".join(
        f"{label}: {value}" for label, value in (
            ("Practice", contact.get("business")),
            ("Owner", contact.get("owner")),
            ("City", ", ".join(p for p in (contact.get("city"), contact.get("state")) if p)),
            ("Website", contact.get("website")),
            ("What Dylan noticed about them", contact.get("opener")),
        ) if value
    )
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4000,
            output_config={"effort": "low"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": (
                f"About this practice:\n{facts}\n\nFor this copy: {random.choice(_VARIATION_HINTS)}"
                f"\n\nEmail to personalize:\n\n{body}"
            )}],
            # Server-side refusal fallback; sent raw so it works on the pinned SDK.
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
    except Exception as e:
        print(f"[email_personalize] API call failed, sending template as is: {e}")
        return body
    if response.stop_reason != "end_turn":
        print(f"[email_personalize] stop_reason={response.stop_reason}, sending template as is")
        return body
    rewrite = "".join(b.text for b in response.content if b.type == "text").strip()
    problem = _valid(body.strip(), rewrite)
    if problem:
        print(f"[email_personalize] rewrite rejected ({problem}), sending template as is")
        return body
    return rewrite
