"""
Claude API cost per client (2026-11-22).

Every Claude call the OS makes on a client's behalf (text agent, DM agent,
follow-up / reactivation texts, lesson analysis, patient intake, booking
autofill, auto-setup, campaign reports) calls record() with the response.
The API reports the exact tokens it billed (input, output incl. thinking,
cache reads, cache writes); those are priced at the model's list rate and
stored in client_ai_usage. finance_auto.post_client_costs posts the monthly
sum to the client's ledger as "Claude AI (actual)".

The client comes from the explicit client_id, else from the client() scope
set by the caller (for helpers that don't take a client id). A call with no
client is not recorded: it's DigiGrowth's own (cold outreach, Blueprints,
the EA), not a client cost. Recording never raises into the agent.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from db import get_pool

_current: ContextVar[int | None] = ContextVar("ai_usage_client", default=None)

# $ per 1M tokens: (input, output, cache read). Cache writes (5-minute) bill
# at 1.25x input. Source: Anthropic list prices (claude-api skill, 2026-11).
PRICES = {
    "claude-opus-5-5":   (4.00, 20.00, 0.20),
    "claude-opus-5":     (5.00, 25.00, 0.50),
    "claude-opus-4-8":   (5.00, 25.00, 0.50),
    "claude-opus-4-7":   (5.00, 25.00, 0.50),
    "claude-opus-4-6":   (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-sonnet-5":   (2.00, 10.00, 0.20),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30),
    "claude-haiku-5-5":  (0.10, 0.50, 0.01),
    "claude-haiku-4-5":  (1.00, 5.00, 0.10),
    "claude-fable-5-2":  (8.00, 40.00, 0.20),
}
_FALLBACK = "claude-opus-5"  # unknown model: price high rather than low


@contextmanager
def client(client_id: int | None):
    """Attribute every Claude call inside this block to client_id."""
    token = _current.set(client_id)
    try:
        yield
    finally:
        _current.reset(token)


def _price(model: str) -> tuple[tuple[float, float, float], bool]:
    m = (model or "").lower()
    for key in sorted(PRICES, key=len, reverse=True):  # longest first: opus-5-5 before opus-5
        if m.startswith(key):
            return PRICES[key], True
    return PRICES[_FALLBACK], False


def cost_usd(model: str, usage) -> float:
    (p_in, p_out, p_read), _ = _price(model)
    g = lambda k: int(getattr(usage, k, 0) or 0)
    return (g("input_tokens") * p_in + g("output_tokens") * p_out
            + g("cache_read_input_tokens") * p_read
            + g("cache_creation_input_tokens") * p_in * 1.25) / 1_000_000


async def ensure_schema(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS client_ai_usage (
            id            BIGSERIAL PRIMARY KEY,
            client_id     INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            feature       TEXT NOT NULL,
            model         TEXT,
            input_tokens  INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cache_read    INTEGER NOT NULL DEFAULT 0,
            cache_write   INTEGER NOT NULL DEFAULT 0,
            cost_usd      NUMERIC(12,6) NOT NULL DEFAULT 0,
            priced        BOOLEAN NOT NULL DEFAULT true,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_client_ai_usage_client ON client_ai_usage(client_id, created_at);
    """)


async def record(response, feature: str, client_id: int | None = None) -> None:
    cid = client_id if client_id is not None else _current.get()
    usage = getattr(response, "usage", None)
    if not cid or usage is None:
        return
    try:
        model = getattr(response, "model", "") or ""
        _, known = _price(model)
        g = lambda k: int(getattr(usage, k, 0) or 0)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO client_ai_usage (client_id, feature, model, input_tokens, output_tokens,
                                                cache_read, cache_write, cost_usd, priced)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                int(cid), feature, model, g("input_tokens"), g("output_tokens"),
                g("cache_read_input_tokens"), g("cache_creation_input_tokens"), cost_usd(model, usage), known,
            )
    except Exception as e:  # noqa: BLE001 - cost tracking must never break an agent
        print(f"[ai_usage] record failed ({feature}, client {cid}): {e}", flush=True)
