// 12th update (11.11): finding new leads from a phone. Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_phone_search_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 300) : ""); } };
const U = { james: uuid(), gio: uuid(), tim: uuid(), gone: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 12) run, and run again safely", true);
await addUser(db, U.james, "james", { role: "admin" }); await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim"); await addUser(db, U.gone, "gone", { active: false });
const call = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows : r; };
const v = async (who, sql, p) => { const r = await call(who, sql, p); return Array.isArray(r) ? r[0].v : r; };
const KEY = "AIzaSyD-test_key_0123456789abcdefghijk";

// ---- settings
let r = await v("gio", "select public.lead_cfg() as v");
check("before setup: no key, limit 900, nothing used", r.key === "" && r.cap === 900 && r.used === 0 && r.admin === false, r);
r = await v("gio", "select public.lead_cfg_set($1, 50) as v", [KEY]);
check("someone who isn't an admin can't set the key", r.ok === false && /administrator/.test(r.error), r);
r = await v("james", "select public.lead_cfg_set($1, 50) as v", ["not a key!"]);
check("a malformed key is refused", r.ok === false && /Google API key/.test(r.error), r);
r = await v("james", "select public.lead_cfg_set($1, 100001) as v", [KEY]);
check("a limit over 100000 is refused", r.ok === false, r);
r = await v("james", "select public.lead_cfg_set($1, 2) as v", [KEY]);
check("an admin saves the key and a monthly limit", r.key === KEY && r.cap === 2 && r.admin === true, r);
r = await v("james", "select public.lead_cfg_set(null, 3) as v");
check("changing only the limit keeps the key", r.key === KEY && r.cap === 3, r);
r = await v("gio", "select public.lead_cfg() as v");
check("teammates get the key (their phone sends it to Google)", r.key === KEY, r);
r = await call("gio", "select * from public.lead_settings");
check("...but can't read the settings table directly", Array.isArray(r) && r.length === 0, r);
r = await call("gio", "update public.lead_settings set month_cap = 99999");
r = await v("gio", "select public.lead_cfg() as v");
check("...or change it directly", r.cap === 3, r);
r = await v(null, "select public.lead_cfg() as v");
check("signed-out visitors get nothing", r.ok === false, r);
r = await v("gone", "select public.lead_cfg() as v");
check("a deactivated person gets nothing", r.ok === false, r);

// ---- monthly limit
const takes = [];
for (let i = 0; i < 4; i++) takes.push(await v(i % 2 ? "tim" : "gio", "select public.lead_quota_take() as v"));
check("the first 3 requests this month are counted", takes.slice(0, 3).every((x) => x.used >= 1 && x.cap === 3) && takes[2].used === 3, takes);
check("the 4th is refused: the limit holds for the whole team", takes[3].ok === false && /limit of 3/.test(takes[3].error), takes[3]);
r = await call("gio", "update public.lead_usage set calls = 0");
r = await v("gio", "select public.lead_quota_take() as v");
check("nobody can reset the counter directly", r.ok === false, r);
r = await v("gio", "select public.lead_cfg() as v");
check("lead_cfg shows how much is used", r.used === 3, r);
await v("james", "select public.lead_cfg_set('', 900) as v");
r = await v("gio", "select public.lead_cfg() as v");
check("an admin can remove the key", r.key === "", r);

// ---- saving businesses
await db.query("insert into public.leads (id, name, phone, status, search) values ('0xa:0x1', 'Called Roofing', '(519) 555-0101', 'green', 'Roofing | Kitchener')");
await db.query("insert into public.leads (id, name, phone, status, search) values ('0xa:0x2', 'Waiting Roofing', '519-555-0102', 'none', 'Old search')");
const rows = [
  { id: "ChIJ_new_1", name: "New Roofing", phone: "(519) 555-0199", address: "1 King St", website: "https://new.example", rating: "4.6", reviews: "120", hours: '{"Monday":"9 AM-5 PM"}' },
  { id: "ChIJ_called", name: "Called Roofing (Google)", phone: "+1 519-555-0101", rating: "4.0", reviews: "8" },
  { id: "ChIJ_waiting", name: "Waiting Roofing", phone: "+1 519 555 0102", rating: "4.9", reviews: "77" },
  { id: "ChIJ_nophone", name: "No Phone Co", phone: "" },
  { id: "ChIJ_new_1", name: "New Roofing again", phone: "(519) 555-0199" },
];
r = await v("gio", "select public.lead_add_found($1, $2, $3::jsonb) as v", ["Roofing | Kitchener, Ontario, Canada", "Roofing", JSON.stringify(rows)]);
check("a new business is added; the called one and the one without a phone are left out", r.added === 1 && r.moved === 1 && r.skipped === 3, r);
const got = Object.fromEntries((r.rows || []).map((x) => [x.id, x]));
check("the new lead has its details, who found it and where it came from", got.ChIJ_new_1 && got.ChIJ_new_1.website === "https://new.example" && got.ChIJ_new_1.reviews === "120" && got.ChIJ_new_1.added_by === U.gio && got.ChIJ_new_1.source === "google_places" && got.ChIJ_new_1.status === "none", got.ChIJ_new_1);
check("a business already waiting (same phone, PC's id) moves into this search, keeping its id", got["0xa:0x2"] && got["0xa:0x2"].search === "Roofing | Kitchener, Ontario, Canada" && got["0xa:0x2"].reviews === "77", got["0xa:0x2"]);
r = await call("gio", "select id, status, search from public.leads where id = '0xa:0x1'");
check("the called business is untouched", r[0].status === "green" && r[0].search === "Roofing | Kitchener", r);
r = await call("gio", "select count(*)::int as n from public.leads where phone_key = '5195550199'");
check("no duplicate by phone number", r[0].n === 1, r);
r = await v("gio", "select public.lead_add_found('x', 'x', $1::jsonb) as v", [JSON.stringify(Array.from({ length: 101 }, (_, i) => ({ id: "b" + i, name: "b", phone: "5195550" + String(i).padStart(3, "0") })))]);
check("more than 100 businesses at once is refused", r.ok === false, r);
r = await v("gone", "select public.lead_add_found('x', 'x', '[]'::jsonb) as v");
check("a deactivated person can't add leads", r.ok === false, r);

