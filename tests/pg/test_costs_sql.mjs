// 11th update (11.10): company costs. Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_costs_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 300) : ""); } };
const U = { james: uuid(), omar: uuid(), gio: uuid(), gone: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 11) run, and run again safely", true);
await addUser(db, U.james, "james", { role: "admin" }); await addUser(db, U.omar, "omar", { role: "admin" });
await addUser(db, U.gio, "gio"); await addUser(db, U.gone, "gone", { active: false });
const call = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows : r; };
const add = (who, label, amt, on, to) => call(who, "select public.exp_add($1, $2, $3::date, $4) as v", [label, amt, on, to]);

let r = await add("james", "Claude subscription", 30, "2026-11-03", null);
check("an admin adds a cost", Array.isArray(r) && r[0].v.id, r);
r = await call("gio", "select public.exp_list() as v");
const one = Array.isArray(r) && r[0].v[0];
check("everyone sees it, with who it's charged to (the admin by default) and who added it",
  one && one.label === "Claude subscription" && Number(one.amount) === 30 && one.charged_to === U.james && one.charged_name === "James" && one.created_name === "James", r);
r = await add("omar", "Website hosting", 12.499, "2026-11-05", U.gio);
check("an admin can charge a cost to a teammate (amount rounded to cents)", Array.isArray(r), r);
r = await call("gio", "select public.exp_list() as v");
check("newest spending date first", Array.isArray(r) && r[0].v[0].label === "Website hosting" && Number(r[0].v[0].amount) === 12.5 && r[0].v[0].charged_to === U.gio, r);
r = await add("gio", "Sneaky", 5, null, null);
check("someone who isn't an admin can't add a cost", !Array.isArray(r) && /administrator/.test(r.error), r);
r = await call("gio", "insert into public.expenses (label, amount) values ('x', 1)");
check("...or write to the table directly", !Array.isArray(r) && r.ok === false, r);
const id = (await call("gio", "select public.exp_list() as v"))[0].v[0].id;
r = await call("gio", "select public.exp_delete($1) as v", [id]);
check("someone who isn't an admin can't remove a cost", !Array.isArray(r) && /administrator/.test(r.error), r);
r = await call("gio", "delete from public.expenses where id = $1", [id]);
r = await call("gio", "select count(*)::int as n from public.expenses");
check("...or delete it directly", Array.isArray(r) && r[0].n === 2, r);
for (const [label, amt, to, why] of [["", 5, null, "an empty description"], ["x".repeat(81), 5, null, "a description over 80 characters"],
  ["Ok", 0, null, "a zero amount"], ["Ok", -4, null, "a negative amount"], ["Ok", 5, U.gone, "a deactivated person"], ["Ok", 5, uuid(), "someone who doesn't exist"]]) {
  r = await add("james", label, amt, null, to);
  check(`refuses ${why}`, !Array.isArray(r) && r.ok === false, r);
}
r = await call("james", "select public.exp_delete($1) as v", [id]);
check("an admin removes a cost", Array.isArray(r) && r[0].v.ok === true, r);
r = await call("james", "select public.exp_delete($1) as v", [id]);
check("removing it twice says it's already gone", !Array.isArray(r) && /already/.test(r.error), r);
r = await call(null, "select public.exp_list() as v");
check("signed-out visitors can't see costs", !Array.isArray(r) && r.ok === false, r);
r = await call("gone", "select public.exp_list() as v");
check("a deactivated person sees no costs", Array.isArray(r) && r[0].v.length === 0, r);
r = await db.query("select count(*)::int as n from public.audit_log where table_name = 'expenses'");
check("adding and removing costs is recorded in the audit log", r.rows[0].n >= 3, r.rows);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
