// 14th update (11.15): invoices, invoice templates, team cards. Real migrations on a real Postgres.
// Run:  cd tests/pg && node test_invoices_sql.mjs
import { freshDb, addUser, as } from "./db.mjs";
import { randomUUID as uuid } from "crypto";

let ok = 0, fail = 0;
const check = (label, cond, extra) => { if (cond) { ok++; console.log("  PASS", label); } else { fail++; console.log("  FAIL", label, extra !== undefined ? JSON.stringify(extra).slice(0, 400) : ""); } };
const U = { omar: uuid(), gio: uuid(), tim: uuid(), gone: uuid(), kyle: uuid(), mubaraq: uuid() };
const db = await freshDb({ twice: true });
check("all migrations (1 to 14) run, and run again safely", true);
await addUser(db, U.omar, "omar", { role: "admin" }); await addUser(db, U.gio, "gio"); await addUser(db, U.tim, "tim");
await addUser(db, U.gone, "gone", { active: false });
await db.query("insert into public.leads (id, name, phone, status, owner_name, email, address) values ('L1', 'Maple Roofing', '519-555-0101', 'green', 'Sam Lee', 'sam@maple.ca', '1 King St, London ON')");
await db.query("insert into public.deals (id, client, upfront, monthly, months, lead_id, owner_id) values ($1, 'Maple Roofing', 1500, 99, 12, 'L1', $2)", [uuid(), U.gio]);
const v = async (who, sql, p = []) => { const r = await as(db, who && U[who], sql, p); return r.ok ? r.rows[0].v : r; };
const save = (who, o) => v(who, "select public.inv_save($1::jsonb) as v", [JSON.stringify(o)]);

// ---------- settings
let r = await v("gio", "select public.inv_settings() as v");
check("defaults: company name, CAD, no tax until an admin sets it, 14 days to pay", r.company_name === "Leafline Web Services" && r.currency === "CAD" && +r.tax_rate === 0 && r.default_due_days === 14 && r.etransfer_email === "", r);
r = await v("gio", "select public.inv_settings_set($1::jsonb) as v", [JSON.stringify({ etransfer_email: "pay@leaflineweb.com" })]);
check("a teammate can't change the invoice settings", r.ok === false && /administrator/.test(r.error), r);
r = await v("omar", "select public.inv_settings_set($1::jsonb) as v", [JSON.stringify({ etransfer_email: "pay@leaflineweb.com", tax_rate: 13, tax_number: "123456789 RT0001" })]);
check("an admin sets the e-Transfer email and HST", r.etransfer_email === "pay@leaflineweb.com" && +r.tax_rate === 13 && r.tax_number === "123456789 RT0001", r);
r = await v("omar", "select public.inv_settings_set($1::jsonb) as v", [JSON.stringify({ etransfer_email: "not an email" })]);
check("a bad e-Transfer email is refused", r.ok === false && /email/.test(r.error), r);
r = await v("omar", "select public.inv_settings_set($1::jsonb) as v", [JSON.stringify({ tax_rate: 99 })]);
check("a silly tax rate is refused", r.ok === false, r);
r = await v("omar", "select public.inv_settings_set($1::jsonb) as v", [JSON.stringify({ hacker: 1 })]);
check("unknown settings are refused", r.ok === false && /Unknown/.test(r.error), r);
r = await v(null, "select public.inv_settings() as v");
check("signed-out visitors can't read the settings (e-Transfer email stays private)", r.ok === false || r === null, r);
r = await v("gone", "select public.inv_settings() as v");
check("a deactivated person gets nothing", r === null || r.ok === false, r);