// ---- your PC runs it
r = await v("gio", "select public.lead_req_add('Canada', 'Ontario', 'Kitchener', '') as v");
check("a request without a business type is refused", r.ok === false && /business type/.test(r.error), r);
r = await v("gio", "select public.lead_req_add('', '', '', 'Roofing') as v");
check("a request without any place is refused", r.ok === false, r);
const q1 = await v("gio", "select public.lead_req_add(' Canada ', 'Ontario', 'Kitchener', ' Roofing ') as v");
check("a phone sends a search to its owner's PC", q1.id && q1.status === "pending" && q1.btype === "Roofing" && q1.country === "Canada", q1);
r = await v("tim", "select public.lead_req_claim() as v");
check("someone else's PC never picks it up", r === null, r);
r = await v("tim", "select public.lead_req_get($1) as v", [q1.id]);
check("...or sees it", r.ok === false, r);
r = await call("tim", "select count(*)::int as n from public.lead_requests");
check("...even reading the table directly", r[0].n === 0, r);
const c1 = await v("gio", "select public.lead_req_claim() as v");
check("the owner's PC picks it up and marks it running", c1 && c1.id === q1.id && c1.status === "running", c1);
r = await v("gio", "select public.lead_req_claim() as v");
check("it's picked up only once", r === null, r);
r = await v("gio", "select public.lead_req_update($1, 'running', 4, 1, 'Reading listing 5/20', null) as v", [q1.id]);
r = await v("gio", "select public.lead_req_get($1) as v", [q1.id]);
check("the phone sees the PC's progress", r.status === "running" && r.found === 4 && r.message === "Reading listing 5/20", r);
r = await v("gio", "select public.lead_req_update($1, 'done', 12, 2, 'Done', 'Roofing | Kitchener, Ontario, Canada') as v", [q1.id]);
r = await v("gio", "select public.lead_req_get($1) as v", [q1.id]);
check("the phone sees the result and the search name", r.status === "done" && r.found === 12 && r.skipped === 2 && r.q === "Roofing | Kitchener, Ontario, Canada", r);
r = await v("gio", "select public.lead_req_update($1, 'running', 1, 0, 'late', null) as v", [q1.id]);
check("a finished search can't be reopened", r.ok === false && r.status === "done", r);
const q2 = await v("gio", "select public.lead_req_add('Canada', '', 'Waterloo', 'Plumbing') as v");
await v("gio", "select public.lead_req_claim() as v");
r = await v("gio", "select public.lead_req_cancel($1) as v", [q2.id]);
check("the phone can stop a running search", r.ok === true, r);
r = await v("gio", "select public.lead_req_update($1, 'running', 3, 0, 'x', null) as v", [q2.id]);
check("...and the PC is told it was stopped", r.ok === false && r.cancelled === true, r);
r = await v("tim", "select public.lead_req_cancel($1) as v", [q1.id]);
check("nobody else can stop your search", r.ok === false, r);
for (let i = 0; i < 3; i++) await v("gio", "select public.lead_req_add('Canada', '', 'Guelph', 'HVAC') as v");
r = await v("gio", "select public.lead_req_add('Canada', '', 'Guelph', 'HVAC') as v");
check("at most 3 waiting searches per person", r.ok === false && /3 searches/.test(r.error), r);
await db.query("update public.lead_requests set created_at = now() - interval '31 minutes' where status = 'pending'");
r = await v("gio", "select public.lead_req_claim() as v");
check("a search nobody picked up for 30 minutes expires instead of starting late", r === null, r);
r = await call("gio", "select count(*)::int as n from public.lead_requests where status = 'failed' and message like '%30 minutes%'");
check("...and says why", r[0].n === 3, r);
r = await v("gio", "select public.lead_req_update($1, 'banana', 0, 0, '', null) as v", [q1.id]);
check("a made-up status is refused", r.ok === false, r);
r = await call("gio", "insert into public.lead_requests (btype) values ('x')");
check("requests can't be written directly", r.ok === false, r);
r = await v(null, "select public.lead_req_add('Canada', '', '', 'x') as v");
check("signed-out visitors can't send searches", r.ok === false, r);
r = await call("gio", "select public.lead_req_expire()");
check("the clean-up function can't be called directly", r.ok === false, r);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
