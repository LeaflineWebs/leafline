-- Seventh migration (Leafline 11.3): "Confirm payment". Safe to run more than once.
-- A deal payment now counts toward the money made only after someone ticks it as really received.
-- The ticks are stored on the deal as a comma-separated list of "YYYY-MM-DD:upfront" / "YYYY-MM-DD:monthly" keys.
-- Until this is run, ticks stay on the computer that made them and upload by themselves afterwards.
alter table public.deals add column if not exists confirmed text not null default '';
do $$ begin
  alter table public.deals add constraint deals_confirmed_shape
    check (length(confirmed) < 20000 and confirmed ~ '^([0-9]{4}-[0-9]{2}-[0-9]{2}:(upfront|monthly)(,|$))*$');
exception when duplicate_object then null; end $$;
