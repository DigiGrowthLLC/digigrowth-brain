// Run with Claude in Chrome's javascript_tool inside a tab already on Dylan's Canvas
// (logged in). Read-only: GETs Canvas's own planner + missing-submissions data using the
// browser session; no token needed. Result is also kept in window.__dgCanvas.
// The leading `await` matters: without it javascript_tool returns the pending promise as {}.
// Tested on webcourses.ucf.edu 2026-11-13.
await (async () => {
  const DAYS = 10;   // 3-day assignment rule + 3 days of study before a test, with margin
  const now = new Date();
  const fmt = (iso) => iso ? new Date(iso).toLocaleString('sv-SE', {
    timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false }).slice(0, 16) : null;

  async function getAll(path) {
    let url = `${location.origin}/api/v1/${path}`, out = [];
    while (url) {
      const r = await fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
      if (!r.ok) throw new Error(`Canvas HTTP ${r.status} on ${path.split('?')[0]}`);
      out = out.concat(JSON.parse((await r.text()).replace(/^while\(1\);/, '')));
      const m = (r.headers.get('Link') || '').match(/<([^>]+)>;\s*rel="next"/);
      url = m ? m[1] : null;
    }
    return out;
  }

  let result;
  try {
    const start = new Date(now - 864e5).toISOString();
    const end = new Date(+now + DAYS * 864e5).toISOString();
    const [items, missingRaw] = await Promise.all([
      getAll(`planner/items?start_date=${start}&end_date=${end}&per_page=100`),
      getAll('users/self/missing_submissions?include[]=planner_overrides&include[]=course&filter[]=submittable&per_page=100'),
    ]);
    const WORK = new Set(['assignment', 'quiz', 'discussion_topic', 'planner_note', 'wiki_page']);
    const work = [], events = [];
    for (const it of items) {
      const p = it.plannable || {}, subs = it.submissions || {}, ov = it.planner_override || {};
      if (it.plannable_type === 'calendar_event') {
        events.push({ course: it.context_name, title: p.title, start: fmt(p.start_at), end: fmt(p.end_at), all_day: !!p.all_day });
        continue;
      }
      if (!WORK.has(it.plannable_type) || ov.marked_complete || subs.submitted || subs.excused) continue;
      work.push({
        course: it.context_name, title: p.title || p.name, type: it.plannable_type,
        due: fmt(p.due_at || p.todo_date || it.plannable_date), points: p.points_possible ?? null,
        missing: !!subs.missing, url: it.html_url ? new URL(it.html_url, location.origin).href : null,
      });
    }
    work.sort((a, b) => (a.due || '9999').localeCompare(b.due || '9999'));
    const missing = missingRaw.filter(m => !(m.planner_override || {}).marked_complete).map(m => ({
      course: (m.course || {}).name, title: m.name, due: fmt(m.due_at), points: m.points_possible, url: m.html_url,
    }));
    result = { now: fmt(now.toISOString()), work, missing, events };
  } catch (e) {
    result = { error: String(e.message || e), hint: '401/403 = logged out; sign in to Canvas in Chrome' };
  }
  window.__dgCanvas = result;
  // javascript_tool truncates long results, so return compact lines (one per item),
  // not JSON. Full objects (with links) stay in window.__dgCanvas if needed.
  if (result.error) return `ERROR: ${result.error} (${result.hint})`;
  const short = (s, n) => (s || '').slice(0, n);
  return [
    `now ${result.now}`,
    'WORK (course | type | title | due | pts):',
    ...result.work.map(w => `${short(w.course, 10)} | ${short(w.type, 5)} | ${short(w.title, 50)} | ${w.due} | ${w.points ?? ''}${w.missing ? ' | MISSING' : ''}`),
    `MISSING (${result.missing.length}):`,
    ...result.missing.map(m => `${short(m.course, 10)} | ${short(m.title, 50)} | ${m.due}`),
    'EVENTS:',
    ...result.events.map(e => `${short(e.course, 10)} | ${short(e.title, 40)} | ${e.start}`),
  ].join('\n');
})();
