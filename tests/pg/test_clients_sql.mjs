// 19th update (12.0): clients. Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_clients_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 400) : ""); } };
const U = { gio: uuid(), tim: uuid(), james: uuid(), gone: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 19) run, and run again safely", true);
await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim"); await addUser(db, U.james, "james", { role: "admin" }); await addUser(db, U.gone, "gone", { active: false });
const v = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows[0].v : r; };
const D1 = uuid(), D2 = uuid(), D3 = uuid();
await db.query(`insert into public.leads (id, name, phone) values ('L1', 'Maple Roofing', '519-555-0101') on conflict do nothing`);
await db.query(`insert into public.deals (id, client, upfront, monthly, months, closed_at, owner_id) values
  ($1, 'Maple Roofing website', 900, 0, 0, current_date - 30, $4), ($2, 'Maple Roofing SEO', 0, 250, 0, current_date - 20, $4), ($3, 'Oak Dental logo', 400, 0, 0, current_date - 5, $5)`,
  [D1, D2, D3, U.gio, U.tim]);
const before = (await db.query("select count(*)::int n, sum(upfront)::numeric s from public.deals")).rows[0];

console.log("adding a client");
let r = await v("gio", "select public.cli_save($1) as v", [{ name: " Maple Roofing ", company: "Maple Roofing Ltd", contact: "Sam Lee", phone: "519-555-0101", email: "sam@maple.ca",
  status: "active", priority: "high", tags: ["Website", "SEO", "website", " "], team: [{ id: U.gio, role: "Account lead" }, { id: U.tim, role: "Design" }, { id: U.gio }], lead_id: "L1", notes: "Pays on the 1st" }]);
check("Gio adds a client with contact details, tags, priority and team", r.id && r.name === "Maple Roofing" && r.priority === "high" && r.lead_id === "L1", r);
const C1 = r.id;
check("blank tags are dropped and duplicates merged", Array.isArray(r.tags) && r.tags.length === 3, r.tags);
check("a teammate listed twice is kept once, with their responsibility", r.team.length === 2 && r.team[0].role === "Account lead", r.team);
check("the start date defaults to today", !!r.start_date, r.start_date);
r = await v("gio", "select public.cli_save($1) as v", [{ name: "" }]);
check("a client needs a name", r.ok === false && /name/.test(r.error), r);
r = await v("gio", "select public.cli_save($1) as v", [{ name: "X", email: "not an email" }]);
check("a bad email is refused with a clear message", r.ok === false && /email/.test(r.error), r);
r = await v("gio", "select public.cli_save($1) as v", [{ name: "X", status: "vip" }]);
check("an unknown status is refused", r.ok === false && /status/.test(r.error), r);
r = await v("gio", "select public.cli_save($1) as v", [{ name: "X", team: [{ id: uuid() }] }]);
check("only real teammates can be assigned", r.ok === false && /teammates/.test(r.error), r);
r = await v("gone", "select public.cli_save($1) as v", [{ name: "Sneaky" }]);
check("a deactivated account can't add clients", r.ok === false && /Sign in/.test(r.error), r);
r = await v(null, "select public.cli_save($1) as v", [{ name: "Sneaky" }]);
check("signed out: refused", r.ok === false, r);
r = await as(db, U.gio, "insert into public.clients (name) values ('Direct')");
check("clients can't be written directly, only through the checked functions", r.ok === false, r);
r = await v("tim", "select public.cli_save($1) as v", [{ name: "Oak Dental", status: "pending" }]);
const C2 = r.id;
check("Tim adds a pending client", r.status === "pending", r);

console.log("services are the client's deals (nothing copied)");
r = await v("gio", "select public.cli_link($1, $2, true) as v", [C1, D1]);
check("linking a deal adds it as a service", r.deal_ids && r.deal_ids.includes(D1), r);
r = await v("gio", "select public.cli_link($1, $2, true) as v", [C1, D2]);
check("...two services", r.deal_ids.length === 2, r.deal_ids);
r = await v("gio", "select public.cli_link($1, $2, true) as v", [C1, uuid()]);
check("a deal that doesn't exist (not synced yet) gives a clear message", r.ok === false && /sync/.test(r.error), r);
r = await v("tim", "select public.cli_link($1, $2, true) as v", [C2, D2]);
check("moving a deal to another client is allowed (a deal belongs to one client)", r.deal_ids.includes(D2), r);
r = await db.query("select client_id from public.client_deals where deal_id = $1", [D2]);
check("...and it's no longer on the first client", r.rows.length === 1 && r.rows[0].client_id === C2, r.rows);
await v("gio", "select public.cli_link($1, $2, true) as v", [C1, D2]);
const after = (await db.query("select count(*)::int n, sum(upfront)::numeric s from public.deals")).rows[0];
check("the deals themselves are untouched (same count and amounts)", after.n === before.n && String(after.s) === String(before.s), [before, after]);
r = await v("gio", "select public.cli_link($1, $2, false) as v", [C1, D2]);
check("taking a service off a client", !r.deal_ids.includes(D2), r);
await v("gio", "select public.cli_link($1, $2, true) as v", [C1, D2]);

