"""
Drafts a starting response_ai_context for a client (see response_ai.py) by
gathering everything already known about them — their completed onboarding
intake answers, their anchor contact's business info (website, notes, etc.
from client_marketing.py's Marketing Setup tab), and text extracted from any
PDFs/docx they've uploaded (client_uploads — e.g. a "resource library" doc
with their guarantee/FAQs/testimonials) — and asking Claude to write it up
as one coherent context document in the same shape a human would write by
hand in that textarea.

This only DRAFTS text and hands it back to the caller (routers/
client_marketing.py's generate-response-ai-context endpoint) — nothing is
saved here. The admin reviews/edits the draft in the UI before saving,
same as any other AI-assisted first draft in this codebase.

PDF/docx bytes are read transiently from R2 (r2_storage.get_object_bytes)
purely to extract text in memory — never written to disk, same "Railway
never persists upload bytes" principle as everywhere else uploads are
touched, just a momentary read instead of a stream-through.
"""
import asyncio
import io
import json
import os

import anthropic
import pypdf
from docx import Document

import r2_storage
from db import get_pool

_MAX_CHARS_PER_FILE = 8000
_MAX_TOTAL_FILE_CHARS = 30000

_PDF_TYPE = "application/pdf"
_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_PROMPT_TEMPLATE = """You are drafting reference material for an AI SMS assistant that will text \
real leads on behalf of this local business. Using ONLY the information below, write a context \
document the assistant will be given verbatim as its knowledge of the business.

Cover, where the information below actually supports it: business name, what they do, their offer/\
guarantee (with exact numbers if given), tone/voice, hours, common questions and how to answer them, \
and what should always be escalated to a human (e.g. billing/insurance questions, complaints, \
anything not covered here). Write it as clear prose/bullet points, not a form. Aim for roughly \
400-700 words — thorough enough to be useful, not exhaustive.

Critical rule: NEVER invent or guess at a fact, number, price, or claim that isn't actually present \
in the information below. Where something important is missing (e.g. no guarantee mentioned \
anywhere), write "[NEEDS INFO: ...]" instead of making something up.

--- Client record ---
{client_info}

--- Linked contact / business info ---
{anchor_info}

--- Onboarding intake answers ---
{onboarding_text}

--- Excerpts from uploaded documents ---
{uploads_text}
"""


def _extract_pdf_text(data: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def _extract_docx_text(data: bytes) -> str:
    try:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def _is_pdf(file_type: str | None, file_name: str) -> bool:
    return file_type == _PDF_TYPE or file_name.lower().endswith(".pdf")


def _is_docx(file_type: str | None, file_name: str) -> bool:
    return file_type == _DOCX_TYPE or file_name.lower().endswith(".docx")


async def _gather_uploaded_text(conn, client_id: int) -> str:
    if not r2_storage.is_configured():
        return "(file storage not connected)"

    rows = await conn.fetch(
        "SELECT file_name, file_type, r2_key FROM client_uploads WHERE client_id = $1 ORDER BY uploaded_at DESC",
        client_id,
    )
    candidates = [r for r in rows if _is_pdf(r["file_type"], r["file_name"]) or _is_docx(r["file_type"], r["file_name"])]
    if not candidates:
        return "(no PDF/docx files uploaded)"

    parts: list[str] = []
    total = 0
    for row in candidates:
        try:
            data = await asyncio.to_thread(r2_storage.get_object_bytes, row["r2_key"])
        except Exception:
            continue
        text = _extract_pdf_text(data) if _is_pdf(row["file_type"], row["file_name"]) else _extract_docx_text(data)
        text = text.strip()[:_MAX_CHARS_PER_FILE]
        if not text:
            continue
        parts.append(f"[{row['file_name']}]\n{text}")
        total += len(text)
        if total >= _MAX_TOTAL_FILE_CHARS:
            break
    return "\n\n".join(parts) if parts else "(no extractable text found in uploaded files)"


async def generate_context(client_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT name, contact_name, email, phone, notes FROM clients WHERE id = $1", client_id,
        )
        if not client:
            raise ValueError("Client not found")

        onboarding = await conn.fetch(
            "SELECT section, answers FROM client_onboarding_responses "
            "WHERE client_id = $1 AND completed_at IS NOT NULL ORDER BY section",
            client_id,
        )
        anchor = await conn.fetchrow(
            "SELECT business, owner, website, city, state, notes FROM contacts "
            "WHERE client_id = $1 AND is_client_anchor LIMIT 1",
            client_id,
        )
        uploads_text = await _gather_uploaded_text(conn, client_id)

    client_info = (
        f"Name on file: {client['name']}\nPrimary contact: {client['contact_name'] or '—'}\n"
        f"Email: {client['email'] or '—'}\nPhone: {client['phone'] or '—'}\nNotes: {client['notes'] or '—'}"
    )
    anchor_info = (
        f"Business: {anchor['business'] or '—'}\nOwner: {anchor['owner'] or '—'}\n"
        f"Website: {anchor['website'] or '—'}\nLocation: {', '.join(x for x in [anchor['city'], anchor['state']] if x) or '—'}\n"
        f"Notes: {anchor['notes'] or '—'}"
    ) if anchor else "(no linked contact on file for this client)"
    onboarding_text = "\n\n".join(
        f"## {row['section']}\n{json.dumps(row['answers'], indent=2)}" for row in onboarding
    ) or "(no onboarding form completed yet)"

    prompt = _PROMPT_TEMPLATE.format(
        client_info=client_info, anchor_info=anchor_info,
        onboarding_text=onboarding_text, uploads_text=uploads_text,
    )

    api_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5")
    response = await asyncio.to_thread(
        api_client.messages.create,
        model=model, max_tokens=2500, messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()
