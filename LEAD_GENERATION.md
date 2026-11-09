# Lead generation: how new leads are found

## On the PC (Windows app)
Find Leads opens Google Maps in a browser window on your PC, reads each business (phone, website, hours, rating) and
looks for owner names on their websites. Free, unchanged.

## On a phone or the website (11.11)
Find Leads has the same form ("Find new leads" on phones). It works in one of two ways:

1. **Google Places API**, once an admin saves a key in **Settings > Finding leads on phones**.
   - Same data as Google Maps. Owner names aren't looked up (a phone can't read other websites), so they show N/A.
   - One search = 1 to 3 Google requests (20 businesses each, up to 60).
   - Cost (Google's price list, November 2026): requests that include phone numbers are "Text Search Enterprise":
     **1,000 free per month**, then $35 per 1,000.
   - Leafline's own lock: the database counts every request and refuses past the **monthly limit** set in Settings
     (default 900), for the whole team together. Nothing is sent to Google once it's reached.
   - Google's own lock (recommended): in Google Cloud set the Text Search **requests per day** quota to 30, restrict the
     key to your website's address and to "Places API (New)", and add a $1 budget alert. The in-app guide ("How to get
     a free key") walks through it.
2. **Your PC runs it**: with no key (or the limit used up, or Google refusing the key), the phone hands the search to
   *your own* Leafline app on your PC. It runs the normal Google Maps search there and the leads appear on the phone.
   Your PC needs Leafline open and signed in as you. Nobody else's PC ever runs your search. Requests that no PC picks
   up within 30 minutes expire. Stop on the phone stops the PC too.

Either way: one lead per phone number, and businesses someone already called are left out (same as the PC).
Needs the 12th database update (`supabase/migrations/20261109000012_phone_search.sql`, included in RUN_IN_SUPABASE.sql).