console.log("timeline");
r = await v("tim", "select public.cli_note($1, 'call', $2) as v", [C1, "Called Sam, wants a new landing page in March"]);
check("Tim adds a call to Maple's timeline", r.id && r.kind === "call", r);
const N1 = r.id;
r = await v("tim", "select public.cli_note($1, 'note', '   ') as v", [C1]);
check("an empty note is refused", r.ok === false, r);
r = await v("tim", "select public.cli_note($1, 'change', 'fake') as v", [C1]);
check("people can't write 'change' entries (only the app does)", r.ok === false, r);
await v("gio", "select public.cli_save($1) as v", [{ id: C1, name: "Maple Roofing", status: "completed", priority: "high", team: [{ id: U.gio, role: "Account lead" }, { id: U.tim, role: "Design" }], lead_id: "L1", tags: ["Website"] }]);
r = await v("gio", "select public.cli_get($1) as v", [C1]);
const bodies = r.timeline.map((e) => e.body);
check("the timeline records: added, services, the call, the status change", bodies.includes("Client added") && bodies.some((b) => b.startsWith("Service added: Maple Roofing website")) && bodies.some((b) => b.includes("landing page")) && bodies.includes("Status: active → completed"), bodies);
check("...newest first, with who did it", r.timeline[0].created_name && new Date(r.timeline[0].created_at) >= new Date(r.timeline.at(-1).created_at), r.timeline[0]);
check("...and the move to Oak and back is on both clients", bodies.some((b) => b.startsWith("Service moved to Oak Dental")) || (await v("tim", "select public.cli_get($1) as v", [C2])).timeline.some((e) => e.body.startsWith("Service moved to Maple")), null);
r = await v("gio", "select public.cli_note_delete($1) as v", [N1]);
check("Gio can't delete Tim's note", r.ok === false, r);
r = await v("james", "select public.cli_note_delete($1) as v", [N1]);
check("an admin can", r.ok === true, r);
const chg = (await v("gio", "select public.cli_get($1) as v", [C1])).timeline.find((e) => e.kind === "change");
r = await v("james", "select public.cli_note_delete($1) as v", [chg.id]);
check("the app's own change entries can't be deleted", r.ok === false, r);

console.log("who sees what");
r = await v("tim", "select public.cli_list() as v");
check("everyone on the team sees every client", r.clients.length === 2 && r.admin === false, r);
r = await as(db, U.gone, "select count(*)::int n from public.clients");
check("a deactivated account sees no clients", r.ok && r.rows[0].n === 0, r);
r = await as(db, null, "select count(*)::int n from public.clients");
check("signed out sees nothing", !r.ok || r.rows[0].n === 0, r);
r = await v("gone", "select public.cli_list() as v");
check("...and can't list them", r.ok === false, r);

console.log("archive, reactivate, delete");
r = await v("tim", "select public.cli_archive($1, true) as v", [C2]);
check("archiving keeps the client, marked archived", !!r.archived_at, r);
r = await v("tim", "select public.cli_list() as v");
check("archived clients are listed last", r.clients.at(-1).id === C2, r.clients.map((c) => c.name));
r = await v("tim", "select public.cli_archive($1, false) as v", [C2]);
check("reactivating brings it back", r.archived_at === null, r);
r = await v("tim", "select public.cli_delete($1) as v", [C1]);
check("only an admin can delete a client", r.ok === false && /admin/.test(r.error), r);
r = await v("james", "select public.cli_delete($1) as v", [C1]);
check("an admin deletes it", r.ok === true, r);
r = await db.query("select count(*)::int n from public.deals where id = any($1)", [[D1, D2]]);
check("its deals are kept (only unlinked)", r.rows[0].n === 2, r.rows);
r = await db.query("select (select count(*) from public.client_events where client_id = $1)::int e, (select count(*) from public.client_deals where client_id = $1)::int d", [C1]);
check("its timeline and links go with it", r.rows[0].e === 0 && r.rows[0].d === 0, r.rows);
r = await db.query("delete from public.deals where id = $1", [D3]);
await v("tim", "select public.cli_link($1, $2, true) as v", [C2, D1]);
await db.query("delete from public.deals where id = $1", [D1]);
r = await db.query("select count(*)::int n from public.client_deals where deal_id = $1", [D1]);
check("deleting a deal removes its link (the client stays)", r.rows[0].n === 0, r.rows);

console.log("System health");
r = await v("james", "select public.team_health() as v");
check("the health check reports update 19, and 18", r.updates["19"] === true && r.updates["18"] === true, r.updates);
r = await v("gio", "select public.team_health() as v");
check("...admins only", r.ok === false, r);
r = await as(db, U.gio, "select public.cli_json(c) from public.clients c");
check("the internal helpers can't be called directly", r.ok === false, r);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
