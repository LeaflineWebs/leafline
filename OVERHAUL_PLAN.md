# Leafline overhaul plan (12.0)

Working plan for the full overhaul you asked for on 2026-11-18. It's built in stages, and each stage is tested and shipped on its own,
so nothing big lands at once and every existing feature keeps working the whole way through.

## What exists today (discovery)

**Two apps, one page.** The PC app (Electron + Python engine with a local SQLite copy that syncs) and the website (`docs/`,
engine `web_src/engine.js`) share one page (`UI_HTML` in `backend/leafline_backend.py`) plus feature modules
(messages, invoices, reminders, glass, splits, productivity, email). Every feature has to work on both.

**15 pages, flat sidebar:** Dashboard, Team, Leaderboard, Announcements, Messages, Find Leads, Called Leads, Pipeline,
Calendar, Call Log, Notes, Profits, Invoices, Admin, Settings. On phones: a bottom bar with Home, Messages, Leads,
Called, Calendar, More.

**Money today.** A *deal* holds the client name, the upfront and monthly price, the number of months, notes, the linked
lead and an assigned teammate. Payments are *worked out* from that schedule and ticked off one by one ("confirmed").
Invoices can point at a deal or lead. Profit splits hang off deals. Expenses are separate company costs.
**There is no "client" anywhere:** the same business shows up as a lead, a deal name and an invoice "client_name" text,
with nothing tying them together.

## Problems found so far
1. On computers **two navigations show at once** (sidebar + floating bottom bar). The bottom bar covers page content
   (the dashboard's lower cards sit under it).
2. The **sidebar is one flat list of 15 items**, with no grouping. Selling, clients/money and team features are mixed together.
3. **No client management.** Who you work for, what you do for them, what they pay and what they owe is spread over
   Profits (deals), Invoices and Called Leads.
4. Reminders button blocked by notifications (fixed in 11.22.1).
5. **Called Leads repeats itself**: four big count cards (Meeting set up 12, Interested 12...) sit above columns
   whose headers already show the same counts. On phones the filter row runs off the right edge (sort and type
   pickers can't be reached without swiping).
6. **Pipeline** columns run past the screen at every size below 1920 wide; there's no visible cue that it scrolls sideways.
7. **Invoices on phones**: the tab buttons run off the right edge.
8. **Profits**: four large summary cards take the whole first screen; the useful parts (this week's payments, what
   to confirm) start below the fold. Same on the dashboard: the lower cards are hidden under the floating bar.
9. **Mixed names** for the same thing: "Announcements" in the sidebar vs "News" on phones, "Leaderboard" vs "Ranks",
   "Profits" page titled "Money tracker".
10. Top bar on computers has 9 controls (search, theme, sync, bell, script, reminders, account, sign out); account and
    sign out duplicate the sidebar's avatar and Settings.

Audit method: every page screenshotted and machine-checked (sideways overflow, clipped text, overlapping controls)
at 1920, 1440, 1280, 820, 390 and 360 widths; screenshots in the session scratchpad.

## Status (2026-11-18, version 12.0.0, not pushed yet)
- Done: Clients (database update 19, page, profile, editor, set up from deals, archive/delete, connections to the
  dashboard, Profits, Pipeline, invoices, reminders and email); grouped sidebar and phone More menu; no duplicate
  floating bar on computers; sidebar fits from 1280 x 720 up; Called Leads, Pipeline, Invoices and Profits layout
  fixes; More menu closes when you tap the page you're on; invoices made from a deal now link to that deal.
- Checked: every page at 1920, 1440, 1280, 820, 390 and 360 wide (no sideways scrolling, clipped text or
  overlapping controls); 27 app test suites, 11 database suites and the email function tests all pass
  (test_import needs the old upload files and can't run on this PC).
- Kept on purpose: "News" / "Ranks" as the short phone labels (the full names don't fit the phone bar); the top
  bar's buttons (each is used).
- Still open: Stage 5 performance pass (duplicate requests / redraws), and a client "next date" showing on the Calendar.

## Stages

### Stage 1: Clients (the most important part)
- **Database update 19** (additive only, nothing changed or deleted):
  - `clients` table: name, business, contact person, phone, email, address, status
    (active / pending / inactive / completed), priority, tags, notes, assigned teammates, start date,
    linked lead, archived_at.
  - `client_activity` table: notes, conversations and updates on a client's timeline.
  - `deals.client_id` (nullable): links each deal to its client. **Deals stay the single source of truth for services
    and prices; payments stay the confirmed payments on deals; invoices link through `client_id` too.** No money is copied.
  - Row-level security on everything; writes only through checked functions (like invoices and reminders).
  - A safe one-time *suggestion* (not automatic) to group existing deals into clients by name, which you confirm.
- **Clients page**: summary strip (active clients, monthly recurring, collected, outstanding, overdue), search, filters
  (status, service, teammate, payment status, tag), sorting, list on computers / cards on phones.
- **Client profile**: Overview, Services (its deals), Money (payment history from confirmed payments + invoices,
  outstanding, upcoming, total), Activity (timeline: notes, payments, invoices, service changes), Team.
- **Actions**: add, edit, archive, reactivate, delete (with confirmation; deals and invoices are kept, just unlinked),
  add a service, record a payment (confirms the deal payment), make an invoice (prefilled), add a note or reminder.
- **Connections**: "Won" in the Pipeline or a deal in Profits offers to create or link the client; invoices pick the
  client; reminders can point at a client; the dashboard shows clients needing attention and overdue payments.

### Stage 2: Navigation and layout
- Group the sidebar: **Work** (Dashboard, Find Leads, Called Leads, Pipeline, Calendar, Call Log) ·
  **Clients & money** (Clients, Profits, Invoices) · **Team** (Team, Leaderboard, Announcements, Messages, Notes) ·
  Admin, Settings.
- Computers: sidebar only (the floating bar is hidden). Phones: bottom bar (Home, Leads, Called, Clients, More), with the
  More sheet grouped the same way as the sidebar.
- One page header pattern (title, summary, primary action on the right) and consistent card, spacing and type sizes.

### Stage 3: Page-by-page cleanup
Each page: the important information first, secondary details folded into expandable sections, one primary action,
and tables turned into cards on phones. Fix every clipped, overlapping or overflowing element the audit finds at
1920, 1440, 1280, 820 (tablet), 390 (iPhone) and 360 (small phone) widths.

### Stage 4: Dashboard
Today at a glance: calls and streak, reminders due, meetings, **clients needing attention, overdue payments**,
money this month, recent activity, and quick actions (new search, add client, record payment, new invoice).

### Stage 5: Performance and final pass
Remove duplicate requests and needless redraws, then do a full walkthrough at every size with the console checked for
errors, and run the whole test suite (currently 26 suites, about 1,200 checks) plus new client tests.

## Rules followed throughout
No database resets, no deleted records, no destructive migrations, RLS always on, no credentials in the app,
every existing feature kept. Each stage ships as its own version after its tests pass, and only when you say to push.