// ---------- create
const items = [{ description: "Website design", details: "5 pages", qty: 1, unit_price: 1200 }, { description: "Hosting", qty: 12, unit_price: 25.5 }, { description: "", unit_price: 0 }];
r = await save("gio", { client_name: "Maple Roofing", lead_id: "L1", issue_date: "2026-11-01", due_date: "2026-11-15", items, discount_kind: "percent", discount_value: 10, tax_rate: 13 });
check("a teammate creates an invoice; blank rows are dropped", r.number === "LF-2026-0001" && r.status === "draft" && r.items.length === 2, r);
// 1200 + 306 = 1506; 10% = 150.60; base 1355.40; 13% = 176.20 (176.202); total 1531.60
check("totals are calculated in the database", +r.subtotal === 1506 && +r.discount_total === 150.6 && +r.tax_total === 176.2 && +r.total === 1531.6, [r.subtotal, r.discount_total, r.tax_total, r.total]);
const inv1 = r;
r = await save("tim", { client_name: "Oak Plumbing", issue_date: "2026-11-02", due_date: "2026-11-02", items: [{ description: "Logo", qty: 1, unit_price: 300, taxable: false }], tax_rate: 13, status: "sent" });
check("numbers count up, issued straight away, untaxed items pay no tax", r.number === "LF-2026-0002" && r.status === "sent" && +r.tax_total === 0 && +r.total === 300, r);
const inv2 = r;
r = await save("gio", { client_name: "Cedar", due_date: "2026-11-01", issue_date: "2026-11-05", items });
check("the due date can't be before the invoice date", r.ok === false && /due date/.test(r.error), r);
r = await save("gio", { client_name: "Cedar", due_date: "2026-12-01", items: [] });
check("an invoice needs at least one item", r.ok === false && /item/.test(r.error), r);
r = await save("gio", { client_name: "Cedar", due_date: "2026-12-01", items: [{ qty: 1, unit_price: 50 }] });
check("every priced item needs a description", r.ok === false && /description/.test(r.error), r);
r = await save("gio", { client_name: "Cedar", due_date: "2026-12-01", items: [{ description: "X", qty: "abc", unit_price: 5 }] });
check("a quantity that isn't a number is refused", r.ok === false && /numbers/.test(r.error), r);
r = await save("gio", { client_name: "", due_date: "2026-12-01", items });
check("a client name is required", r.ok === false && /client/.test(r.error), r);
r = await save("gio", { client_name: "Cedar", due_date: "2026-12-01", items, discount_kind: "amount", discount_value: 99999 });
check("an amount discount can't go below zero", +r.discount_total === 1506 && +r.total === 0, [r.discount_total, r.total]);
await v("gio", "select public.inv_delete($1) as v", [r.id]);
r = await save("gone", { client_name: "Cedar", due_date: "2026-12-01", items });
check("a deactivated person can't create invoices", r.ok === false, r);

// ---------- who sees what
r = await v("gio", "select public.inv_list() as v");
check("a teammate sees only the invoices they made", r.invoices.length === 1 && r.invoices[0].id === inv1.id && r.admin === false, r);
r = await v("omar", "select public.inv_list() as v");
check("an admin sees every invoice", r.invoices.length === 2 && r.admin === true, r.invoices && r.invoices.length);
check("an issued invoice past its due date shows as overdue", r.invoices.find((x) => x.id === inv2.id).overdue === true);
r = await v("tim", "select public.inv_get($1) as v", [inv1.id]);
check("another teammate can't open someone else's invoice", r.ok === false && /not found/.test(r.error), r);
r = await as(db, U.tim, "select count(*)::int as n from public.invoices");
check("reading the table directly also only shows your own", r.ok && r.rows[0].n === 1, r);
r = await as(db, U.gio, "update public.invoices set total = 1 where id = $1", [inv1.id]);
check("nobody changes the table directly (no update policy)", r.ok && r.affected === 0, r);
r = await as(db, U.gio, "insert into public.invoices (number, client_name, due_date, items) values ('X-1', 'Hack', '2026-12-01', '[]')");
check("nobody inserts into the table directly", r.ok === false, r);
r = await v(null, "select public.inv_list() as v");
check("signed-out visitors get nothing", r.ok === false, r);
r = await as(db, U.gio, "select public.inv_totals('[]'::jsonb, 'none', 0, 0)");
check("the internal helpers can't be called from the app", r.ok === false, r);

