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

            CREATE TABLE IF NOT EXISTS clients (
                id               SERIAL PRIMARY KEY,
                name             TEXT NOT NULL,
                contact_name     TEXT,
                email            TEXT,
                phone            TEXT,
                status           TEXT NOT NULL DEFAULT 'active',
                portal_token     TEXT UNIQUE NOT NULL,
                token_revoked_at TIMESTAMPTZ,
                notes            TEXT,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_portal_token ON clients(portal_token);

            CREATE TABLE IF NOT EXISTS client_onboarding_responses (
                id           SERIAL PRIMARY KEY,
                client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                section      TEXT NOT NULL,
                answers      JSONB NOT NULL DEFAULT '{}',
                completed_at TIMESTAMPTZ,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(client_id, section)
            );

            CREATE TABLE IF NOT EXISTS crm_custom_statuses (
                id          SERIAL PRIMARY KEY,
                key         TEXT UNIQUE NOT NULL,
                label       TEXT NOT NULL,
                color       TEXT NOT NULL DEFAULT '#3a7bd5',
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS onboarding_videos (
                id          SERIAL PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT,
                embed_url   TEXT NOT NULL,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                active      BOOLEAN NOT NULL DEFAULT true,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS ad_campaign_stats (
                id          SERIAL PRIMARY KEY,
                client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                platform    TEXT NOT NULL DEFAULT 'meta',
                stat_date   DATE NOT NULL,
                spend       NUMERIC(10,2),
                impressions INTEGER,
                clicks      INTEGER,
                leads       INTEGER,
                raw         JSONB,
                synced_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(client_id, platform, stat_date)
            );

            CREATE TABLE IF NOT EXISTS onboarding_action_items (
                id          SERIAL PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT,
                link_tab    TEXT,
                link_url    TEXT,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                active      BOOLEAN NOT NULL DEFAULT true,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS client_action_item_completions (
                id             SERIAL PRIMARY KEY,
                client_id      INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                action_item_id INTEGER NOT NULL REFERENCES onboarding_action_items(id) ON DELETE CASCADE,
                completed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(client_id, action_item_id)
            );

            -- The agency's own launch-readiness checklist, shown read-only on
            -- the client portal's "To Do" tab (separate from the onboarding
            -- "Next Steps" checklist above, which the CLIENT completes).
            -- Completion here is set by DigiGrowth staff on a per-client
            -- basis (client_launch_checklist_status below), since these are
            -- tasks the agency does for the client, not tasks the client
            -- does themselves.
            CREATE TABLE IF NOT EXISTS launch_checklist_items (
                id          SERIAL PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT,
                phase       TEXT NOT NULL DEFAULT 'prelaunch',
                sort_order  INTEGER NOT NULL DEFAULT 0,
                active      BOOLEAN NOT NULL DEFAULT true,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS client_launch_checklist_status (
                id           SERIAL PRIMARY KEY,
                client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                item_id      INTEGER NOT NULL REFERENCES launch_checklist_items(id) ON DELETE CASCADE,
                completed_at TIMESTAMPTZ,
                UNIQUE(client_id, item_id)
            );

            CREATE TABLE IF NOT EXISTS watch_videos (
                id           SERIAL PRIMARY KEY,
                slug         TEXT UNIQUE NOT NULL,
                title        TEXT,
                github_path  TEXT NOT NULL,
                file_type    TEXT NOT NULL DEFAULT 'video/mp4',
                file_size    BIGINT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            -- Unified view-tracking log for both the website VSL (Vimeo) and
            -- self-hosted outreach ("loom") videos — see content_tracking.py.
            CREATE TABLE IF NOT EXISTS content_view_events (
                id          SERIAL PRIMARY KEY,
                source      TEXT NOT NULL,
                content_key TEXT NOT NULL,
                contact_id  TEXT REFERENCES contacts(id) ON DELETE SET NULL,
                session_id  TEXT,
                event_type  TEXT NOT NULL,
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
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
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_enrolled_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_anchor_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_touch1_sent_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_touch2_sent_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_touch3_sent_at TIMESTAMPTZ;
            ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            -- Excludes automated sequence sends (no_show/cancel/dm_followup/
            -- reminder) from outreach-volume analytics -- those aren't fresh
            -- outreach, they're follow-up on an existing relationship. See
            -- routers/sms.py::_store_message and integrations.py::gmail_send.
            ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS is_automated BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS is_automated BOOLEAN NOT NULL DEFAULT false;
            -- When each stage checkbox was actually set (see
            -- email_inbox.py::set_contact_stage) -- lets analytics.py narrow
            -- these to a period accurately instead of the phone-was-contacted
            -- proxy it used before these existed.
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_replied_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_dm_reached_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_primed_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_engaged_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS stage_interested_at TIMESTAMPTZ;
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
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS cancel_touch1_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS cancel_touch2_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS cancel_touch3_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS cancel_touch4_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS cancel_sequence_stopped_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS no_show_call_reminder_created_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS cancel_call_reminder_created_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS reminders_stopped_at TIMESTAMPTZ;
            ALTER TABLE sms_sequences ADD COLUMN IF NOT EXISTS gatekeeper TEXT;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS outcome_close_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS outcome_notes TEXT;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS onboarding_kickoff_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS onboarding_followup_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS client_booking_notification_sent_at TIMESTAMPTZ;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_client_anchor BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
            ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
            ALTER TABLE onboarding_action_items ADD COLUMN IF NOT EXISTS link_tab TEXT;
            ALTER TABLE onboarding_action_items ADD COLUMN IF NOT EXISTS link_url TEXT;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS calendly_url TEXT;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS booking_notification_enabled BOOLEAN NOT NULL DEFAULT true;
            ALTER TABLE watch_videos ADD COLUMN IF NOT EXISTS contact_id TEXT REFERENCES contacts(id) ON DELETE SET NULL;
            CREATE INDEX IF NOT EXISTS idx_content_view_events_lookup ON content_view_events (source, content_key, contact_id);
        """)
        # One-time cleanup: an earlier deploy briefly seeded these 6 rows
        # into onboarding_action_items (the client-completed "Next Steps"
        # checklist) by mistake — they belong in launch_checklist_items (the
        # agency-completed "To Do" checklist) below instead. Matched by exact
        # title; harmless no-op once removed / if never present.
        await conn.execute(
            """
            DELETE FROM onboarding_action_items WHERE title IN (
                'Set up client portal', 'Set up email marketing', 'Set up SMS marketing',
                'Set up response AI', 'Create landing page', 'Create paid ad creatives'
            )
            """
        )
        # Seed the default Prelaunch launch checklist once, on a fresh table
        # only — never re-runs once any item exists, so it won't clobber
        # items an admin has since edited/deleted/reordered.
        await conn.execute(
            """
            INSERT INTO launch_checklist_items (title, phase, sort_order)
            SELECT title, 'prelaunch', ord FROM (VALUES
                ('Set up client portal', 0),
                ('Set up email marketing', 1),
                ('Set up SMS marketing', 2),
                ('Set up response AI', 3),
                ('Create landing page', 4),
                ('Create paid ad creatives', 5)
            ) AS seed(title, ord)
            WHERE NOT EXISTS (SELECT 1 FROM launch_checklist_items)
            """
        )
        # Real clients' portals must never touch DigiGrowth's own shared
        # Twilio/Gmail credentials (real calling, real SMS/email send) — only
        # a client explicitly flagged is_test can. Backfill the one
        # pre-existing self-test client by name; idempotent (WHERE NOT
        # is_test), safe to run every startup.
        await conn.execute(
            "UPDATE clients SET is_test = true WHERE name = 'DigiGrowth Test' AND NOT is_test"
        )
        # Same "stub what needs real per-client credentials" pattern as
        # Twilio/Gmail: no real client has connected their own Calendly yet,
        # so calendly_url stays NULL for everyone except the self-test
        # client, which reuses DigiGrowth's own internal Calendly (the
        # same CALENDLY_URL the OS's BookingModal.jsx uses) since it's
        # Dylan's own account either way. Idempotent, safe every startup.
        await conn.execute(
            "UPDATE clients SET calendly_url = 'https://calendly.com/dylanrg-digigrowthllc/30min' "
            "WHERE name = 'DigiGrowth Test' AND calendly_url IS NULL"
        )
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sms_messages_stage ON sms_messages(stage) WHERE stage IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_email_messages_tracking_token ON email_messages(tracking_token) WHERE tracking_token IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sms_sequences_single_default ON sms_sequences (is_default) WHERE is_default;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cold_call_scripts_single_default ON cold_call_scripts (is_default) WHERE is_default;
            CREATE INDEX IF NOT EXISTS idx_contacts_client ON contacts(client_id) WHERE client_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_sms_conversations_client ON sms_conversations(client_id) WHERE client_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_email_conversations_client ON email_conversations(client_id) WHERE client_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_ad_campaign_stats_client ON ad_campaign_stats(client_id, stat_date);
        """)
        # One-time migration: the old single-value 'interested' disposition becomes
        # the new stage_interested checkbox (manually set, since a human set it).
        await conn.execute("""
            UPDATE sms_conversations
            SET stage_interested = true, stage_interested_manual = true, disposition = NULL
            WHERE disposition = 'interested'
        """)
        # One-time cleanup: the DM Follow-Up sequence's enrollment gate
        # (dm_followup_enrolled_at) shipped 12 minutes after the sequence
        # itself, so the ungated poller ran at least once and could have set
        # anchor/touch state (even sent Touch 1) on pre-existing DM-Reached
        # conversations that were never actually enrolled. Clear that leftover
        # state so a later legitimate re-enrollment (unchecking/rechecking DM
        # Reached) starts from a clean slate instead of inheriting stale
        # timestamps that could make Touch 2/3 fire early. Idempotent and
        # permanently safe to leave here — current code can never produce
        # anchor/touch state on an unenrolled row, so this only ever matches
        # that one historical window.
        await conn.execute("""
            UPDATE sms_conversations
            SET dm_followup_anchor_at = NULL, dm_followup_touch1_sent_at = NULL,
                dm_followup_touch2_sent_at = NULL, dm_followup_touch3_sent_at = NULL
            WHERE dm_followup_enrolled_at IS NULL AND dm_followup_anchor_at IS NOT NULL
        """)
        # One-time backfill: is_automated didn't exist until every automated
        # sequence module already had weeks of send history, so every one of
        # those historical rows defaulted to is_automated=false and kept
        # inflating Total Outreach even after the exclusion shipped (a rep
        # correctly reported "still says 92" right after this went live).
        # Each sequence's stage tag is a reliable, already-unique fingerprint
        # for which rows are automated — see no_show_sequence.py/
        # cancel_sequence.py/dm_followup_sequence.py/reminder_engine.py's
        # _send_touch()/_send_instance() calls for the exact tag patterns.
        # Idempotent — only ever touches rows still (incorrectly) false.
        await conn.execute("""
            UPDATE sms_messages
            SET is_automated = true
            WHERE NOT is_automated AND (
                stage LIKE 'no_show_touch%' OR stage LIKE 'cancel_touch%' OR
                stage LIKE 'dm_followup_touch%' OR stage LIKE 'reminder_%' OR
                stage = 'reschedule_confirmation'
            )
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
        # One-time seed: email stats reset floor, requested 2026-09-01 after
        # historical email data turned out to be unreliable — email analytics
        # (routers/analytics.py::_email_metrics) now clamp `since` to this
        # date, so "All Time" effectively means "since this date" going
        # forward instead of true all-time. ON CONFLICT DO NOTHING makes this
        # genuinely one-time: it sets the floor to "yesterday" the first time
        # this migration runs and is never overwritten by a later deploy.
        await conn.execute("""
            INSERT INTO dialer_settings (key, value, updated_at)
            VALUES ('email_stats_reset_at', to_char(date_trunc('day', now() - interval '1 day'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), now())
            ON CONFLICT (key) DO NOTHING
        """)
