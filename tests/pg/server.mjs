// Test stand-in for the Supabase parts Messages uses, backed by a REAL Postgres (PGlite) with the real migrations:
//   * POST /rpc/<fn>              -> runs public.<fn>(...) as the signed-in user (role authenticated + JWT subject), like PostgREST
//   * storage: signed upload / signed download / remove, each checked against storage.objects row level security
//   * a Phoenix websocket that speaks the Supabase Realtime "postgres_changes" protocol, delivering only rows the
//     subscriber may read (the same membership rule the RLS policies use)
// The Python fake Supabase (tests/fake_supabase.py) forwards messaging calls here. Usage: node server.mjs  -> prints "READY <port>"
import http from "http";
import crypto from "crypto";
import { WebSocketServer } from "ws";
import { freshDb, as } from "./db.mjs";

const db = await freshDb();
const TABLES = ["conversations", "conversation_members", "messages", "message_reactions", "message_notifications", "pinned_messages"];
await db.exec(`create or replace function public._rt() returns trigger language plpgsql as $$
  declare r jsonb := case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end;
  begin perform pg_notify('rt', jsonb_build_object('table', tg_table_name, 'type', tg_op, 'record', r - 'content' - 'meta')::text); return null; end $$;`);
for (const t of TABLES) await db.exec(`drop trigger if exists _rt on public.${t}; create trigger _rt after insert or update or delete on public.${t} for each row execute function public._rt();`);

const tokens = new Map();                 // access token -> user id (pushed by the Python fake)
const files = new Map();                  // path -> {bytes, type}
const grants = new Map();                 // one-time upload / download tokens
const BUCKET = (await db.query("select file_size_limit, allowed_mime_types from storage.buckets where id = 'message-files'")).rows[0];
const sigs = new Map();                   // function name -> [{name, type}]
for (const r of (await db.query(`select p.proname, p.proargnames, array(select format_type(t, null) from unnest(p.proargtypes) t) as types
                                 from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and (p.proname like 'msg\\_%' or p.proname like 'inv\\_%' or p.proname like 'team\\_%')`)).rows)
  sigs.set(r.proname, (r.proargnames || []).map((n, i) => ({ name: n, type: r.types[i] })));

const send = (res, code, obj, type = "application/json") => {
  const b = Buffer.isBuffer(obj) ? obj : Buffer.from(JSON.stringify(obj === undefined ? null : obj));
  res.writeHead(code, { "Content-Type": type, "Content-Length": b.length, "Access-Control-Allow-Origin": "*" }); res.end(b);
};
const body = (req) => new Promise((ok) => { const c = []; req.on("data", (d) => c.push(d)); req.on("end", () => ok(Buffer.concat(c))); });
const pgErr = (res, r) => send(res, r.code === "42501" ? 403 : 400, { code: r.code || "P0001", message: r.error });
const lit = (v, type = "") => v === null || v === undefined ? null : Array.isArray(v) && type.endsWith("[]") ? "{" + v.map((x) => JSON.stringify(String(x))).join(",") + "}" : typeof v === "object" ? JSON.stringify(v) : String(v);