// ---------- edit, conflicts, status
r = await save("gio", { ...inv1, items: inv1.items, client_name: "Maple Roofing Ltd", version: inv1.version });
check("the creator edits their invoice", r.client_name === "Maple Roofing Ltd" && r.version === inv1.version + 1, r);
r = await save("gio", { ...inv1, client_name: "Stale", version: inv1.version });
check("saving an old copy is refused (someone else changed it)", r.ok === false && /changed/.test(r.error), r);
r = await save("tim", { ...inv1, client_name: "Tim was here", version: undefined });
check("another teammate can't edit it", r.ok === false && /not found/.test(r.error), r);
r = await v("gio", "select public.inv_set_status($1, 'sent') as v", [inv1.id]);
check("the creator issues it", r.status === "sent" && r.sent_at, r);
r = await v("gio", "select public.inv_set_status($1, 'void') as v", [inv1.id]);
check("only an admin can void", r.ok === false && /administrator/.test(r.error), r);
r = await v("gio", "select public.inv_pay($1, 100, '2026-11-03', 'e-Transfer', 'x', null) as v", [inv1.id]);
check("only an admin can mark it paid", r.ok === false && /administrator/.test(r.error), r);
r = await v("omar", "select public.inv_pay($1, 1531.60, '2099-01-01', 'e-Transfer', 'LF-2026-0001', null) as v", [inv1.id]);
check("a payment date in the future is refused", r.ok === false, r);
r = await v("omar", "select public.inv_pay($1, 1531.60, '2026-11-03', 'e-Transfer', 'CA1234', 'Autodeposit') as v", [inv1.id]);
check("an admin marks it paid, with the payment details", r.status === "paid" && +r.paid_amount === 1531.6 && r.paid_method === "e-Transfer" && r.paid_ref === "CA1234" && r.paid_by_name === "Omar", r);
r = await save("gio", { ...inv1, version: undefined });
check("a paid invoice can't be edited", r.ok === false && /paid/.test(r.error), r);
r = await v("gio", "select public.inv_delete($1) as v", [inv1.id]);
check("only drafts can be deleted", r.ok === false && /drafts/.test(r.error), r);
r = await v("omar", "select public.inv_unpay($1) as v", [inv1.id]);
check("an admin can undo a payment", r.status === "sent" && r.paid_amount === null, r);
r = await v("omar", "select public.inv_set_status($1, 'void', 'Client cancelled') as v", [inv2.id]);
check("an admin voids an invoice with a reason", r.status === "void" && r.void_reason === "Client cancelled", r);

// ---------- duplicate
r = await v("gio", "select public.inv_duplicate($1) as v", [inv1.id]);
check("duplicating makes a new draft with a new number and the same items", r.status === "draft" && r.number === "LF-2026-0003" && r.items.length === 2 && r.client_name === "Maple Roofing Ltd", r);
check("...dated today with the same days to pay", (new Date(r.due_date) - new Date(r.issue_date)) / 864e5 === 14, [r.issue_date, r.due_date]);
r = await v("tim", "select public.inv_duplicate($1) as v", [inv1.id]);
check("you can't duplicate an invoice you can't see", r.ok === false, r);

// ---------- clients
r = await v("gio", "select public.inv_clients('maple') as v");
check("client suggestions come from past invoices, deals and leads", ["invoice", "deal", "lead"].every((s) => r.some((x) => x.source === s)), r);
const lead = r.find((x) => x.source === "lead");
check("a lead's details fill in (owner, email, address)", lead && lead.contact === "Sam Lee" && lead.email === "sam@maple.ca" && lead.address.startsWith("1 King"), lead);
r = await v("tim", "select public.inv_clients('maple') as v");
check("suggestions never include someone else's invoices", !r.some((x) => x.source === "invoice"), r);
r = await v("gio", "select public.inv_clients('100%_') as v");
check("wildcards in the search are treated as text", Array.isArray(r) && r.length === 0, r);

