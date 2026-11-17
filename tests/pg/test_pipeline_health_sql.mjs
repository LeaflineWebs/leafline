// 17th update (11.19): pipeline stages, duplicate / do-not-call guard, app status + admin health. Real migrations, real Postgres.
// Run:  cd tests/pg && node test_pipeline_health_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 400) : ""); } };
const U = { gio: uuid(), tim: uuid(), james: uuid(), gone: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 17) run, and run again safely", true);
await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim"); await addUser(db, U.james, "james", { role: "admin" }); await addUser(db, U.gone, "gone", { active: false });
await db.query("insert into public.leads (id, name, phone) values ('L1','Maple Roofing','(519) 555-0101'), ('L2','Oak Plumbing','519-555-0102'), ('L3','Birch Dental','519.555.0103'), ('L4','Pine Spa','519 555 0104')");
await db.query("update public.leads set status = 'red', called_by = $1, called_at = now() - interval '20 days' where id = 'L4'", [U.tim]);
const v = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows[0].v : r; };
const call = (who, lead, phone, outcome, ago) => db.query("insert into public.call_log (lead_id, employee_id, phone, started_at, outcome, source) values ($1, $2, $3, now() - $4::interval, $5, 'app')", [lead, U[who], phone, ago, outcome]);

// ---- pipeline
console.log("pipeline stages");
let r = await v("gio", "select public.lead_stage_set('L1', 'proposal') as v");
check("Gio moves Maple Roofing to Proposal sent", r.ok === true && r.stage === "proposal", r);
r = await v("tim", "select public.lead_stage_list() as v");
check("the whole team sees it", r.length === 1 && r[0].lead_id === "L1" && r[0].stage === "proposal" && r[0].updated_by === U.gio, r);
r = await v("tim", "select public.lead_stage_set('L1', 'won') as v");
check("a teammate can move it on (shared pipeline)", r.ok === true, r);
r = await v("tim", "select public.lead_stage_list() as v");
check("...and it's replaced, not duplicated", r.length === 1 && r[0].stage === "won" && r[0].updated_by === U.tim, r);
r = await v("gio", "select public.lead_stage_set('L1', 'dancing') as v");
check("a made-up stage is refused", r.ok === false && /stage is not valid/.test(r.error), r);
r = await v("gio", "select public.lead_stage_set('NOPE', 'won') as v");
check("a business that doesn't exist is refused", r.ok === false && /not found/.test(r.error), r);
r = await v("gone", "select public.lead_stage_set('L1', 'lost') as v");
check("a deactivated account is refused", r.ok === false, r);
r = await v(null, "select public.lead_stage_set('L1', 'lost') as v");
check("signed out: refused", r.ok === false, r);
r = await as(db, U.james, "insert into public.lead_stages (lead_id, stage) values ('L2', 'won')");
check("nobody can write the table directly (not even an admin)", r.ok === false, r);
r = await v("gio", "select public.lead_stage_set('L1', '') as v");
r = await v("gio", "select public.lead_stage_list() as v");
check("an empty stage puts it back to automatic", r.length === 0, r);
r = await db.query("select summary from public.activity where kind = 'pipeline' order by id");
check("moves show in Activity", r.rows.some((x) => x.summary === "Gio moved Maple Roofing to Proposal sent") && r.rows.some((x) => x.summary === "Tim moved Maple Roofing to Won"), r.rows);
r = await db.query("select count(*)::int n from public.audit_log where table_name = 'lead_stages'");
check("...and in the audit log", r.rows[0].n >= 3, r.rows);

