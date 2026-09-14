"""
Shared handle to the app's single AsyncIOScheduler instance (created once
in main.py's lifespan()), so other modules can schedule one-off deferred
jobs on the SAME running event loop without importing main.py directly
(risking a circular import, since main.py imports every router).

Needed by response_ai.py's min-delay-before-replying rule: a plain
threading.Thread can't be used to defer the reply (a new thread needs its
own event loop, and db.py's asyncpg pool is bound to the main loop — see
response_ai.py's module docstring), and sleeping synchronously inside the
Twilio webhook handler for up to however many seconds risks Twilio's
webhook timeout retrying the request. Scheduling a one-off APScheduler job
for "now + N seconds" runs on the main loop (same as every other scheduled
job in this codebase) with none of those problems.
"""
_scheduler = None


def set_scheduler(scheduler) -> None:
    global _scheduler
    _scheduler = scheduler


def get_scheduler():
    return _scheduler
