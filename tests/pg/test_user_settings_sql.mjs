// 9th update (11.8): private account details. Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_user_settings_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 300) : ""); } };
const U = { gio: uuid(), tim: uuid(), james: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 9) run, and run again safely", true);
await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim"); await addUser(db, U.james, "james", { role: "admin" });
const call = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows : r; };

let r = await call("gio", "select public.me_settings_get() as v");
check("nothing saved yet: empty answer", Array.isArray(r) && JSON.stringify(r[0].v) === "{}", r);
r = await call("gio", "select public.me_settings_set($1::jsonb) as v", [JSON.stringify({ account: { email: "gio@leaflineweb.com", phone: "416-555-0101" } })]);
check("save your account details", Array.isArray(r) && r[0].v.data.account.email === "gio@leaflineweb.com", r);
r = await call("gio", "select public.me_settings_set($1::jsonb) as v", [JSON.stringify({ other: 1 })]);
check("a later save merges (keeps what was there)", Array.isArray(r) && r[0].v.data.account.phone === "416-555-0101" && r[0].v.data.other === 1, r);
r = await call("gio", "select public.me_settings_get() as v");
check("read it back (e.g. on another device)", Array.isArray(r) && r[0].v.data.account.email === "gio@leaflineweb.com", r);

r = await call("tim", "select public.me_settings_get() as v");
check("a teammate gets only their own (empty) row", Array.isArray(r) && JSON.stringify(r[0].v) === "{}", r);
r = await call("tim", "select * from public.user_settings");
check("a teammate can't list anyone else's row", Array.isArray(r) && r.length === 0, r);
r = await call("james", "select * from public.user_settings");
check("an admin can't read other people's rows either", Array.isArray(r) && r.length === 0, r);
r = await call("tim", "update public.user_settings set data = '{}'::jsonb where user_id = $1", [U.gio]);
r = await call("gio", "select public.me_settings_get() as v");
check("a teammate can't change your row", Array.isArray(r) && r[0].v.data.account.email === "gio@leaflineweb.com", r);
r = await call("tim", "insert into public.user_settings (user_id, data) values ($1, '{}')", [U.gio]);
check("a teammate can't create a row for you", !Array.isArray(r) && r.ok === false, r);
r = await call(null, "select public.me_settings_get() as v");
check("signed-out visitors can't call it", !Array.isArray(r) && r.ok === false, r);
r = await call("gio", "select public.me_settings_set($1::jsonb) as v", [JSON.stringify(["not", "an", "object"])]);
check("rejects data that isn't an object", !Array.isArray(r) && r.ok === false, r);
r = await call("gio", "select public.me_settings_set($1::jsonb) as v", [JSON.stringify({ big: "x".repeat(5000) })]);
check("rejects oversized data", !Array.isArray(r) && r.ok === false, r);

console.log("reactions on shared notes and scripts");
const N1 = uuid(), N2 = uuid();
await db.query("insert into public.notes (id, kind, scope, owner_id, title) values ($1,'script','shared',$2,'Opener'), ($3,'note','personal',$2,'Mine')", [N1, U.gio, N2]);
r = await call("tim", "select public.note_react($1, $2) as v", [N1, "🔥"]);
check("a teammate reacts to a shared script", Array.isArray(r) && r[0].v.on === true, r);
await call("gio", "select public.note_react($1, $2) as v", [N1, "🔥"]);
r = await call("gio", "select public.note_reactions_for($1::uuid[]) as v", [[N1]]);
check("counts, who reacted and whether you did", Array.isArray(r) && r[0].v[0].n === 2 && r[0].v[0].mine === true && r[0].v[0].who.length === 2, r);
r = await call("tim", "select public.note_react($1, $2) as v", [N1, "🔥"]);
check("pressing it again takes the reaction back", Array.isArray(r) && r[0].v.on === false, r);
r = await call("tim", "select public.note_react($1, $2) as v", [N2, "👍"]);
check("can't react to someone's private note", !Array.isArray(r) && r.ok === false, r);
r = await call("tim", "select public.note_react($1, $2) as v", [N1, "💩"]);
check("only the listed reactions are allowed", !Array.isArray(r) && r.ok === false, r);
r = await call("tim", "insert into public.note_reactions (note_id, user_id, emoji) values ($1, $2, '👍')", [N1, U.gio]);
check("nobody can write reactions directly (or in someone else's name)", !Array.isArray(r) && r.ok === false, r);
await db.query("update public.notes set scope = 'personal' where id = $1", [N1]);
r = await call("tim", "select public.note_reactions_for($1::uuid[]) as v", [[N1]]);
check("when a note stops being shared, its reactions are hidden", Array.isArray(r) && r[0].v.length === 0, r);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
