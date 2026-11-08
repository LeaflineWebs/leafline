// A local Postgres (PGlite) with every Supabase migration applied, plus a helper to act as a signed-in teammate
// exactly like PostgREST does: role "authenticated" and the user's id as the JWT subject.
import { PGlite } from "@electric-sql/pglite";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, "..", "..");

export async function freshDb({ twice = false } = {}) {
  const db = new PGlite();
  await db.exec(fs.readFileSync(path.join(HERE, "supabase_stubs.sql"), "utf8"));
  const dir = path.join(REPO, "supabase", "migrations");
  const files = fs.readdirSync(dir).filter((f) => f.endsWith(".sql")).sort();
  for (let k = 0; k < (twice ? 2 : 1); k++)
    for (const f of files) {
      try { await db.exec(fs.readFileSync(path.join(dir, f), "utf8")); }
      catch (e) { throw new Error(`${f} (run ${k + 1}): ${e.message}`); }
    }
  return db;
}

export async function addUser(db, id, username, { role = "employee", active = true } = {}) {
  await db.query("insert into auth.users (id, email) values ($1, $2) on conflict do nothing", [id, username + "@leaflineweb.com"]);
  await db.query(`insert into public.profiles (id, username, display_name, role, active, must_change_password)
                  values ($1, $2, $3, $4, $5, false) on conflict (id) do update set role = excluded.role, active = excluded.active, display_name = excluded.display_name`,
    [id, username, username[0].toUpperCase() + username.slice(1), role, active]);
}

// Run one statement as a signed-in user (or anonymous when uid is null). Errors are returned, not thrown.
let queue = Promise.resolve();
export function as(db, uid, sql, params = []) {
  const run = async () => {
    try {
      return await db.transaction(async (tx) => {
        await tx.query(`select set_config('request.jwt.claim.sub', $1, true)`, [uid || ""]);
        await tx.exec(`set local role ${uid ? "authenticated" : "anon"}`);
        const r = await tx.query(sql, params);
        return { ok: true, rows: r.rows, affected: r.affectedRows };
      });
    } catch (e) { return { ok: false, error: e.message, code: e.code }; }
  };
  const p = queue.then(run, run); queue = p.then(() => {}, () => {}); return p;
}
