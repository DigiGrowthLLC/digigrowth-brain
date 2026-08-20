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
                follow_up_at TIMESTAMPTZ,
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

            CREATE TABLE IF NOT EXISTS email_messages (
                id               SERIAL PRIMARY KEY,
                contact_id       TEXT REFERENCES contacts(id) ON DELETE CASCADE,
                thread_id        TEXT NOT NULL,
                email            TEXT NOT NULL,
                direction        TEXT NOT NULL,
                subject          TEXT,
                body             TEXT NOT NULL,
                gmail_message_id TEXT UNIQUE NOT NULL,
                sent_at          TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS email_conversations (
                id           SERIAL PRIMARY KEY,
                contact_id   TEXT REFERENCES contacts(id) ON DELETE CASCADE,
                thread_id    TEXT UNIQUE NOT NULL,
                email        TEXT NOT NULL,
                subject      TEXT,
                status       TEXT NOT NULL DEFAULT 'active',
                disposition  TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_read_at TIMESTAMPTZ
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
            CREATE INDEX IF NOT EXISTS idx_email_messages_thread ON email_messages(thread_id);
            CREATE INDEX IF NOT EXISTS idx_email_messages_contact ON email_messages(contact_id);
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

            CREATE TABLE IF NOT EXISTS dialer_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS sms_sequences (
                id                 SERIAL PRIMARY KEY,
                name               TEXT NOT NULL,
                category           TEXT NOT NULL DEFAULT 'General',
                is_default         BOOLEAN NOT NULL DEFAULT false,
                curiosity_opener   TEXT,
                relevance          TEXT,
                guarantee          TEXT,
                ask                TEXT,
                cta                TEXT,
                created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS cold_call_scripts (
                id         SERIAL PRIMARY KEY,
                name       TEXT NOT NULL,
                category   TEXT NOT NULL DEFAULT 'General',
                is_default BOOLEAN NOT NULL DEFAULT false,
                opener     TEXT,
                intro      TEXT,
                main_body  TEXT,
                close      TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id         SERIAL PRIMARY KEY,
                channel    TEXT NOT NULL,
                name       TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS campaign_periods (
                id          SERIAL PRIMARY KEY,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                ended_at    TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_campaigns_channel ON campaigns(channel);
            CREATE INDEX IF NOT EXISTS idx_campaign_periods_campaign ON campaign_periods(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_periods_active ON campaign_periods(campaign_id) WHERE ended_at IS NULL;

            CREATE TABLE IF NOT EXISTS tags (
                id         SERIAL PRIMARY KEY,
                name       TEXT UNIQUE NOT NULL,
                color      TEXT NOT NULL DEFAULT '#3a7bd5',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS pending_approvals (
                id         SERIAL PRIMARY KEY,
                kind       TEXT NOT NULL,
                title      TEXT NOT NULL,
                summary    TEXT,
                payload    JSONB NOT NULL DEFAULT '{}',
                status     TEXT NOT NULL DEFAULT 'pending',
                result     TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                decided_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_pending_approvals_status ON pending_approvals(status);

            CREATE TABLE IF NOT EXISTS newsletter_send_queue (
                id          SERIAL PRIMARY KEY,
                approval_id INTEGER REFERENCES pending_approvals(id) ON DELETE SET NULL,
                contact_id  TEXT REFERENCES contacts(id) ON DELETE CASCADE,
                email       TEXT NOT NULL,
                subject     TEXT NOT NULL,
                html        TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'queued',
                error       TEXT,
                queued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                sent_at     TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_newsletter_queue_status ON newsletter_send_queue(status);

            CREATE TABLE IF NOT EXISTS newsletter_queue_state (
                id     BOOLEAN PRIMARY KEY DEFAULT true CHECK (id),
                paused BOOLEAN NOT NULL DEFAULT false
            );
            INSERT INTO newsletter_queue_state (id, paused) VALUES (true, false) ON CONFLICT (id) DO NOTHING;

            CREATE TABLE IF NOT EXISTS appointment_reminders (
                id                   SERIAL PRIMARY KEY,
                contact_id           TEXT REFERENCES contacts(id) ON DELETE CASCADE,
                prospect_name        TEXT,
                prospect_phone       TEXT,
                prospect_email       TEXT,
                appointment_at       TIMESTAMPTZ NOT NULL,
                prospect_timezone    TEXT NOT NULL,
                status               TEXT NOT NULL DEFAULT 'scheduled',
                confirmation_sent_at TIMESTAMPTZ,
                reminder_24h_sent_at TIMESTAMPTZ,
                reminder_6h_sent_at  TIMESTAMPTZ,
                reminder_1h_sent_at  TIMESTAMPTZ,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_appointment_reminders_at ON appointment_reminders(appointment_at);
            CREATE INDEX IF NOT EXISTS idx_appointment_reminders_status ON appointment_reminders(status);
        """)
        # Migrate existing deployments — no-op if column already exists
        await conn.execute("""
            ALTER TABLE transactions ADD COLUMN IF NOT EXISTS plaid_category TEXT;
            ALTER TABLE transactions ADD COLUMN IF NOT EXISTS recurring_id INTEGER REFERENCES recurring_transactions(id) ON DELETE SET NULL;
            ALTER TABLE todos ADD COLUMN IF NOT EXISTS due_date DATE;
            ALTER TABLE todos ADD COLUMN IF NOT EXISTS recurrence TEXT;
            ALTER TABLE todos ADD COLUMN IF NOT EXISTS description TEXT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS doc_type TEXT NOT NULL DEFAULT 'sop';
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS follow_up_at TIMESTAMPTZ;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_name TEXT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_type TEXT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_size BIGINT;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS file_data BYTEA;
            ALTER TABLE sops ADD COLUMN IF NOT EXISTS github_path TEXT;
            ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS direction TEXT NOT NULL DEFAULT 'outbound';
            ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS phone TEXT;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS last_read_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS disposition TEXT;
            ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS stage TEXT;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS email_opted_out BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS email_opted_out_at TIMESTAMPTZ;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS newsletter_opted_out_at TIMESTAMPTZ;
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS tracking_token TEXT;
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ;
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS open_count INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS bounced_at TIMESTAMPTZ;
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_initial_outreach BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_initial_outreach_manual BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_replied BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_replied_manual BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_primed BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_primed_manual BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_engaged BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_engaged_manual BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_dm_reached BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_dm_reached_manual BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_interested BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_interested_manual BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS pending_sms_campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS pending_email_campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS outcome_show TEXT;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS outcome_close TEXT;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS outcome_show_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS no_show_touch1_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS no_show_touch2_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS no_show_touch3_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS no_show_touch4_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS no_show_sequence_stopped_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS reminders_armed_at TIMESTAMPTZ NOT NULL DEFAULT now();
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sms_messages_stage ON sms_messages(stage) WHERE stage IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_email_messages_tracking_token ON email_messages(tracking_token) WHERE tracking_token IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sms_sequences_single_default ON sms_sequences (is_default) WHERE is_default;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cold_call_scripts_single_default ON cold_call_scripts (is_default) WHERE is_default;
        """)
        # One-time migration: the old single-value 'interested' disposition becomes
        # the new stage_interested checkbox (manually set, since a human set it).
        await conn.execute("""
            UPDATE sms_conversations
            SET stage_interested = true, stage_interested_manual = true, disposition = NULL
            WHERE disposition = 'interested'
        """)
        # One-time backfill: mark pre-existing /newsletter/test-send rows (sent
        # before is_test existed) so they retroactively drop out of analytics —
        # otherwise a self-opened diagnostic send keeps skewing open rate even
        # after the fix, since new rows alone wouldn't touch already-recorded ones.
        await conn.execute("""
            UPDATE email_messages em
            SET is_test = true
            FROM contacts c
            WHERE em.contact_id = c.id
              AND c.business = 'Newsletter Test' AND c.owner = 'Test Recipient'
              AND NOT em.is_test
        """)
        # Sync backfill: campaigns.py::assign_contact_campaign now backfills a
        # contact's whole outbound message history into a campaign at assign
        # time, but that only covers assignments made after that fix shipped —
        # conversations tagged before it (CRM campaign_id set, but messages
        # left untouched) need the same sync applied once here. Idempotent —
        # a no-op once every message already matches its conversation's tag.
        await conn.execute("""
            UPDATE sms_messages sm
            SET campaign_id = sc.campaign_id
            FROM sms_conversations sc
            WHERE sm.contact_id = sc.contact_id AND sc.campaign_id IS NOT NULL
              AND sm.direction = 'outbound' AND sm.campaign_id IS DISTINCT FROM sc.campaign_id
        """)
        await conn.execute("""
            UPDATE email_messages em
            SET campaign_id = ec.campaign_id
            FROM email_conversations ec
            WHERE em.contact_id = ec.contact_id AND ec.campaign_id IS NOT NULL
              AND em.direction = 'outbound' AND em.campaign_id IS DISTINCT FROM ec.campaign_id
        """)
        # One-time backfill: stage_initial_outreach didn't exist before this
        # migration, so every conversation that already has an outbound
        # message needs it retroactively set — otherwise campaign analytics
        # (which read this flag, not raw message counts — see
        # analytics.py::_sms_metrics) would show 0 initial outreach for every
        # prospect contacted before this column existed.
        await conn.execute("""
            UPDATE sms_conversations sc
            SET stage_initial_outreach = true
            WHERE NOT stage_initial_outreach
              AND EXISTS (
                  SELECT 1 FROM sms_messages sm
                  WHERE sm.contact_id = sc.contact_id AND sm.direction = 'outbound'
              )
        """)
        # One-time migration: SMS Sequence moved from a single global template
        # (dialer_settings seq_* keys) to the sms_sequences table (multiple
        # named sequences, one default at a time — see routers/sms_sequences.py).
        # Seed the user's existing sequence content as the first row so it
        # isn't lost. Guarded on sms_sequences being empty so this only ever
        # runs once, on first boot after this table was introduced; the old
        # dialer_settings seq_*/sequence_category rows are left in place
        # afterward (unused, harmless).
        existing_sequence_count = await conn.fetchval("SELECT count(*) FROM sms_sequences")
        if existing_sequence_count == 0:
            seq_rows = await conn.fetch(
                "SELECT key, value FROM dialer_settings WHERE key LIKE 'seq_%' OR key = 'sequence_category'"
            )
            seq_values = {r["key"]: r["value"] for r in seq_rows}
            if seq_values:
                await conn.execute(
                    """
                    INSERT INTO sms_sequences
                        (name, category, is_default, curiosity_opener, relevance, guarantee, ask, cta)
                    VALUES ('Default SMS Sequence', $1, true, $2, $3, $4, $5, $6)
                    """,
                    seq_values.get("sequence_category") or "General",
                    seq_values.get("seq_curiosity_opener") or "",
                    seq_values.get("seq_relevance") or "",
                    seq_values.get("seq_guarantee") or "",
                    seq_values.get("seq_ask") or "",
                    seq_values.get("seq_cta") or "",
                )
        # One-time migration: the dialer's Call Script moved from a single
        # global flat 'call_script' key (dialer_settings) to the
        # cold_call_scripts table (multiple named scripts, one default at a
        # time — see routers/cold_call_scripts.py). The old flat script had
        # no section structure, so it's seeded into main_body (the closest
        # fit) rather than split across opener/intro/close. Guarded on
        # cold_call_scripts being empty so this only ever runs once.
        existing_script_count = await conn.fetchval("SELECT count(*) FROM cold_call_scripts")
        if existing_script_count == 0:
            old_script = await conn.fetchval(
                "SELECT value FROM dialer_settings WHERE key = 'call_script'"
            )
            if old_script:
                await conn.execute(
                    """
                    INSERT INTO cold_call_scripts (name, category, is_default, main_body)
                    VALUES ('Default Call Script', 'General', true, $1)
                    """,
                    old_script,
                )
