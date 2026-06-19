import os
import asyncpg

_pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=2, max_size=10)
        await _create_schema(_pool)
    return _pool


async def _create_schema(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id          TEXT PRIMARY KEY,
                business    TEXT,
                owner       TEXT,
                phone       TEXT UNIQUE,
                email       TEXT,
                website     TEXT,
                city        TEXT,
                state       TEXT,
                grade       TEXT,
                opener      TEXT,
                status      TEXT NOT NULL DEFAULT 'new',
                call_attempts INTEGER NOT NULL DEFAULT 0,
                last_called_at TIMESTAMPTZ,
                last_disposition TEXT,
                notes       TEXT,
                newsletter  BOOLEAN NOT NULL DEFAULT false,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS call_logs (
                id           SERIAL PRIMARY KEY,
                contact_id   TEXT REFERENCES contacts(id) ON DELETE CASCADE,
                started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                duration_sec INTEGER,
                disposition  TEXT,
                notes        TEXT
            );

            CREATE TABLE IF NOT EXISTS sms_messages (
                id           SERIAL PRIMARY KEY,
                contact_id   TEXT REFERENCES contacts(id) ON DELETE CASCADE,
                phone        TEXT NOT NULL,
                direction    TEXT NOT NULL,
                body         TEXT NOT NULL,
                sent_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS sms_conversations (
                id           SERIAL PRIMARY KEY,
                contact_id   TEXT REFERENCES contacts(id) ON DELETE CASCADE,
                phone        TEXT UNIQUE NOT NULL,
                messages     JSONB NOT NULL DEFAULT '[]',
                status       TEXT NOT NULL DEFAULT 'active',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS todos (
                id         SERIAL PRIMARY KEY,
                text       TEXT NOT NULL,
                done       BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS agent_messages (
                id         SERIAL PRIMARY KEY,
                agent      TEXT NOT NULL,
                message    TEXT NOT NULL,
                read       BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS agent_chats (
                id         SERIAL PRIMARY KEY,
                agent_id   TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS recurring_transactions (
                id           SERIAL PRIMARY KEY,
                description  TEXT,
                amount       NUMERIC(10,2) NOT NULL,
                is_income    BOOLEAN NOT NULL DEFAULT false,
                category     TEXT DEFAULT 'Uncategorized',
                notes        TEXT,
                frequency    TEXT NOT NULL,
                start_date   DATE NOT NULL,
                end_date     DATE,
                last_applied DATE,
                active       BOOLEAN NOT NULL DEFAULT true,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id                   SERIAL PRIMARY KEY,
                plaid_transaction_id TEXT UNIQUE,
                date                 DATE NOT NULL,
                description          TEXT,
                amount               NUMERIC(10,2) NOT NULL,
                is_income            BOOLEAN NOT NULL DEFAULT false,
                category             TEXT DEFAULT 'Uncategorized',
                plaid_category       TEXT,
                notes                TEXT,
                recurring_id         INTEGER REFERENCES recurring_transactions(id) ON DELETE SET NULL,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS plaid_config (
                id               SERIAL PRIMARY KEY,
                access_token     TEXT NOT NULL,
                item_id          TEXT NOT NULL UNIQUE,
                institution_name TEXT,
                cursor           TEXT,
                last_synced_at   TIMESTAMPTZ,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
            CREATE INDEX IF NOT EXISTS idx_contacts_grade ON contacts(grade);
            CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
            CREATE INDEX IF NOT EXISTS idx_call_logs_contact ON call_logs(contact_id);
            CREATE INDEX IF NOT EXISTS idx_sms_messages_contact ON sms_messages(contact_id);
            CREATE INDEX IF NOT EXISTS idx_agent_chats_agent ON agent_chats(agent_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);

            CREATE TABLE IF NOT EXISTS sops (
                id           SERIAL PRIMARY KEY,
                title        TEXT NOT NULL,
                content      TEXT NOT NULL DEFAULT '',
                category     TEXT NOT NULL DEFAULT 'General',
                visibility   TEXT NOT NULL DEFAULT 'private',
                sort_order   INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_sops_visibility ON sops(visibility);
        """)
        # Migrate existing deployments — no-op if column already exists
        await conn.execute("""
            ALTER TABLE transactions ADD COLUMN IF NOT EXISTS plaid_category TEXT;
            ALTER TABLE transactions ADD COLUMN IF NOT EXISTS recurring_id INTEGER REFERENCES recurring_transactions(id) ON DELETE SET NULL;
            ALTER TABLE todos ADD COLUMN IF NOT EXISTS due_date DATE;
            ALTER TABLE todos ADD COLUMN IF NOT EXISTS recurrence TEXT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS doc_type TEXT NOT NULL DEFAULT 'sop';
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_name TEXT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_type TEXT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_size BIGINT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_data BYTEA;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS github_path TEXT;
        """)
