// 13th update (11.13): confirming meetings. Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_meeting_checks_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 300) : ""); } };
const U = { gio: uuid(), tim: uuid(), gone: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 13) run, and run again safely", true);
await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim"); await addUser(db, U.gone, "gone", { active: false });
await db.query("insert into public.leads (id, name, phone, status) values ('L1', 'Maple Roofing', '519-555-0101', 'green'), ('L2', 'Oak Plumbing', '519-555-0102', 'green')");
const v = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows[0].v : r; };
const PAST = "2026-01-05 10:00", FUTURE = "2099-01-05 10:00";

let r = await v("gio", "select public.mtg_confirm('L1', $1) as v", [PAST]);
check("a teammate confirms a meeting that already happened", r.ok === true, r);
r = await v("tim", "select public.mtg_list(null) as v");
check("everyone sees it, with who confirmed it", r.length === 1 && r[0].lead_id === "L1" && r[0].meeting_key === PAST && r[0].confirmed_by === U.gio && r[0].confirmed_name === "Gio", r);
r = await v("gio", "select public.mtg_confirm('L1', $1) as v", [PAST]);
check("confirming twice is harmless", r.ok === true && (await v("gio", "select public.mtg_list(null) as v")).length === 1, r);
r = await v("gio", "select public.mtg_confirm('L2', $1) as v", [FUTURE]);
check("a meeting in the future can't be confirmed yet", r.ok === false && /hasn't happened/.test(r.error), r);
r = await v("gio", "select public.mtg_confirm('L2', 'tomorrow') as v");
check("a made-up time is refused", r.ok === false && /not valid/.test(r.error), r);
r = await v("gio", "select public.mtg_confirm('NOPE', $1) as v", [PAST]);
check("an unknown business is refused", r.ok === false && /not found/.test(r.error), r);
r = await v("gone", "select public.mtg_confirm('L2', $1) as v", [PAST]);
check("a deactivated person can't confirm", r.ok === false, r);
r = await v(null, "select public.mtg_list(null) as v");
check("signed-out visitors see nothing", r.ok === false, r);
r = await as(db, U.gio, "insert into public.meeting_checks (lead_id, meeting_key) values ('L2', '2026-01-01 09:00')");
check("nobody writes to the table directly", r.ok === false, r);
r = await v("tim", "select public.mtg_list('2026-02-01') as v");
check("the list can start from a day", Array.isArray(r) && r.length === 0, r);
r = await v("tim", "select public.mtg_unconfirm('L1', $1) as v", [PAST]);
check("a confirmation can be undone", r.ok === true && (await v("gio", "select public.mtg_list(null) as v")).length === 0, r);
await v("gio", "select public.mtg_confirm('L1', $1) as v", [PAST]);
await db.query("delete from public.leads where id = 'L1'");
check("removing the business removes its confirmations", (await v("gio", "select public.mtg_list(null) as v")).length === 0);
r = await db.query("select count(*)::int as n from public.audit_log where table_name = 'meeting_checks'");
check("confirmations are recorded in the audit log", r.rows[0].n >= 3, r.rows);
console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