async function rpc(res, uid, fn, args) {
  const sig = sigs.get(fn);
  if (!sig || !uid) return send(res, 404, { code: "PGRST202", message: `Could not find the function public.${fn}` });
  const keys = Object.keys(args || {});
  if (keys.some((k) => !sig.find((a) => a.name === k))) return send(res, 404, { code: "PGRST202", message: `Could not find the function public.${fn} with those arguments` });
  const sql = `select public.${fn}(${keys.map((k, i) => `${k} => $${i + 1}::${sig.find((a) => a.name === k).type}`).join(", ")}) as v`;
  const r = await as(db, uid, sql, keys.map((k) => lit(args[k], sig.find((a) => a.name === k).type)));
  return r.ok ? send(res, 200, r.rows[0].v) : pgErr(res, r);
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://x"), raw = await body(req), uid = req.headers["x-uid"] || "";
  const j = () => { try { return JSON.parse(raw.toString() || "{}"); } catch (e) { return {}; } };
  try {
    if (u.pathname === "/sync") { const b = j(); tokens.clear(); for (const [k, v] of Object.entries(b.tokens || {})) tokens.set(k, v);
      for (const p of b.profiles || []) {
        await db.query("insert into auth.users (id, email) values ($1, $2) on conflict do nothing", [p.id, p.username + "@leaflineweb.com"]);
        await db.query(`insert into public.profiles (id, username, display_name, role, active, must_change_password) values ($1,$2,$3,$4,$5,false)
                        on conflict (id) do update set display_name = excluded.display_name, role = excluded.role, active = excluded.active`, [p.id, p.username, p.display_name, p.role, p.active]);
      }
      return send(res, 200, { ok: true }); }
    if (u.pathname.startsWith("/rpc/")) return rpc(res, uid, u.pathname.slice(5), j());
    if (u.pathname === "/storage/upload-sign") {           // like Supabase: refuses up front if you may not upload there
      const p = j().path;
      const t = await as(db, uid, `with x as (insert into storage.objects (bucket_id, name, owner) values ('message-files', $1, $2) returning 1) select count(*) from x`, [p, uid]);
      if (t.ok) await db.query("delete from storage.objects where bucket_id = 'message-files' and name = $1", [p]);
      if (!t.ok) return send(res, 403, { statusCode: "403", error: "Unauthorized", message: "new row violates row-level security policy" });
      const tok = crypto.randomUUID(); grants.set(tok, { kind: "up", path: p, uid });
      return send(res, 200, { url: `/object/upload/sign/message-files/${p}?token=${tok}`, token: tok });
    }
    if (u.pathname === "/storage/upload") {
      const g = grants.get(u.searchParams.get("token")); grants.delete(u.searchParams.get("token"));
      if (!g || g.kind !== "up") return send(res, 400, { statusCode: "400", error: "InvalidJWT", message: "invalid signature" });
      const type = String(req.headers["content-type"] || "").split(";")[0];
      if (raw.length > Number(BUCKET.file_size_limit)) return send(res, 413, { statusCode: "413", error: "Payload too large", message: "The object exceeded the maximum allowed size" });
      if (!BUCKET.allowed_mime_types.includes(type)) return send(res, 415, { statusCode: "415", error: "invalid_mime_type", message: `mime type ${type} is not supported` });
      const r = await as(db, g.uid, "insert into storage.objects (bucket_id, name, owner, metadata) values ('message-files', $1, $2, $3)", [g.path, g.uid, JSON.stringify({ size: raw.length, mimetype: type })]);
      if (!r.ok) return send(res, 403, { statusCode: "403", error: "Unauthorized", message: r.error });
      files.set(g.path, { bytes: raw, type }); return send(res, 200, { Key: "message-files/" + g.path });
    }
    if (u.pathname === "/storage/sign") {
      const b = j(), out = [];
      for (const p of b.paths || []) {
        const r = await as(db, uid, "select 1 from storage.objects where bucket_id = 'message-files' and name = $1", [p]);
        if (r.ok && r.rows.length && files.has(p)) { const tok = crypto.randomUUID(); grants.set(tok, { kind: "down", path: p, until: Date.now() + 1000 * (b.expiresIn || 60) });
          out.push({ path: p, signedURL: `/object/sign/message-files/${p}?token=${tok}`, error: null }); }
        else out.push({ path: p, signedURL: null, error: "Either the requested resource does not exist or you don't have access" });
      }
      return send(res, 200, out);
    }
    if (u.pathname === "/storage/get") {
      const g = grants.get(u.searchParams.get("token"));
      if (!g || g.kind !== "down" || g.until < Date.now() || !files.has(g.path)) return send(res, 400, { message: "invalid signature" });
      const f = files.get(g.path); return send(res, 200, f.bytes, f.type);
    }
    if (u.pathname === "/storage/remove") {
      const r = await as(db, uid, "delete from storage.objects where bucket_id = 'message-files' and name = any($1::text[]) returning name", [lit(j().prefixes || [], "text[]")]);
      if (!r.ok) return pgErr(res, r);
      for (const x of r.rows) files.delete(x.name);
      return send(res, 200, r.rows.map((x) => ({ name: x.name })));
    }
    send(res, 404, { message: "not found" });
  } catch (e) { send(res, 500, { message: String(e.message || e) }); }
});