// ---------- templates
const tpl = { name: "Website development", category: "Websites", items: [{ description: "Design", qty: 1, unit_price: 1000 }], payment_terms: "50% deposit", terms: "Terms text", due_days: 7 };
r = await v("gio", "select public.inv_tpl_save($1::jsonb) as v", [JSON.stringify(tpl)]);
check("a teammate can't make templates", r.ok === false && /administrator/.test(r.error), r);
r = await v("omar", "select public.inv_tpl_save($1::jsonb) as v", [JSON.stringify(tpl)]);
check("an admin makes a template", r && r.id, r);
const tid = r.id;
r = await v("gio", "select public.inv_tpl_list() as v");
check("everyone can use the templates", r.length === 1 && r[0].name === "Website development" && r[0].payment_terms === "50% deposit" && r[0].due_days === 7, r);
r = await save("gio", { client_name: "Birch", due_date: "2026-12-01", items: tpl.items, template_id: tid, payment_terms: tpl.payment_terms, terms: tpl.terms });
check("an invoice remembers its template", r.template_name === "Website development" && r.terms === "Terms text", r);
r = await v("omar", "select public.inv_tpl_archive($1, true) as v", [tid]);
r = await v("gio", "select public.inv_tpl_list() as v");
check("archived templates are kept (old invoices still point at them)", r.length === 1 && r[0].archived === true, r);
r = await as(db, U.omar, "delete from public.invoice_templates where id = $1", [tid]);
check("templates can't be deleted directly, even by an admin", r.ok && r.affected === 0, r);

// ---------- team cards
r = await v("gio", "select public.team_card_set($1, 'Sales', 'Cold calls', 'Calling, CRM', '519-555-0199', 'gio@leaflineweb.com') as v", [U.gio]);
check("you fill in your own card", r.ok === true, r);
r = await v("gio", "select public.team_card_set($1, 'Boss', null, null, null, null) as v", [U.tim]);
check("you can't change someone else's card", r.ok === false && /own card/.test(r.error), r);
r = await v("omar", "select public.team_card_set($1, 'Sales', 'Follow-ups', null, null, null) as v", [U.tim]);
check("an admin can fill in anyone's card", r.ok === true, r);
r = await v("gio", "select public.team_card_set($1, null, null, null, 'call me', null) as v", [U.gio]);
check("a bad phone number is refused", r.ok === false && /phone/.test(r.error), r);
r = await v("tim", "select public.team_cards() as v");
const g = r.find((x) => x.id === U.gio);
check("every teammate sees the cards (department, skills, contact, status)", r.length === 4 && g.department === "Sales" && g.skills === "Calling, CRM" && g.work_email === "gio@leaflineweb.com" && g.active === true, r);
check("deactivated people show as not active", r.find((x) => x.id === U.gone).active === false);
r = await v(null, "select public.team_cards() as v");
check("signed-out visitors see no cards", Array.isArray(r) && r.length === 0 || r.ok === false, r);
r = await as(db, U.gio, "update public.profiles set role = 'admin' where id = $1", [U.gio]);
check("filling in a card never lets anyone make themselves admin", r.ok === false, r);

// ---------- Kyle and Mubaraq: regular accounts, exactly like the other starters
await addUser(db, U.kyle, "kyle"); await addUser(db, U.mubaraq, "mubaraq");
r = await db.query("select username, role, active from public.profiles where username in ('kyle', 'mubaraq') order by username");
check("Kyle and Mubaraq are regular employees, not admins", r.rows.length === 2 && r.rows.every((x) => x.role === "employee" && x.active), r.rows);
r = await v("kyle", "select public.inv_settings_set($1::jsonb) as v", [JSON.stringify({ footer: "x" })]);
check("Kyle can't change admin settings", r.ok === false, r);
r = await v("mubaraq", "select public.inv_list() as v");
check("Mubaraq starts with no invoices and no admin view", r.invoices.length === 0 && r.admin === false, r);
r = await v("kyle", "select public.team_cards() as v");
check("they appear in the team", ["Kyle", "Mubaraq"].every((n) => r.some((x) => x.name === n)), r.map((x) => x.name));

// ---------- feed + audit
r = await db.query("select summary from public.activity where kind = 'invoice' order by id");
check("issuing and paying show in the activity feed, without amounts", r.rows.some((x) => /issued invoice LF-2026-0001/.test(x.summary)) && r.rows.some((x) => /was paid/.test(x.summary)) && !r.rows.some((x) => /\$/.test(x.summary)), r.rows);
r = await db.query("select count(*)::int as n from public.audit_log where table_name in ('invoices', 'invoice_templates')");
check("every invoice and template change is in the audit log", r.rows[0].n >= 10, r.rows);
console.log(`\n${ok} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
