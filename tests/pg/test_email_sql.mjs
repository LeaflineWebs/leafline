// 18th update (11.20): the email writer's sign-in check + daily limit. Real migrations, real Postgres.
// Run:  cd tests/pg && node test_email_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 400) : ""); } };
const U = { gio: uuid(), tim: uuid(), james: uuid(), gone: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 18) run, and run again safely", true);
await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim"); await addUser(db, U.james, "james", { role: "admin" }); await addUser(db, U.gone, "gone", { active: false });
const v = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows[0].v : r; };

console.log("taking an email from today's allowance");
let r = await v("gio", "select public.email_quota_take('L1') as v");
check("Gio (active) gets one: 1 of 150", r.ok === true && r.used === 1 && r.limit === 150, r);
r = await v("gio", "select public.email_quota_take() as v");
check("...the business id is optional: 2 of 150", r.ok === true && r.used === 2, r);
r = await v("tim", "select public.email_quota_take('L9') as v");
check("each person has their own count", r.ok === true && r.used === 1, r);
r = await v("gone", "select public.email_quota_take('L1') as v");
check("a deactivated account is refused", r.ok === false && /Sign in/.test(r.error), r);
r = await v(null, "select public.email_quota_take('L1') as v");
check("signed out: refused", r.ok === false || r.error, r);
r = await db.query("select count(*)::int as n from public.email_drafts");
check("refused attempts aren't counted", r.rows[0].n === 3, r.rows);
r = await v("gio", "select public.email_quota_take($1) as v", ["x".repeat(500)]);
r = await db.query("select max(length(lead_id))::int as n from public.email_drafts");
check("a long business id is cut to 80 characters", r.rows[0].n === 80, r.rows);

console.log("the daily limit");
await db.query("insert into public.email_drafts (user_id, lead_id, created_at) select $1, 'bulk', now() - interval '1 hour' from generate_series(1, 146)", [U.gio]);
r = await v("gio", "select public.email_quota_take('L1') as v");
check("Gio's 150th email in 24 hours is allowed", r.ok === true && r.used === 150, r);
r = await v("gio", "select public.email_quota_take('L1') as v");
check("the 151st is refused with a clear message", r.ok === false && r.limit_reached === true && /150 emails in the last 24 hours/.test(r.error), r);
r = await v("tim", "select public.email_quota_take('L1') as v");
check("...Tim isn't affected", r.ok === true && r.used === 2, r);
await db.query("update public.email_drafts set created_at = now() - interval '25 hours' where user_id = $1 and lead_id = 'bulk'", [U.gio]);
r = await v("gio", "select public.email_quota_take('L1') as v");
check("emails older than 24 hours stop counting", r.ok === true && r.used === 5, r);
await db.query("update public.email_drafts set created_at = now() - interval '31 days' where user_id = $1 and lead_id = 'bulk'", [U.gio]);
await v("gio", "select public.email_quota_take('L1') as v");
r = await db.query("select count(*)::int as n from public.email_drafts where lead_id = 'bulk'");
check("rows older than 30 days are cleared out", r.rows[0].n === 0, r.rows);

console.log("who can see the log");
r = await as(db, U.tim, "select user_id from public.email_drafts");
check("Tim sees only his own rows", r.ok && r.rows.length === 2 && r.rows.every((x) => x.user_id === U.tim), r);
r = await as(db, U.james, "select count(distinct user_id)::int as n from public.email_drafts");
check("an admin sees everyone's", r.ok && r.rows[0].n === 2, r);
r = await as(db, U.gone, "select count(*)::int as n from public.email_drafts");
check("a deactivated account sees nothing", r.ok && r.rows[0].n === 0, r);
r = await as(db, U.james, "insert into public.email_drafts (user_id) values ($1)", [U.james]);
check("nobody can add rows directly (not even an admin)", r.ok === false, r);
r = await as(db, U.gio, "delete from public.email_drafts");
const left = await db.query("select count(*)::int as n from public.email_drafts where user_id = $1", [U.gio]);
check("...or delete them to reset their count", left.rows[0].n > 0, r);

console.log("System health");
r = await v("james", "select public.team_health() as v");
check("System health reports updates 17 and 18 as run", r.updates && r.updates["17"] === true && r.updates["18"] === true && r.updates["16"] === true, r.updates);
r = await as(db, U.gio, "select public.team_health()");
check("...still admins only", r.ok === false, r);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
