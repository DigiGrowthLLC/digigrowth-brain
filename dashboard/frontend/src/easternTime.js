// Dylan's working timezone. Date math in the UI must use this, not
// `new Date().toISOString()` (UTC) — after 8pm Eastern that already reads as
// tomorrow, which is why tomorrow's 6am todos used to show up the night before.
const TZ = "America/New_York";

// "YYYY-MM-DD" for the current date in Eastern time.
export function easternToday() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date());
}

// "HH:MM" (24h) for the current time in Eastern time.
export function easternNowHHMM() {
  return new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .format(new Date());
}

// True once a todo's due date — and due time, if it has one — has arrived
// in Eastern time. Undated todos are always due.
export function isTodoDue(todo) {
  if (!todo.due_date) return true;
  const today = easternToday();
  const d = todo.due_date.slice(0, 10);
  if (d !== today) return d < today;
  return !todo.due_time || todo.due_time.slice(0, 5) <= easternNowHHMM();
}