// ---------------- realtime: Phoenix channels, postgres_changes
const wss = new WebSocketServer({ server, path: "/realtime/v1/websocket" });
const socks = new Set();
wss.on("connection", (ws, req) => {
  const s = { ws, uid: null, topics: new Map() }; socks.add(s);
  const out = (m) => { try { ws.send(JSON.stringify(m)); } catch (e) { } };
  ws.on("message", (data) => {
    let m; try { m = JSON.parse(String(data)); } catch (e) { return; }
    if (m.topic === "phoenix" && m.event === "heartbeat") return out({ topic: "phoenix", event: "phx_reply", payload: { status: "ok", response: {} }, ref: m.ref });
    if (m.event === "phx_join") {
      const who = tokens.get(m.payload && m.payload.access_token);
      if (!who) return out({ topic: m.topic, event: "phx_reply", payload: { status: "error", response: { reason: "Invalid token" } }, ref: m.ref, join_ref: m.join_ref });
      s.uid = who;
      const pc = ((m.payload.config || {}).postgres_changes || []).map((c, i) => ({ ...c, id: 1000 + i }));
      s.topics.set(m.topic, { joinRef: m.join_ref || m.ref, pc });
      out({ topic: m.topic, event: "phx_reply", payload: { status: "ok", response: { postgres_changes: pc } }, ref: m.ref, join_ref: m.join_ref });
      return out({ topic: m.topic, event: "system", payload: { status: "ok", message: "Subscribed to PostgreSQL", extension: "postgres_changes", channel: m.topic.replace(/^realtime:/, "") }, ref: null });
    }
    if (m.event === "access_token") { const who = tokens.get(m.payload && m.payload.access_token); if (who) s.uid = who; return; }
    if (m.event === "phx_leave") { s.topics.delete(m.topic); return out({ topic: m.topic, event: "phx_reply", payload: { status: "ok", response: {} }, ref: m.ref }); }
  });
  ws.on("close", () => socks.delete(s));
});
const allowed = async (uid, ev) => {
  const r = ev.record || {};
  if (ev.type === "DELETE") return true;                                       // like Supabase: deletes carry only the key, unchecked
  if (ev.table === "message_notifications") return r.user_id === uid;
  const conv = ev.table === "conversations" ? r.id : r.conversation_id;
  const q = await as(db, uid, "select public.msg_is_member($1) as ok", [conv]);
  return q.ok && q.rows[0].ok === true;
};
await db.listen("rt", async (payload) => {
  const ev = JSON.parse(payload);
  const keyOnly = (r) => Object.fromEntries(Object.entries(r).filter(([k]) => ["id", "conversation_id", "user_id", "message_id"].includes(k)));
  for (const s of socks) {
    if (!s.uid) continue;
    for (const [topic, t] of s.topics) {
      const ids = t.pc.filter((c) => (c.table === ev.table || c.table === "*") && (c.event === "*" || c.event === ev.type)).map((c) => c.id);
      if (!ids.length || !(await allowed(s.uid, ev))) continue;
      try { s.ws.send(JSON.stringify({ topic, event: "postgres_changes", ref: null, payload: { ids, data: { schema: "public", table: ev.table, type: ev.type, commit_timestamp: new Date().toISOString(),
        record: ev.type === "DELETE" ? {} : ev.record, old_record: ev.type === "DELETE" ? keyOnly(ev.record) : {} } } })); } catch (e) { }
    }
  }
});
server.listen(Number(process.argv[2] || 0), "127.0.0.1", () => console.log("READY " + server.address().port));
