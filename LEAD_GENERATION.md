# Lead generation: how it works today, and the zero-spend rule

**Status: OFF by default.** The switch is in **Settings → Lead generation**. Even when it's switched ON, Leafline sends
**no request to any paid service**. A "zero-spend lock" is built into the code (`LEADGEN` in the app), not just the settings.

## What exists today (free)
| Provider | Cost | Works on | State |
|---|---|---|---|
| Desktop Google Maps search (Find Leads) | $0, runs a browser on your PC | Windows app | Working, unchanged |
| Google Places API | Paid past free monthly caps; needs a Google Cloud billing account | Phone, website, desktop | **Locked**: the app refuses to call it |
| OpenStreetMap (Overpass API) | $0, no key | Phone, website, desktop | Planned, not built yet |

## Google Places API: what it would cost (checked November 2026)
From Google's own price list (USD per 1,000 requests, first tier):
- Text Search **Pro**: 5,000 free per month, then **$32**. **Enterprise**: 1,000 free, then **$35**.
- Place Details **Essentials**: 10,000 free, then $5. **Pro**: 5,000 free, then $17. **Enterprise**: 1,000 free, then **$20**.
- Phone numbers, websites and opening hours are the fields we need, and they are in the higher (Pro/Enterprise) tiers.

So a small team *could* stay inside the free caps, but:
1. Google needs a **billing account with a card on file** before any key works.
2. One busy week (or a bug, or a leaked key) goes past the free caps and is **billed automatically**.
3. The free caps are per SKU and can change.

That's why it stays locked. If you ever want to try it safely, set a **budget alert and a hard quota cap** (requests/day) in
Google Cloud *before* creating a key, and restrict the key to your website's address. Leafline would then need a small,
separate change to unlock it. Nothing here does that for you.

## Truly free option to build next: OpenStreetMap
The Overpass API is free and needs no key (fair use, about 10,000 requests a day per server). It can find businesses by type
inside a city. Phone numbers and hours are often missing, so it suits finding names and addresses better than ready-to-call
lists. It works the same on phones, the website and the desktop app.

## How the code is laid out (so a provider can be swapped later)
- `LEADGEN.providers` lists each provider with `paid`, `ready` and `desktop` flags.
- `LEADGEN.cfg()` reads the saved choice (per person, synced like other settings); `LEADGEN.status()` builds the text shown in Settings and on Find Leads.
- `LEADGEN.search()` is the single entry point. It throws when the switch is off, when the provider is paid (zero-spend lock), or when the provider isn't built.
- To add a provider, add an entry with `ready:true`, `paid:false` and implement the request inside `search()`. A paid provider stays blocked unless the lock is removed on purpose.
