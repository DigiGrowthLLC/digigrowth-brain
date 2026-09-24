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

            -- Email Handoff sequence state — one row per contact, stamped the
            -- moment a contact's status is set to "email-handoff" (see
            -- routers/crm.py's _fire_email_handoff, fired from every
            -- status-transition site, same as sms-handoff). Mirrors
            -- dm_followup_sequence.py's touch-chaining shape but as a single
            -- one-shot 3-touch sequence (no restart-on-new-silence-cycle
            -- logic — a contact only ever gets enrolled once). Reply
            -- detection for stopping remaining touches is computed live
            -- against email_messages/email_conversations, not trusted from
            -- stage_replied alone, same reasoning as the SMS sequence.
            CREATE TABLE IF NOT EXISTS email_handoff_state (
                contact_id            TEXT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
                enrolled_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
                touch1_sent_at        TIMESTAMPTZ,
                touch2_sent_at        TIMESTAMPTZ,
                touch3_sent_at        TIMESTAMPTZ,
                stage_replied         BOOLEAN NOT NULL DEFAULT false,
                stage_replied_manual  BOOLEAN NOT NULL DEFAULT false,
                stage_replied_at      TIMESTAMPTZ,
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
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

            -- Personalized cold-outreach landing-page mockups (design-agent's
            -- landing-page-lead-magnet skill). HTML is stored directly (a rendered
            -- page is a few KB — unlike watch_videos, no R2 needed for it);
            -- the hero screenshot/mockup image still goes through R2 since it
            -- needs a real og:image URL for the rich link-preview card.
            CREATE TABLE IF NOT EXISTS landing_pages (
                slug         TEXT PRIMARY KEY,
                contact_id   TEXT REFERENCES contacts(id) ON DELETE SET NULL,
                business     TEXT,
                html         TEXT NOT NULL,
                hero_r2_key  TEXT,
                status       TEXT NOT NULL DEFAULT 'draft',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                approved_at  TIMESTAMPTZ,
                sent_at      TIMESTAMPTZ
            );

            -- Per-client outreach copy (Appointment Reminder / No Show /
            -- Cancellation sequences) shown read-only on the client portal's
            -- Sequences tab, edited by DigiGrowth staff from the Clients
            -- admin panel. Not wired to any real SMS/email send yet — see
            -- routers/client_portal.py's Sequences endpoints.
            CREATE TABLE IF NOT EXISTS client_sequence_steps (
                id          SERIAL PRIMARY KEY,
                client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                sequence_key TEXT NOT NULL,
                step_order  INTEGER NOT NULL DEFAULT 0,
                label       TEXT NOT NULL,
                channel     TEXT NOT NULL,
                subject     TEXT,
                body        TEXT NOT NULL,
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            -- Free-text "please fix/do this" requests a client submits from
            -- their portal's To Do tab, surfaced to DigiGrowth staff in the
            -- Clients admin panel.
            CREATE TABLE IF NOT EXISTS client_requests (
                id           SERIAL PRIMARY KEY,
                client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                message      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'open',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                resolved_at  TIMESTAMPTZ
            );

            -- Metadata for files a client uploads via the portal's Upload
            -- tab. The bytes themselves never touch Railway — they go
            -- straight from the client's browser to Cloudflare R2 via a
            -- presigned URL (see r2_storage.py); this table only tracks
            -- what's there and where.
            CREATE TABLE IF NOT EXISTS client_uploads (
                id           SERIAL PRIMARY KEY,
                client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                file_name    TEXT NOT NULL,
                file_type    TEXT,
                file_size    BIGINT,
                r2_key       TEXT NOT NULL UNIQUE,
                notes        TEXT,
                uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        # Migrate existing deployments — no-op if column already exists
        await conn.execute("""
            ALTER TABLE transactions ADD COLUMN IF NOT EXISTS plaid_category TEXT;
            ALTER TABLE transactions ADD COLUMN IF NOT EXISTS recurring_id INTEGER REFERENCES recurring_transactions(id) ON DELETE SET NULL;
            ALTER TABLE todos ADD COLUMN IF NOT EXISTS due_date DATE;
            ALTER TABLE todos ADD COLUMN IF NOT EXISTS due_time TEXT;
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
            -- Cached MX-lookup result (see email_identities.detect_provider) so
            -- email_handoff_sequence.py doesn't re-query DNS every 5-min poll.
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS email_provider TEXT;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS email_provider_checked_at TIMESTAMPTZ;
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
            -- Permanent, never-cleared record of whether each touch has EVER
            -- been sent to this conversation -- unlike the *_sent_at columns
            -- above (which dm_followup_sequence.py resets to NULL every time
            -- a new silence cycle starts, so the cycle-relative send timing
            -- can restart), these three never get cleared. Lets a prospect
            -- re-enter the sequence (go quiet again after replying) without
            -- ever receiving the same touch twice. See dm_followup_sequence.py.
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_touch1_ever_sent_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_touch2_ever_sent_at TIMESTAMPTZ;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS dm_followup_touch3_ever_sent_at TIMESTAMPTZ;
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
            ALTER TABLE watch_videos ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
            ALTER TABLE content_view_events ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
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
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS client_no_show_sequence_sent_at TIMESTAMPTZ;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS client_cancel_sequence_sent_at TIMESTAMPTZ;
            -- Per-step progress for the client-branded no_show/cancellation
            -- drips (client_appointment_sequence.py), same shape as
            -- reminder_steps_sent below — keyed by client_sequence_steps.
            -- step_order as a string. Replaces the single sent_at columns
            -- above (kept, unused going forward) now that these are real
            -- 3-touch drips instead of one-shot sends.
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS client_no_show_steps_sent JSONB NOT NULL DEFAULT '{}';
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS client_cancel_steps_sent JSONB NOT NULL DEFAULT '{}';
            UPDATE appointment_reminders SET client_no_show_steps_sent =
                jsonb_build_object('0', client_no_show_sequence_sent_at, '1', client_no_show_sequence_sent_at)
                WHERE client_no_show_sequence_sent_at IS NOT NULL AND client_no_show_steps_sent = '{}';
            UPDATE appointment_reminders SET client_cancel_steps_sent =
                jsonb_build_object('0', client_cancel_sequence_sent_at, '1', client_cancel_sequence_sent_at)
                WHERE client_cancel_sequence_sent_at IS NOT NULL AND client_cancel_steps_sent = '{}';
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_client_anchor BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
            ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
            ALTER TABLE onboarding_action_items ADD COLUMN IF NOT EXISTS link_tab TEXT;
            ALTER TABLE onboarding_action_items ADD COLUMN IF NOT EXISTS link_url TEXT;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS calendly_url TEXT;
            -- Agency-level sales KPIs (Dylan's own pipeline only) -- entered
            -- on the appointment disposition screen alongside outcome_close,
            -- replacing the Google-Sheet-sourced sales_stats.json fields.
            -- See routers/appointments.py's PATCH handler and
            -- routers/analytics.py's OS-native sales computation.
            ALTER TABLE appointment_reminders DROP COLUMN IF EXISTS deal_value;
            ALTER TABLE appointment_reminders DROP COLUMN IF EXISTS is_strategy_session;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS pricing NUMERIC;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS call_length TEXT;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS booking_notification_enabled BOOLEAN NOT NULL DEFAULT true;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS ads_manager_resource TEXT;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS registrar_resource TEXT;
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS hosting_resource TEXT;
            CREATE TABLE IF NOT EXISTS client_resources (
                id         SERIAL PRIMARY KEY,
                client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                label      TEXT NOT NULL,
                value      TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            -- Websites/funnels built for a client (e.g. a Meta-ads funnel
            -- deployed via the funnel-building skill) — shown in that
            -- client's own portal under a "Website" tab. View/conversion
            -- stats are read from content_view_events (source=
            -- 'client_website', content_key = this row's id as text) rather
            -- than a dedicated events table, reusing the same tracking
            -- pipeline the VSL/outreach-video funnels already use.
            CREATE TABLE IF NOT EXISTS client_websites (
                id         SERIAL PRIMARY KEY,
                client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                label      TEXT NOT NULL,
                url        TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            ALTER TABLE watch_videos ADD COLUMN IF NOT EXISTS contact_id TEXT REFERENCES contacts(id) ON DELETE SET NULL;
            ALTER TABLE watch_videos ALTER COLUMN github_path DROP NOT NULL;
            ALTER TABLE watch_videos ADD COLUMN IF NOT EXISTS r2_key TEXT;
            CREATE INDEX IF NOT EXISTS idx_content_view_events_lookup ON content_view_events (source, content_key, contact_id);
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS guide_progress JSONB NOT NULL DEFAULT '{}';
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS gmail_refresh_token TEXT;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS gmail_sender_email TEXT;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS email_sync_last_ts BIGINT NOT NULL DEFAULT 0;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS response_ai_enabled BOOLEAN NOT NULL DEFAULT false;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS response_ai_context TEXT;
            -- Ordered array of short stage descriptions ("first text" through
            -- "fifth text" in the admin UI) — a loose conversational arc the
            -- agent tries to progress through, not a rigid state machine (it
            -- still answers off-script questions first). See response_ai.py.
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS response_ai_sequence JSONB NOT NULL DEFAULT '[]';
            -- Guardrails: 0 delay / NULL max_words = no limit. response_ai_max_chars
            -- (character-based) was replaced by response_ai_max_words (word-based,
            -- reads more naturally for a length rule) before real use — left in
            -- place unused rather than dropped.
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS response_ai_min_delay_seconds INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS response_ai_max_chars INTEGER;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS response_ai_max_words INTEGER;
            -- Freeform "read these before every reply" guardrails, in the
            -- admin's own words — separate from response_ai_context (the
            -- business knowledge) so the two don't get muddled together.
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS response_ai_rules TEXT;
            -- Calendly Personal Access Token, generated by the client (or
            -- Dylan once added as an admin on their account) from their own
            -- Calendly settings — read-only use, see calendly_integration.py.
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS calendly_api_token TEXT;
            -- The specific event type this client's agent should check —
            -- required, not inferred. A token generated by an admin who
            -- manages multiple clients' Calendly accounts (Dylan's own
            -- case: one token sees both his own event types and a client's)
            -- can see event types belonging to OTHER people entirely, so
            -- "just take whichever one comes back first" is unsafe once
            -- more than one client shares that ambiguity. Stores the
            -- client's actual scheduling_url (their public booking link,
            -- e.g. https://calendly.com/name/event-slug) rather than an
            -- opaque Calendly URI, since that's what an admin already has
            -- on hand and can visually verify is the right one.
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS calendly_event_type_url TEXT;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS meta_pixel_id TEXT;
            -- Meta ad account (act_XXXXXXXXX, digits only stored here) and
            -- Facebook Page ID for this client — meta_ads.py's spend sync
            -- reads the former, routers/meta_lead_webhooks.py resolves an
            -- inbound Lead Ads webhook's page_id to a client via the latter.
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS meta_page_id TEXT;
            -- Voice calling for the client portal's "Call" button
            -- (client_dialer.py) — a Twilio Access Token is scoped to one
            -- Account SID + one API Key + one TwiML App SID, none of which
            -- exist per-subaccount until provision_client_number() creates
            -- them (see client_sms.py).
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS twilio_twiml_app_sid TEXT;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS twilio_api_key_sid TEXT;
            ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS twilio_api_key_secret TEXT;
            ALTER TABLE client_email_messages ADD COLUMN IF NOT EXISTS direction TEXT NOT NULL DEFAULT 'outbound';
            ALTER TABLE contacts ADD COLUMN IF NOT EXISTS client_channel_last_read_at TIMESTAMPTZ;
            -- Per-step sent tracking for client_appointment_reminders.py's
            -- scheduled 24h/day-of reminder sends to a CLIENT's own lead
            -- (client_sequence_steps sequence_key='appointment_reminder'),
            -- keyed by that step's step_order as a string (e.g. {"0": "<ts>"}
            -- once the 24h step has gone out). A JSONB map rather than fixed
            -- named columns (unlike reminder_24h/6h/1h_sent_at above) since a
            -- client can have any number of appointment_reminder steps, not
            -- a fixed 3.
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS reminder_steps_sent JSONB NOT NULL DEFAULT '{}';
            -- The Calendly scheduled_event URI a booking came from (NULL for
            -- manually-entered/AI-booked appointments) — lets an inbound
            -- invitee.canceled webhook find and cancel the matching row
            -- instead of requiring a manual cancel. See
            -- routers/calendly_webhooks.py.
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS calendly_event_uri TEXT;
            -- Dylan's own sales-pipeline call artifacts (internal
            -- AppointmentsPanel only, never surfaced in the client portal):
            -- a pasted link to the call recording, and a link to the
            -- discovery/question form Dylan filled out for that specific
            -- prospect. Both free-text URLs, set manually from the outcome
            -- card alongside pricing/call_length.
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS call_recording_url TEXT;
            ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS question_form_url TEXT;
            -- Whether a content_view_events row (a client funnel's page view,
            -- or its eventual booking conversion) is attributable to Meta
            -- (Facebook/Instagram), so a client's Website tab can report
            -- "viewers/bookings from Meta" instead of just total traffic.
            -- 'view' rows get this straight from the browser (fbclid param
            -- or a facebook.com/instagram.com referrer, see the funnel
            -- page's tracking snippet); 'conversion' rows get it from
            -- Calendly's own tracking.utm_content echo, since the actual
            -- booking completes on Calendly's domain, not ours — see
            -- routers/calendly_webhooks.py's _handle_invitee_created.
            ALTER TABLE content_view_events ADD COLUMN IF NOT EXISTS from_meta BOOLEAN;
            -- Fourth single free-text resource field alongside ads_manager/
            -- registrar/hosting (see clients.py's "Per-client resources"
            -- comment) — the client's funnel/landing-page link, promoted
            -- out of the freeform "Other Resources" list into its own field
            -- since every client has at most one of these too.
            ALTER TABLE clients ADD COLUMN IF NOT EXISTS funnel_resource TEXT;
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
        # Seed default PT-oriented sequence copy for any client that has
        # none yet — covers both existing clients (first run after this
        # table shipped) and, going forward, routers/clients.py's
        # create_client() calls the same seed inline for brand-new ones.
        # Never touches a client that already has rows here, so admin edits
        # are never clobbered.
        await conn.execute(
            """
            INSERT INTO client_sequence_steps (client_id, sequence_key, step_order, label, channel, subject, body)
            SELECT c.id, s.sequence_key, s.step_order, s.label, s.channel, s.subject, s.body
            FROM clients c
            CROSS JOIN (VALUES
                ('appointment_reminder', 0, '24 Hour Reminder', 'sms', NULL,
                 'Hi {first_name}, this is a friendly reminder about your physical therapy appointment tomorrow, {date} at {time}, with {business}. Reply CONFIRM to confirm or call us if you need to reschedule.'),
                ('appointment_reminder', 1, 'Day-Of Reminder', 'sms', NULL,
                 'Hi {first_name}, just a reminder — your appointment at {business} is today at {time}. We look forward to seeing you!'),
                ('no_show', 0, 'Touch 1 (SMS)', 'sms', NULL,
                 'Hi {first_name}, we missed you at your appointment today at {business}. No worries — these things happen! Reply here or give us a call to get you rescheduled so we can keep your recovery on track.'),
                ('no_show', 1, 'Touch 1 (Email)', 'email', 'We missed you today',
                 E'Hi {first_name},\n\nWe noticed you weren''t able to make your physical therapy appointment today. Consistency is a big part of recovery, so we''d love to get you back on the schedule as soon as possible.\n\nReply to this email or give us a call whenever works for you.\n\nTalk soon,\n{business}'),
                ('cancellation', 0, 'Touch 1 (SMS)', 'sms', NULL,
                 'Hi {first_name}, we''ve canceled your appointment as requested. Whenever you''re ready to get back to feeling better, just reply here or give us a call to grab a new time.'),
                ('cancellation', 1, 'Touch 1 (Email)', 'email', 'Your appointment has been canceled',
                 E'Hi {first_name},\n\nThis confirms your upcoming appointment with {business} has been canceled.\n\nIf you''d like to reschedule, just reply to this email or call us — we''re happy to find a time that works for you.\n\nTake care,\n{business}')
            ) AS s(sequence_key, step_order, label, channel, subject, body)
            WHERE NOT EXISTS (SELECT 1 FROM client_sequence_steps WHERE client_id = c.id)
            """
        )
        # Backfill Touch 3/Touch 4 steps (step_order 2-5) for existing
        # clients whose no_show/cancellation sequences were seeded before
        # this build, back when they were one-shot (Touch 1 only). The
        # blanket seed above only fires for a client with zero rows, so it
        # never reaches these — this backfill is scoped per sequence_key
        # instead (WHERE NOT EXISTS a step_order=2 row for that specific
        # sequence), and never touches a client who already has Touch 3/4
        # rows (e.g. from an admin edit or a re-run).
        await conn.execute(
            """
            INSERT INTO client_sequence_steps (client_id, sequence_key, step_order, label, channel, subject, body)
            SELECT c.id, s.sequence_key, s.step_order, s.label, s.channel, s.subject, s.body
            FROM clients c
            CROSS JOIN (VALUES
                ('no_show', 2, 'Touch 3 (SMS)', 'sms', NULL,
                 'Hi {first_name}, still happy to get you back on the schedule at {business} whenever works for you — just reply here or give us a call.'),
                ('no_show', 3, 'Touch 3 (Email)', 'email', 'Still here when you''re ready',
                 E'Hi {first_name},\n\nThings come up — no worries at all. Whenever you''re ready to get back on track, just reply to this email or give {business} a call and we''ll find a time that fits.\n\nTalk soon,\n{business}'),
                ('no_show', 4, 'Touch 4 (SMS)', 'sms', NULL,
                 '{first_name}, going to close out your file at {business} unless I hear back — no pressure either way, just let us know.'),
                ('no_show', 5, 'Touch 4 (Email)', 'email', 'Closing your file',
                 E'Hi {first_name},\n\nHaven''t heard back, so we''ll close this out on our end unless we hear from you. If timing''s just been off, no worries at all — reply here or call {business} whenever it opens up.\n\nTake care,\n{business}'),
                ('cancellation', 2, 'Touch 3 (SMS)', 'sms', NULL,
                 'Hi {first_name}, if timing''s better now, still happy to get you a new time at {business} — just reply here or give us a call.'),
                ('cancellation', 3, 'Touch 3 (Email)', 'email', 'Still worth getting back on the schedule?',
                 E'Hi {first_name},\n\nPlans change, that''s normal. If it''s still worth getting back on the schedule at {business}, just reply to this email or give us a call.\n\nTalk soon,\n{business}'),
                ('cancellation', 4, 'Touch 4 (SMS)', 'sms', NULL,
                 '{first_name}, going to close out your file at {business} unless I hear back — no pressure either way, just let us know.'),
                ('cancellation', 5, 'Touch 4 (Email)', 'email', 'Closing your file',
                 E'Hi {first_name},\n\nHaven''t heard back, so we''ll close this out on our end unless we hear from you. If timing''s just been off, no worries at all — reply here or call {business} whenever it opens up.\n\nTake care,\n{business}')
            ) AS s(sequence_key, step_order, label, channel, subject, body)
            WHERE EXISTS (SELECT 1 FROM client_sequence_steps WHERE client_id = c.id AND sequence_key = s.sequence_key)
            AND NOT EXISTS (SELECT 1 FROM client_sequence_steps WHERE client_id = c.id AND sequence_key = s.sequence_key AND step_order = s.step_order)
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
        # One-time cleanup (2026-09-22): DM Follow-Up enrollment used to be
        # tied to the "DM Reached" analytics checkbox — checking/unchecking
        # it was the only way to start/stop the sequence, which forced reps
        # to corrupt analytics just to stop an unwanted cycle. Enrollment is
        # now its own control (POST /inbox/contact/{id}/dm-followup — see
        # dm_followup_sequence.py's module docstring) that refuses to enroll
        # anyone already dispositioned, but that guard only applies to NEW
        # enrollments going forward. Any contact already booked/not-interested
        # under the old coupled logic could still be sitting "enrolled" from
        # before this shipped — this clears that stale enrollment (and any
        # in-flight cycle) for every already-dispositioned row, once.
        await conn.execute("""
            UPDATE sms_conversations
            SET dm_followup_enrolled_at = NULL, dm_followup_anchor_at = NULL,
                dm_followup_touch1_sent_at = NULL, dm_followup_touch2_sent_at = NULL,
                dm_followup_touch3_sent_at = NULL
            WHERE disposition IS NOT NULL AND dm_followup_enrolled_at IS NOT NULL
        """)
        # One-time backfill (2026-09-22): assigning an SMS campaign from the
        # contact card used to only set contacts.pending_sms_campaign_id when
        # the contact had never been texted yet (no sms_conversations row) —
        # a value analytics.py's _sms_metrics never reads at all (it only
        # counts sms_conversations.campaign_id), so the assignment stayed
        # invisible to Analytics indefinitely despite the UI showing it as
        # assigned (labeled "(pending)"). routers/campaigns.py's
        # assign_contact_campaign() now creates that sms_conversations row
        # immediately instead, but only going forward — this backfill applies
        # the same fix to every contact already sitting in that stuck state:
        # for any contact with pending_sms_campaign_id set, a phone on file,
        # and still no sms_conversations row, create one now with campaign_id
        # already set (empty message history — a tracking record, not an
        # enrollment into any send sequence) and clear the pending marker.
        # A contact with pending_sms_campaign_id set but NO phone (e.g. a
        # phone-less Calendly self-booking) has no channel to create this
        # row against and is left as-is — assign_contact_campaign() now
        # refuses that case outright going forward rather than leaving it
        # silently pending, but there's nothing to backfill for one that's
        # already in that state.
        await conn.execute("""
            INSERT INTO sms_conversations (contact_id, phone, campaign_id)
            SELECT c.id, c.phone, c.pending_sms_campaign_id
            FROM contacts c
            WHERE c.pending_sms_campaign_id IS NOT NULL
              AND c.phone IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM sms_conversations sc WHERE sc.contact_id = c.id)
            ON CONFLICT (phone) DO UPDATE SET campaign_id = EXCLUDED.campaign_id, updated_at = now()
        """)
        await conn.execute("""
            UPDATE contacts SET pending_sms_campaign_id = NULL
            WHERE pending_sms_campaign_id IS NOT NULL AND phone IS NOT NULL
        """)
        # One-time backfill for the new "only ever send each touch once"
        # lifetime cap: the *_ever_sent_at columns didn't exist until now, so
        # any touch a prospect already received under the old (resettable)
        # behavior needs to be backfilled as "ever sent" -- otherwise the
        # very first new silence cycle after this ships would treat their
        # already-delivered touches as never-sent and send them again.
        # Idempotent -- only fills rows still NULL.
        await conn.execute("""
            UPDATE sms_conversations
            SET dm_followup_touch1_ever_sent_at = COALESCE(dm_followup_touch1_ever_sent_at, dm_followup_touch1_sent_at),
                dm_followup_touch2_ever_sent_at = COALESCE(dm_followup_touch2_ever_sent_at, dm_followup_touch2_sent_at),
                dm_followup_touch3_ever_sent_at = COALESCE(dm_followup_touch3_ever_sent_at, dm_followup_touch3_sent_at)
            WHERE dm_followup_touch1_sent_at IS NOT NULL OR dm_followup_touch2_sent_at IS NOT NULL
               OR dm_followup_touch3_sent_at IS NOT NULL
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
        # Client marketing infrastructure — deliberately separate from
        # everything above. Everything above (contacts.client_id,
        # sms_conversations, email_messages, campaigns, etc.) is DigiGrowth's
        # own outreach machinery, gated so only an is_test client can touch
        # DigiGrowth's shared Twilio/Gmail credentials. This block is the
        # opposite: it provisions each real client's OWN Twilio number, own
        # email-sending domain, own self-built AI response agent
        # (response_ai.py), own landing page, and own ad creatives —
        # infrastructure that belongs to the client, not to DigiGrowth, and
        # must never share a table or a send credential with the internal
        # outreach system above.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS client_marketing_config (
                client_id              INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
                twilio_subaccount_sid  TEXT,
                twilio_number          TEXT,
                email_subdomain        TEXT,
                email_dns_status       TEXT NOT NULL DEFAULT 'pending',
                gmail_refresh_token    TEXT,
                gmail_sender_email     TEXT,
                landing_page_url       TEXT,
                meta_pixel_id          TEXT,
                ad_creative_status     JSONB NOT NULL DEFAULT '{}',
                updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            -- Outbound/inbound email sent through the CLIENT's own Google
            -- Workspace mailbox (client_marketing_config.gmail_refresh_token),
            -- mirroring email_messages but for the client's own mailbox, never
            -- DigiGrowth's shared one. Inbound rows come from
            -- client_email.py's polling sync (mirrors email_inbox.py's
            -- internal Gmail sync) — to_email holds the other party's
            -- address either way (the send target when outbound, the
            -- sender when inbound), matching client_sms_messages' shape.
            CREATE TABLE IF NOT EXISTS client_email_messages (
                id           SERIAL PRIMARY KEY,
                client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                to_email     TEXT NOT NULL,
                subject      TEXT NOT NULL,
                body         TEXT NOT NULL,
                gmail_message_id TEXT,
                direction    TEXT NOT NULL DEFAULT 'outbound',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_client_email_messages_client ON client_email_messages(client_id, created_at DESC);

            -- Email warm-up ramp state for a client's own mailbox (one row
            -- per client, created on first "Start Warm-Up" click). Sends
            -- made here go to a fixed internal seed list, not real
            -- prospects, so they're logged separately in
            -- client_email_warmup_log rather than client_email_messages —
            -- that table feeds the client portal's Inbox Activity panel and
            -- dashboard/analytics stats, which warm-up noise has no business
            -- appearing in. sent_today/last_sent_date also get bumped by a
            -- REAL send through the same mailbox (see client_email.py's
            -- send_client_email), so real outreach that starts mid-warmup
            -- counts toward that day's ramp target instead of stacking
            -- redundant seed volume on top.
            CREATE TABLE IF NOT EXISTS client_email_warmup (
                client_id      INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
                status         TEXT NOT NULL DEFAULT 'not_started',
                started_at     TIMESTAMPTZ,
                completed_at   TIMESTAMPTZ,
                current_day    INTEGER NOT NULL DEFAULT 0,
                sent_today     INTEGER NOT NULL DEFAULT 0,
                last_sent_date DATE,
                last_sent_at   TIMESTAMPTZ,
                seed_cursor    INTEGER NOT NULL DEFAULT 0,
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS client_email_warmup_log (
                id               SERIAL PRIMARY KEY,
                client_id        INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                day_number       INTEGER NOT NULL,
                to_email         TEXT NOT NULL,
                gmail_message_id TEXT,
                sent_at          TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_client_email_warmup_log_client ON client_email_warmup_log(client_id, sent_at DESC);

            -- The client's own outbound SMS sequence template, shaped like
            -- sms_sequences.py's stage model but intentionally a separate
            -- table — this is the client's message to their own prospects,
            -- never DigiGrowth's.
            CREATE TABLE IF NOT EXISTS client_sms_sequences (
                id                SERIAL PRIMARY KEY,
                client_id         INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                curiosity_opener  TEXT NOT NULL DEFAULT '',
                relevance         TEXT NOT NULL DEFAULT '',
                guarantee         TEXT NOT NULL DEFAULT '',
                ask               TEXT NOT NULL DEFAULT '',
                cta               TEXT NOT NULL DEFAULT '',
                updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(client_id)
            );

            -- Internal (DigiGrowth-owned) cold-outreach email infrastructure
            -- — NOT client-owned, and deliberately separate from
            -- client_marketing_config/client_email_*. These are dedicated
            -- mailboxes on subdomains of digigrowthllc.com used to send the
            -- email_handoff_sequence.py 3-touch sequence, auto-routed per
            -- lead by MX-detecting whether the recipient is Google- or
            -- Microsoft-hosted (see email_identities.py). No fixed count —
            -- rows are added one at a time via the admin UI as mailboxes are
            -- provisioned.
            CREATE TABLE IF NOT EXISTS email_send_identities (
                id                  SERIAL PRIMARY KEY,
                provider            TEXT NOT NULL,              -- 'google' | 'microsoft'
                domain              TEXT NOT NULL,
                mailbox_email       TEXT NOT NULL UNIQUE,
                display_name        TEXT,
                oauth_refresh_token TEXT,
                ms_tenant_id        TEXT,                        -- Microsoft-only
                status              TEXT NOT NULL DEFAULT 'warming',  -- 'warming' | 'active' | 'paused'
                activated_at        TIMESTAMPTZ,
                send_cursor         INTEGER NOT NULL DEFAULT 0,
                email_sync_last_ts  INTEGER NOT NULL DEFAULT 0,  -- inbox-poll cursor, mirrors client_marketing_config.email_sync_last_ts
                created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_email_send_identities_provider_status
                ON email_send_identities(provider, status);

            -- Per-identity warm-up ramp state (mirrors client_email_warmup's
            -- shape, but this engine cross-warms identities against EACH
            -- OTHER with real threaded opener+reply email exchanges instead
            -- of one-way sends to a fixed seed list — see identity_warmup.py).
            CREATE TABLE IF NOT EXISTS identity_warmup (
                identity_id     INTEGER PRIMARY KEY REFERENCES email_send_identities(id) ON DELETE CASCADE,
                status          TEXT NOT NULL DEFAULT 'not_started',  -- 'not_started' | 'running' | 'complete'
                started_at      TIMESTAMPTZ,
                completed_at    TIMESTAMPTZ,
                current_day     INTEGER NOT NULL DEFAULT 0,
                sent_today      INTEGER NOT NULL DEFAULT 0,
                replied_today   INTEGER NOT NULL DEFAULT 0,
                last_sent_date  DATE,
                last_sent_at    TIMESTAMPTZ,
                partner_cursor  INTEGER NOT NULL DEFAULT 0,
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS identity_warmup_log (
                id                   SERIAL PRIMARY KEY,
                from_identity_id     INTEGER NOT NULL REFERENCES email_send_identities(id) ON DELETE CASCADE,
                to_identity_id       INTEGER NOT NULL REFERENCES email_send_identities(id) ON DELETE CASCADE,
                day_number           INTEGER NOT NULL,
                direction            TEXT NOT NULL,               -- 'opener' | 'reply'
                thread_key           TEXT NOT NULL,
                provider_message_id  TEXT,
                sent_at              TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_identity_warmup_log_from ON identity_warmup_log(from_identity_id, sent_at DESC);
            CREATE INDEX IF NOT EXISTS idx_identity_warmup_log_thread ON identity_warmup_log(thread_key);

            -- Which identity touch1 sent from, so touch2/3 reuse it for
            -- thread continuity. Added here (not in the earlier ALTER
            -- block) since it references email_send_identities, created
            -- just above in this same statement.
            ALTER TABLE email_handoff_state ADD COLUMN IF NOT EXISTS identity_id INTEGER REFERENCES email_send_identities(id) ON DELETE SET NULL;

            -- Out-of-office/autoresponder inbound (see
            -- email_identities._is_auto_reply) — excluded from the Email
            -- Handoff reply-stop check so an OOO doesn't kill the sequence.
            -- The backfill UPDATE catches OOOs stored before this column
            -- existed; idempotent, cheap (inbound identity rows only).
            ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS is_auto_reply BOOLEAN NOT NULL DEFAULT false;
            UPDATE email_messages SET is_auto_reply = true
            WHERE direction = 'inbound' AND NOT is_auto_reply AND thread_id LIKE 'identity-%'
              AND (subject ~* '^\\s*(automatic reply|auto[- ]?reply|autoreply|auto:|out of (the )?office)'
                   OR left(body, 600) ~* 'out of (the )?office|i am currently out|limited access to (my )?e-?mail');

            -- Set when a prospect is pulled out of the Email Handoff sequence
            -- from the Outreach Templates "View Active Prospects" queue
            -- (DELETE /api/dialer/email-handoff-active/{contact_id}).
            -- Re-enrolling clears it. See email_handoff_sequence.enroll().
            ALTER TABLE email_handoff_state ADD COLUMN IF NOT EXISTS stopped_at TIMESTAMPTZ;

            -- Personalized outreach video for the {loom} merge field, built
            -- server-side by outreach_video.py (site screenshot + headcam
            -- bubble -> R2 -> /watch/<slug>). loom_started_at doubles as a
            -- claim so a crashed run is retried after a timeout.
            ALTER TABLE email_handoff_state ADD COLUMN IF NOT EXISTS loom_url TEXT;
            ALTER TABLE email_handoff_state ADD COLUMN IF NOT EXISTS loom_attempts INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE email_handoff_state ADD COLUMN IF NOT EXISTS loom_error TEXT;
            ALTER TABLE email_handoff_state ADD COLUMN IF NOT EXISTS loom_started_at TIMESTAMPTZ;

            -- Email-channel funnel stages, per contact — the Inbox's stage
            -- menu shows these (instead of the SMS stage_* columns on
            -- sms_conversations) while the Email reply channel is selected.
            -- stage_replied NULL = automatic (a real, non-auto-reply inbound
            -- email exists); true/false = a rep's explicit tick. Engaged or
            -- Interested counts as a positive reply in Email analytics.
            CREATE TABLE IF NOT EXISTS email_contact_stages (
                contact_id           TEXT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
                stage_replied        BOOLEAN,
                stage_replied_at     TIMESTAMPTZ,
                stage_engaged        BOOLEAN NOT NULL DEFAULT false,
                stage_engaged_at     TIMESTAMPTZ,
                stage_interested     BOOLEAN NOT NULL DEFAULT false,
                stage_interested_at  TIMESTAMPTZ,
                updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            -- Inbound/outbound SMS sent through the CLIENT's own provisioned
            -- Twilio number (client_marketing_config.twilio_number) — kept
            -- separate from sms_messages, which is DigiGrowth's own number.
            CREATE TABLE IF NOT EXISTS client_sms_messages (
                id           SERIAL PRIMARY KEY,
                client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                from_number  TEXT NOT NULL,
                to_number    TEXT NOT NULL,
                direction    TEXT NOT NULL,
                body         TEXT NOT NULL,
                twilio_sid   TEXT,
                stage        TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_client_sms_messages_client ON client_sms_messages(client_id, created_at DESC);

            -- response_ai.py's per-(client, lead phone) conversation state.
            -- client_sms_messages above is just a flat message log; this is
            -- what tracks whether the AI is still actively handling a thread
            -- ('ai_active'), has handed it to a human ('escalated', e.g. the
            -- lead asked for one or the model wasn't confident), or already
            -- booked the lead ('booked'). response_ai_enabled on
            -- client_marketing_config is the per-client kill switch that
            -- gates whether this whole path runs at all.
            CREATE TABLE IF NOT EXISTS client_lead_conversations (
                id              SERIAL PRIMARY KEY,
                client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                phone           TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'ai_active',
                last_message_at TIMESTAMPTZ,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(client_id, phone)
            );

            -- Per-client manual ledger, mirroring the shape of the agency-wide
            -- `transactions` table above but scoped to one client's own P&L:
            -- what it costs DigiGrowth to deliver/run the campaign (category
            -- 'Ad Spend' plus whatever else) against the revenue that client's
            -- own business generated from it, so client_finance.py can surface
            -- ROAS (revenue / ad spend) per client instead of only agency-wide
            -- income vs. expenses.
            CREATE TABLE IF NOT EXISTS client_transactions (
                id          SERIAL PRIMARY KEY,
                client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                date        DATE NOT NULL,
                description TEXT,
                amount      NUMERIC(10,2) NOT NULL,
                is_income   BOOLEAN NOT NULL DEFAULT false,
                category    TEXT NOT NULL DEFAULT 'Other',
                notes       TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_client_transactions_client ON client_transactions(client_id, date);
        """)
        # Templatize the launch checklist itself: fill in the real,
        # step-by-step setup SOP for SMS/Response AI/Email as each item's
        # description, so "Set up SMS marketing" etc. isn't just a bare
        # checkbox — it's the repeatable playbook. Only fills a NULL/blank
        # description so an admin's later edit via the ClientsPanel editor
        # is never clobbered on a later deploy.
        await conn.execute(
            """
            UPDATE launch_checklist_items SET description = $2
            WHERE title = $1 AND (description IS NULL OR description = '')
            """,
            "Set up SMS marketing",
            "1) Marketing Setup tab -> Buy Number (provisions a dedicated Twilio "
            "subaccount + local number for this client). "
            "2) Register an A2P 10DLC Brand + Campaign for the client's "
            "subaccount in the Twilio console using their real business "
            "name/EIN -- unregistered numbers get filtered/blocked at volume. "
            "3) Confirm the inbound webhook (set automatically on purchase) "
            "points at /webhooks/client-sms/{client_id}. "
            "4) Send yourself a test text to/from the new number; confirm it "
            "shows up via GET /clients/{id}/sms-messages. "
            "5) Once Response AI is connected, confirm it's using this same "
            "number, not one of its own.",
        )
        await conn.execute(
            """
            UPDATE launch_checklist_items SET description = $2
            WHERE title = $1 AND (description IS NULL OR description = '')
            """,
            "Set up response AI",
            "1) Confirm SMS marketing is provisioned first -- this reuses the "
            "client's own Twilio number, it doesn't bring one. "
            "2) Open this client's Agent tab, enable the agent, and write or "
            "generate its context (business info, offer, tone, hours, FAQs, "
            "what to escalate). "
            "3) Fill in the SMS Sequence (5 stage goals) and Rules (reply "
            "delay, max words, freeform rules the agent reads before every "
            "reply). "
            "4) Optional: connect the client's Calendly Personal Access "
            "Token under Calendar so the agent checks real availability "
            "before proposing a time. "
            "5) Test: text the client's number, confirm the agent replies "
            "on-brand, booking a time creates a real appointment, and asking "
            "for a human stops it from auto-replying to that thread.",
        )
        # One-time fix: replace the stale Appointwise-era description on
        # existing installs even though it's already non-blank (the general
        # IS NULL/blank guard above only protects a manually-edited
        # description, and this specific text is now simply wrong, not a
        # customization worth preserving) — narrowly scoped to rows that
        # still contain the literal old text, so a real admin edit that
        # happens not to mention Appointwise is never touched.
        await conn.execute(
            """
            UPDATE launch_checklist_items SET description = $2
            WHERE title = $1 AND description LIKE '%Appointwise%'
            """,
            "Set up response AI",
            "1) Confirm SMS marketing is provisioned first -- this reuses the "
            "client's own Twilio number, it doesn't bring one. "
            "2) Open this client's Agent tab, enable the agent, and write or "
            "generate its context (business info, offer, tone, hours, FAQs, "
            "what to escalate). "
            "3) Fill in the SMS Sequence (5 stage goals) and Rules (reply "
            "delay, max words, freeform rules the agent reads before every "
            "reply). "
            "4) Optional: connect the client's Calendly Personal Access "
            "Token under Calendar so the agent checks real availability "
            "before proposing a time. "
            "5) Test: text the client's number, confirm the agent replies "
            "on-brand, booking a time creates a real appointment, and asking "
            "for a human stops it from auto-replying to that thread.",
        )
        await conn.execute(
            """
            UPDATE launch_checklist_items SET description = $2
            WHERE title = $1 AND (description IS NULL OR description = '')
            """,
            "Set up email marketing",
            "1) Confirm the client has (or buy them) Google Workspace on "
            "their own domain -- this is the real sending mailbox, not "
            "DigiGrowth's Gmail. "
            "2) Locally run reauth_google.py logged into that mailbox to "
            "generate a refresh token. "
            "3) Paste the refresh token and sender email into this client's "
            "Marketing Setup tab. "
            "4) Send a test email from the tab and confirm it lands (check "
            "spam too). "
            "5) Confirm SPF/DKIM/DMARC are set at the client's registrar per "
            "Workspace's setup wizard -- required for real deliverability, "
            "not just for sends to succeed.",
        )
        # One-time cleanup: a since-reverted change briefly seeded "Set up
        # SMS/email automations" / "Verify & hook up analytics" into this
        # (DigiGrowth-agency-run) launch checklist -- they belong as
        # MARKETING_STEPS/MARKETING_GUIDES entries on the client-scoped
        # Marketing Setup tab instead (ClientsPanel.jsx), not here. Removes
        # them if a deploy already ran the old seed; harmless no-op
        # otherwise/afterward.
        await conn.execute(
            "DELETE FROM launch_checklist_items WHERE title IN "
            "('Set up SMS/email automations', 'Verify & hook up analytics')"
        )
        # Replaces the old "give us calendar access" client Next Steps item
        # (asking the client to just hand over calendar access, no
        # instructions) with a clearer, self-service version: add DigiGrowth
        # as a Calendly ADMIN specifically (not a viewer). Matches the same
        # short-row + linked-guide-document pattern as the existing Meta Ads
        # Access item (link_url points at a published guide, not raw steps
        # crammed into description). Matched by the old title so this only
        # ever fires once per environment; once renamed, the old title no
        # longer matches and this becomes a permanent no-op. If no such item
        # exists yet (fresh install, or already renamed to the new title),
        # falls through to inserting it fresh instead.
        _calendly_admin_title = "Add DigiGrowth as a Calendly Admin"
        _calendly_admin_description = (
            "Add us as an Admin on your Calendly account so we can manage your "
            "booking pages and availability directly. Full steps and the exact "
            "link to invite are in the guide below."
        )
        _calendly_admin_guide_url = "https://claude.ai/code/artifact/80eef5cb-766b-4e3b-b539-f4ddfaf09e7b"
        _old_calendar_item = await conn.fetchval(
            "SELECT id FROM onboarding_action_items WHERE title ILIKE '%calendar access%' LIMIT 1"
        )
        if _old_calendar_item:
            await conn.execute(
                "UPDATE onboarding_action_items SET title = $2, description = $3, link_url = $4 WHERE id = $1",
                _old_calendar_item, _calendly_admin_title, _calendly_admin_description, _calendly_admin_guide_url,
            )
        else:
            _already_added = await conn.fetchval(
                "SELECT id FROM onboarding_action_items WHERE title = $1", _calendly_admin_title
            )
            if not _already_added:
                await conn.execute(
                    "INSERT INTO onboarding_action_items (title, description, link_url, sort_order) "
                    "VALUES ($1, $2, $3, 0)",
                    _calendly_admin_title, _calendly_admin_description, _calendly_admin_guide_url,
                )
        # Corrective follow-up: the migration above initially shipped with a
        # long numbered description and a raw calendly.com/app link instead
        # of the short-row + linked-guide pattern above. Matched by that old
        # placeholder link so this is a genuine one-time fix for an
        # environment that already ran the pre-fix version; once corrected,
        # link_url no longer equals the old value and this is a permanent
        # no-op.
        await conn.execute(
            """
            UPDATE onboarding_action_items
            SET description = $2, link_url = $3
            WHERE title = $1 AND link_url = 'https://calendly.com/app'
            """,
            _calendly_admin_title, _calendly_admin_description, _calendly_admin_guide_url,
        )

        # booked_at: a permanent record of "an appointment was booked from
        # this conversation", separate from `disposition`. Analytics'
        # Booked count used to read disposition='booked' directly, but
        # disposition is a single current-status field a rep can overwrite
        # later (e.g. closing a no-show thread as 'not_interested' after
        # the prospect ghosts) — which silently erased that conversation's
        # booked credit even though the appointment genuinely happened.
        # See routers/analytics.py's booked-count queries and
        # routers/appointments.py's booking handler, which now stamps this
        # column instead of relying on disposition alone.
        await conn.execute("ALTER TABLE sms_conversations ADD COLUMN IF NOT EXISTS booked_at TIMESTAMPTZ")
        await conn.execute("ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS booked_at TIMESTAMPTZ")
        # Backfill 0: link an orphaned appointment_reminders row (contact_id
        # NULL) back to the CRM contact it actually belongs to, by exact
        # phone or email match — mirrors the same matching rules
        # calendly_webhooks.py's _handle_invitee_created uses at booking
        # time (Dylan's own pipeline: client_id NULL or is_client_anchor,
        # so a client's own patient is never mis-claimed here). Needed
        # because that matching used to be phone-only; Calendly's default
        # booking form doesn't collect phone, so a known SMS lead who
        # booked without re-entering it got contact_id=NULL forever, with
        # zero way for a later, unrelated app request to fix it after the
        # fact. Runs unconditionally (contact_id IS NULL is naturally
        # idempotent) so it also catches any future case where the phone
        # genuinely wasn't available but the email later gets added to
        # the contact. Caught live 2026-09-19: Blake Overmiller (Precision
        # PT, V.1.4 campaign) booked via Calendly with only his email, and
        # his real, already-texting-with-us contact never got linked.
        await conn.execute(
            """
            UPDATE appointment_reminders ar SET contact_id = c.id
            FROM contacts c
            WHERE ar.contact_id IS NULL
              AND (c.client_id IS NULL OR c.is_client_anchor)
              AND (
                (ar.prospect_phone IS NOT NULL AND ar.prospect_phone <> '' AND c.phone = ar.prospect_phone)
                OR (ar.prospect_email IS NOT NULL AND ar.prospect_email <> '' AND c.email = ar.prospect_email)
              )
            """
        )
        # Backfill 1: conversations currently sitting at disposition='booked'
        # — updated_at is the closest proxy for when that happened, matching
        # how the old disposition-based query was already windowed.
        await conn.execute(
            "UPDATE sms_conversations SET booked_at = updated_at WHERE disposition = 'booked' AND booked_at IS NULL"
        )
        await conn.execute(
            "UPDATE email_conversations SET booked_at = updated_at WHERE disposition = 'booked' AND booked_at IS NULL"
        )
        # Corrective: the first version of backfill 2 below (deployed
        # 2026-09-14) didn't exclude canceled appointments, so a contact
        # whose only appointment_reminders rows are canceled — e.g. the
        # "Dylan"/"Outcome Verification Test" contact used to test the
        # reminder pipeline itself, never a real prospect — got wrongly
        # credited with booked_at. Clear it before backfill 2 re-runs with
        # the status filter added below; a conversation genuinely booked
        # keeps its credit either via disposition='booked' (backfill 1) or
        # a real, non-canceled appointment (backfill 2).
        await conn.execute(
            """
            UPDATE sms_conversations sc SET booked_at = NULL
            WHERE disposition IS DISTINCT FROM 'booked'
              AND EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = sc.contact_id)
              AND NOT EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = sc.contact_id AND ar.status != 'canceled')
            """
        )
        await conn.execute(
            """
            UPDATE email_conversations ec SET booked_at = NULL
            WHERE disposition IS DISTINCT FROM 'booked'
              AND EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = ec.contact_id)
              AND NOT EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = ec.contact_id AND ar.status != 'canceled')
            """
        )
        # Backfill 2 (REMOVED 2026-09-17): used to recover booked_at for any
        # conversation whose contact had a real appointment, regardless of
        # which channel actually booked it. appointment_reminders has no
        # channel column (create_appointment_row() only knows the channel at
        # request time, via payload.get("channel") — it's never persisted),
        # so this blindly stamped BOTH sms_conversations.booked_at AND
        # email_conversations.booked_at for a contact any time either table's
        # row wasn't already 'booked' — crediting appointments booked by
        # phone/Dialer/CRM (channel=None) to whichever conversation threads
        # happened to exist for that contact. Reported live 2026-09-17: email
        # outreach showed 5 "booked" appointments that were never booked
        # through email.
        #
        # Backfill 3 (REPLACED 2026-09-22): tried to avoid backfill 2's
        # mis-credit by only recovering booked_at when the channel was
        # "unambiguous" — contact has a conversation row on exactly one of
        # sms/email — and by requiring disposition == 'booked' or this same
        # unambiguous-appointment evidence before keeping any booked_at. That
        # correctly stopped guessing between two *untagged* channels, but it
        # kept leaving real, campaign-tagged bookings uncredited any time a
        # contact simply had threads on both channels (common — most
        # prospects get both an SMS and an email touch), which is what
        # backfill 2's removal was actually trying to prevent, not a reason
        # to withhold credit. Reported live 2026-09-22 (third time this
        # exact complaint has come up): V.1.4's Analytics count was two
        # appointments short.
        #
        # The rule that actually matches what "campaign booked" should mean:
        # credit is a per-channel fact, not a single either/or guess. Any
        # sms_conversations/email_conversations row that (a) is already
        # tagged with a campaign_id — i.e. the contact card genuinely shows
        # that channel's campaign — and (b) belongs to a contact with a
        # real, non-canceled appointment gets booked_at stamped, full stop.
        # No requirement that the OTHER channel be empty, and no requirement
        # that the thread still be open (a closed thread's booking still
        # really happened — see the 2026-09-19 Louis Walker case below).
        # Runs unconditionally (not "IS NULL"-guarded to a one-shot) so a
        # later real, non-canceled appointment for an already-tracked
        # contact still gets picked up on the next deploy.
        #
        # Deliberately does NOT touch `disposition` — a contact who no-showed
        # and was later dispositioned 'not_interested' keeps that as their
        # current status (that's still true and shouldn't be overwritten
        # back to 'booked'), while booked_at (which Analytics' Booked count
        # actually reads — see routers/analytics.py) still credits the real
        # booking that happened. Caught live 2026-09-19: Louis Walker (Elite
        # Performance PT, V.1.4 campaign) booked, no-showed, was dispositioned
        # not_interested afterward, and lost his booked credit entirely under
        # the old all-or-nothing guard — this stays fixed under the new rule.
        await conn.execute(
            """
            UPDATE sms_conversations sc SET booked_at = COALESCE(booked_at, (
                SELECT MIN(ar.created_at) FROM appointment_reminders ar
                WHERE ar.contact_id = sc.contact_id AND ar.status != 'canceled'
            ))
            WHERE booked_at IS NULL
              AND sc.campaign_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = sc.contact_id AND ar.status != 'canceled')
            """
        )
        await conn.execute(
            """
            UPDATE email_conversations ec SET booked_at = COALESCE(booked_at, (
                SELECT MIN(ar.created_at) FROM appointment_reminders ar
                WHERE ar.contact_id = ec.contact_id AND ar.status != 'canceled'
            ))
            WHERE booked_at IS NULL
              AND ec.campaign_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = ec.contact_id AND ar.status != 'canceled')
            """
        )
        # Corrective guard: clears booked_at whenever disposition isn't
        # 'booked' UNLESS the backfill above just justified it with real,
        # campaign-tagged appointment evidence — same condition as that
        # backfill's WHERE clause, so this never undoes what it just did,
        # only genuine phantom credits left over from the old backfill 2 (or
        # any other unexplained booked_at, e.g. a campaign_id later cleared
        # by contacts/{id}/campaigns' DELETE endpoint after credit was given).
        await conn.execute(
            """
            UPDATE sms_conversations sc SET booked_at = NULL
            WHERE disposition IS DISTINCT FROM 'booked'
              AND booked_at IS NOT NULL
              AND NOT (
                sc.campaign_id IS NOT NULL
                AND EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = sc.contact_id AND ar.status != 'canceled')
              )
            """
        )
        await conn.execute(
            """
            UPDATE email_conversations ec SET booked_at = NULL
            WHERE disposition IS DISTINCT FROM 'booked'
              AND booked_at IS NOT NULL
              AND NOT (
                ec.campaign_id IS NOT NULL
                AND EXISTS (SELECT 1 FROM appointment_reminders ar WHERE ar.contact_id = ec.contact_id AND ar.status != 'canceled')
              )
            """
        )

        # Calendly webhook subscription — real bookings on a Calendly link
        # (Dylan's own, or a client's) push invitee.created events here
        # instead of a rep having to notice the booking and manually create
        # the appointment_reminders row (see routers/calendly_webhooks.py).
        # signing_key is what Calendly hands back at subscription-creation
        # time, used to verify every inbound payload is really from them;
        # webhook_uri is the subscription's own resource URI, kept so it can
        # be looked up/torn down (a client re-clicking "Connect" shouldn't
        # pile up duplicate subscriptions on their Calendly account).
        await conn.execute("ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS calendly_webhook_uri TEXT")
        await conn.execute("ALTER TABLE client_marketing_config ADD COLUMN IF NOT EXISTS calendly_webhook_signing_key TEXT")

        # Seed the two auto-applied lead-source tags calendly_webhooks.py
        # stamps onto a client's leads (ads-lead vs organic-lead, based on
        # the ?utm_source=paid_ad marker on the ad-funnel page's Calendly
        # link) so they render with real colors in the portal's tag chips
        # from the first booking on, instead of falling back to the default
        # blue the first time each name is used.
        await conn.execute("INSERT INTO tags (name, color) VALUES ('ads-lead', '#f5a623') ON CONFLICT (name) DO NOTHING")
        await conn.execute("INSERT INTO tags (name, color) VALUES ('organic-lead', '#4ade80') ON CONFLICT (name) DO NOTHING")

        # Starter tag catalog for database-reactivation imports — a client
        # importing an old/lapsed patient list (not fresh ad leads) tags them
        # on the way in so they can be segmented later, same tags table/UI
        # ads-lead/organic-lead already use above.
        for _tag_name, _tag_color in [
            ("Previous Patient", "#6ab0ff"), ("Never Followed Up", "#f5a623"),
            ("No-Show History", "#dc3c3c"), ("Cancelled Appointment", "#e08ad0"),
            ("Lost to Insurance", "#8a6fd8"), ("Price Objection", "#c2c24a"),
            ("Referral", "#4ade80"), ("Cold / Unresponsive", "#5a6f8f"),
        ]:
            await conn.execute("INSERT INTO tags (name, color) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING", _tag_name, _tag_color)

        # Placeholder agent slots an admin can name ahead of building them
        # (e.g. a future database-reactivation agent) — the existing
        # Facebook Leads response agent stays wired to client_marketing_config
        # and is NOT a row in this table; see ClientsPanel.jsx's Agents tab.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_agents (
                id         SERIAL PRIMARY KEY,
                client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        # Queue for personalized Send Info Loom videos — the outreach-video
        # skill needs local Playwright/ffmpeg + the local headcam master
        # clip, none of which exist on this Railway container, so a
        # disposition change can't generate the video synchronously. This
        # gets drained by a scheduled local Claude Code run (see
        # content-agent/run-send-info-queue.ps1), same shape as
        # leadgen-agent's scheduled scrape-leads run. See send_info_queue.py.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS send_info_loom_queue (
                id           SERIAL PRIMARY KEY,
                contact_id   TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                status       TEXT NOT NULL DEFAULT 'pending',
                watch_url    TEXT,
                error        TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_send_info_loom_queue_pending "
            "ON send_info_loom_queue(created_at) WHERE status = 'pending'"
        )

        # Dylan's OWN Calendly connection — same idea as client_marketing_config's
        # calendly_* columns above, just for DigiGrowth's own pipeline rather
        # than a client's. Reuses dialer_settings (the app's existing
        # generic key/value store, see reminder_engine.py/dm_followup_sequence.py's
        # template storage) instead of a dedicated table for a handful of values.
