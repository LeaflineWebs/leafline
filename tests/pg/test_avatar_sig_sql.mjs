// 20th update (12.0.1): profiles.avatar_sig, a fingerprint of each picture so the apps re-download a picture only when
// it changed (saves the free plan's monthly download allowance). Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_avatar_sig_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";
import { createHash } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 300) : ""); } };
const U = { gio: uuid(), tim: uuid(), james: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 20) run, and run again safely", true);
await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim"); await addUser(db, U.james, "james", { role: "admin" });
const md5 = (s) => createHash("md5").update(s).digest("hex");
const PIC = "data:image/jpeg;base64,AAAA", PIC2 = "data:image/jpeg;base64,BBBB";

let r = await as(db, U.gio, "update public.profiles set avatar = $1 where id = $2", [PIC, U.gio]);
check("Gio can still change his own picture", r.ok, r);
r = await as(db, U.tim, "select id, avatar_sig from public.profiles order by username");
const sig = Object.fromEntries((r.rows || []).map((x) => [x.id, x.avatar_sig]));
check("everyone on the team can read the fingerprints", r.ok && Object.keys(sig).length === 3, r);
check("the fingerprint is the md5 of the picture", sig[U.gio] === md5(PIC), sig[U.gio]);
check("no picture: the md5 of nothing (still compares fine)", sig[U.tim] === md5(""), sig[U.tim]);
await as(db, U.gio, "update public.profiles set avatar = $1 where id = $2", [PIC2, U.gio]);
r = await as(db, U.tim, "select avatar_sig from public.profiles where id = $1", [U.gio]);
check("changing the picture changes the fingerprint by itself", r.ok && r.rows[0].avatar_sig === md5(PIC2), r);
r = await as(db, U.gio, "update public.profiles set avatar_sig = 'x' where id = $1", [U.gio]);
check("nobody can write the fingerprint (the database computes it)", !r.ok, r);
r = await as(db, U.james, "select public.team_health() as v");
check("the health check reports update 20", r.ok && r.rows[0].v.updates["20"] === true && r.rows[0].v.updates["19"] === true, r.ok ? r.rows[0].v.updates : r);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
