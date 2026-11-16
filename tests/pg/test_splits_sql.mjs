// 16th update (11.18): profit splits. Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_splits_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 300) : ""); } };
const U = { omar: uuid(), jay: uuid(), tim: uuid(), james: uuid(), gone: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 16) run, and run again safely", true);
await addUser(db, U.omar, "omar"); await addUser(db, U.jay, "jay"); await addUser(db, U.tim, "tim");
await addUser(db, U.james, "james", { role: "admin" }); await addUser(db, U.gone, "gone", { active: false });
const D = uuid(), D2 = uuid();
await db.query("insert into public.deals (id, client, upfront, monthly, months, closed_at, owner_id) values ($1, 'Maple Roofing', 1200, 300, 12, '2026-11-01', $2)", [D, U.omar]);
await db.query("insert into public.deals (id, client, upfront, closed_at, owner_id) values ($1, 'Oak Plumbing', 500, '2026-11-02', $2)", [D2, U.tim]);
const v = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows[0].v : r; };
const set = (who, deal, key, shares, dflt = true) => v(who, "select public.deal_split_set($1, $2, $3::jsonb, $4) as v", [deal, key, JSON.stringify(shares), dflt]);
const rows = async (who = "tim") => { const r = await as(db, U[who], "select deal_id, pay_key, shares from public.deal_splits order by pay_key"); return r.ok ? r.rows : r; };

let r = await set("omar", D, "2026-11-01:upfront", [{ id: U.omar, pct: 60 }, { id: U.jay, pct: 40 }]);
check("Omar (the deal is credited to him) splits a confirmed payment 60/40 with Jay", r.ok === true && r.shares.length === 2 && r.shares[0].pct == 60, r);
let all = await rows();
check("the split is saved for that payment AND as the deal's default", all.length === 2 && all.some((x) => x.pay_key === "2026-11-01:upfront") && all.some((x) => x.pay_key === ""), all);
check("everyone signed in can read splits (the leaderboard needs them)", Array.isArray(all) && all.length === 2, all);
r = await as(db, null, "select count(*)::int as n from public.deal_splits");
check("signed-out visitors can't read them", !r.ok || r.rows[0].n === 0, r);
r = await as(db, U.gone, "select count(*)::int as n from public.deal_splits");
check("deactivated accounts can't read them", !r.ok || r.rows[0].n === 0, r);

r = await set("omar", D, "2026-12-01:monthly", [{ id: U.omar, pct: 50 }, { id: U.jay, pct: 50 }], false);
all = await rows();
check("a split just for one payment can leave the default alone", all.find((x) => x.pay_key === "")?.shares[0].pct == 60 && all.find((x) => x.pay_key === "2026-12-01:monthly")?.shares[0].pct == 50, all);
r = await set("omar", D, "2026-11-01:upfront", [{ id: U.jay, pct: 100 }]);
all = await rows();
check("changing a split replaces it (no duplicates)", all.filter((x) => x.pay_key === "2026-11-01:upfront").length === 1 && all.find((x) => x.pay_key === "2026-11-01:upfront").shares[0].id === U.jay, all);
r = await set("omar", D, "", [{ id: U.omar, pct: 33.33 }, { id: U.jay, pct: 33.33 }, { id: U.tim, pct: 33.34 }]);
check("three-way split with decimals that add up to exactly 100", r.ok === true, r);