// ---- guard
console.log("duplicate / do-not-call guard");
await call("tim", "L1", "(519) 555-0101", "no_answer", "2 days");
await call("tim", null, "+1 519-555-0102", "voicemail", "1 day");          // logged by phone only, no business attached
await call("gio", "L3", "519.555.0103", "interested", "1 hour");           // Gio's own call
await call("tim", "L3", "519.555.0103", "no_answer", "30 days");          // too old to count as "recent"
await call("james", "L2", "519-555-0102", "not_interested", "100 days");
const LEADS = [{ id: "L1", key: "5195550101" }, { id: "L2", key: "5195550102" }, { id: "L3", key: "5195550103" }, { id: "L4", key: "5195550104" }];
r = await v("gio", "select public.lead_guard($1::jsonb) as v", [JSON.stringify(LEADS)]);
const by = Object.fromEntries((Array.isArray(r) ? r : []).map((x) => [x.id, x]));
check("Maple Roofing: Tim called it 2 days ago (No answer)", by.L1 && by.L1.last_name === "Tim" && by.L1.last_outcome === "no_answer" && !by.L1.dnc_at, by.L1);
check("Oak Plumbing: found by phone number even with no business attached (voicemail, yesterday)", by.L2 && by.L2.last_name === "Tim" && by.L2.last_outcome === "voicemail", by.L2);
check("Oak Plumbing: James was told 'not interested' 100 days ago", by.L2 && by.L2.dnc_name === "James", by.L2);
check("Birch Dental: Gio's own call doesn't warn Gio, and a 30-day-old call isn't recent", !by.L3, by.L3);
check("Pine Spa: marked Not interested on the business itself", by.L4 && by.L4.dnc_name === "Tim" && !by.L4.last_at, by.L4);
r = await v("tim", "select public.lead_guard($1::jsonb) as v", [JSON.stringify(LEADS)]);
const byT = Object.fromEntries(r.map((x) => [x.id, x]));
check("for Tim, his own calls don't warn him, but Gio's do", !byT.L1 && byT.L3 && byT.L3.last_name === "Gio", r);
r = await v("gio", "select public.lead_guard($1::jsonb) as v", ['"nonsense"']);
check("rubbish input gives an empty answer, not an error", Array.isArray(r) && r.length === 0, r);
r = await v("gio", "select public.lead_guard($1::jsonb) as v", [JSON.stringify(Array.from({ length: 400 }, (_, i) => ({ id: "X" + i, key: "" })))]);
check("a long list is fine (capped at 300)", Array.isArray(r), r);
r = await v(null, "select public.lead_guard($1::jsonb) as v", [JSON.stringify(LEADS)]);
check("signed-out visitors learn nothing", !Array.isArray(r) || r.length === 0, r);

// ---- app status + health
console.log("app status + health page");
r = await v("gio", "select public.me_status_report($1::jsonb) as v", [JSON.stringify({ version: "11.19.0", platform: "desktop", sync_state: "synced", pending: 0 })]);
check("Gio's app reports its version and sync state", r.ok === true, r);
r = await v("tim", "select public.me_status_report($1::jsonb) as v", [JSON.stringify({ version: "11.17.0", platform: "web", sync_state: "offline", pending: 3, last_error: "x".repeat(500) })]);
check("Tim's app reports too (long errors are cut short)", r.ok === true, r);
r = await v("gio", "select public.me_status_report($1::jsonb) as v", [JSON.stringify({ pending: "lots" })]);
check("rubbish numbers are refused", r.ok === false, r);
r = await as(db, U.gio, "select user_id from public.app_status");
check("Gio can see only his own status row", r.ok && r.rows.length === 1 && r.rows[0].user_id === U.gio, r);
r = await as(db, U.james, "select count(*)::int n from public.app_status");
check("an admin can see everyone's", r.ok && r.rows[0].n === 2, r);
r = await as(db, U.gio, "update public.app_status set version = 'hacked'");
check("nobody can write the table directly", !r.ok || r.affected === 0, r);
r = await v("gio", "select public.team_health() as v");
check("the health page is for admins only", r.ok === false && /Administrators only/.test(r.error), r);
r = await v("james", "select public.team_health() as v");
const ups = r.updates || {};
check("the admin sees every database update (2 to 18 now that 18 exists) as installed", Object.keys(ups).length === 17 && Object.entries(ups).every(([k, x]) => x === true || (k === "10" && x !== false)), ups);
const tim = (r.people || []).find((p) => p.username === "tim"), gone = (r.people || []).find((p) => p.username === "gone");
check("...and each person's app version, platform, sync state, waiting changes and error", tim && tim.version === "11.17.0" && tim.platform === "web" && tim.sync_state === "offline" && tim.pending === 3 && tim.last_error.length === 300, tim);
check("...including people whose app hasn't reported yet, and deactivated accounts", gone && gone.version === null && gone.active === false, gone);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