// the rules
r = await set("jay", D, "2026-11-01:upfront", [{ id: U.jay, pct: 100 }]);
check("Jay (in the split, but the deal isn't credited to him) can't change it", r.ok === false && /Only an admin or the person this deal is credited to/.test(r.error), r);
r = await set("tim", D, "", [{ id: U.tim, pct: 100 }]);
check("Tim can't give himself someone else's deal", r.ok === false && /Only an admin/.test(r.error), r);
r = await set("james", D2, "2026-11-02:upfront", [{ id: U.tim, pct: 70 }, { id: U.james, pct: 30 }]);
check("an admin can split any deal", r.ok === true, r);
r = await set("omar", D, "", [{ id: U.omar, pct: 60 }, { id: U.jay, pct: 30 }]);
check("percents that don't add up to 100 are refused", r.ok === false && /add up to 100 \(they add up to 90\)/.test(r.error), r);
r = await set("omar", D, "", [{ id: U.omar, pct: 110 }, { id: U.jay, pct: -10 }]);
check("a percent over 100 or below 0 is refused", r.ok === false && /more than 0 and at most 100/.test(r.error), r);
r = await set("omar", D, "", [{ id: U.omar, pct: 0 }, { id: U.jay, pct: 100 }]);
check("a 0% part is refused", r.ok === false && /more than 0/.test(r.error), r);
r = await set("omar", D, "", [{ id: U.omar, pct: 50.555 }, { id: U.jay, pct: 49.445 }]);
check("more than 2 decimals is refused", r.ok === false && /2 decimals/.test(r.error), r);
r = await set("omar", D, "", [{ id: U.omar, pct: 50 }, { id: U.omar, pct: 50 }]);
check("the same person twice is refused", r.ok === false && /only be in the split once/.test(r.error), r);
r = await set("omar", D, "", [{ id: U.omar, pct: 50 }, { id: U.gone, pct: 50 }]);
check("a deactivated teammate can't get a share", r.ok === false && /active teammates only/.test(r.error), r);
r = await set("omar", D, "", [{ id: uuid(), pct: 100 }]);
check("someone who isn't on the team can't get a share", r.ok === false && /active teammates only/.test(r.error), r);
r = await set("omar", D, "", [{ id: "not-a-uuid", pct: 100 }]);
check("rubbish ids are refused", r.ok === false && /teammate and a percent/.test(r.error), r);
r = await set("omar", D, "", []);
check("an empty split is refused", r.ok === false && /between 1 and 8/.test(r.error), r);
r = await set("omar", D, "next tuesday", [{ id: U.omar, pct: 100 }]);
check("a made-up payment key is refused", r.ok === false && /payment is not valid/.test(r.error), r);
r = await set("omar", uuid(), "", [{ id: U.omar, pct: 100 }]);
check("a deal that doesn't exist is refused", r.ok === false && /deal was not found/.test(r.error), r);
r = await set(null, D, "", [{ id: U.omar, pct: 100 }]);
check("signed out: refused", r.ok === false, r);
r = await set("gone", D, "", [{ id: U.gone, pct: 100 }]);
check("deactivated account: refused", r.ok === false, r);

// nobody can go around the function
r = await as(db, U.omar, "insert into public.deal_splits (deal_id, pay_key, shares) values ($1, '2026-11-15:upfront', '[{\"id\":\"x\",\"pct\":100}]')", [D]);
check("nobody can insert into the table directly", r.ok === false, r);
r = await as(db, U.james, "update public.deal_splits set shares = '[]' where deal_id = $1", [D]);
check("not even an admin can edit it directly (writes go through the checks)", !r.ok || r.affected === 0, r);
r = await as(db, U.james, "delete from public.deal_splits where deal_id = $1", [D]);
check("...or delete it directly", !r.ok || r.affected === 0, r);

// feed + audit
r = await db.query("select summary from public.activity where kind = 'credit' order by id");
const feed = r.rows.map((x) => x.summary);
check("the team sees who split what in Activity", feed.some((s) => s === "Omar split Maple Roofing: Omar 60%, Jay 40%"), feed);
check("decimals read nicely and money is never shown in Activity", feed.some((s) => s.includes("Omar 33.33%, Jay 33.33%, Tim 33.34%")) && !feed.some((s) => /\$|1200|300/.test(s)), feed);
r = await db.query("select count(*)::int as n from public.audit_log where table_name = 'deal_splits'");
check("every change is in the audit log", r.rows[0].n >= 5, r.rows);

// deleting a deal (admins only) removes its splits; nothing else is touched
await db.query("delete from public.deals where id = $1", [D2]);
all = await rows("james");
check("deleting a deal removes its splits", !all.some((x) => x.deal_id === D2) && all.some((x) => x.deal_id === D), all);

console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
