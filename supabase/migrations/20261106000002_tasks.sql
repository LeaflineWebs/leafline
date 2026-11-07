-- OPTIONAL second migration: lets calendar events be ticked off ("tasks completed" on the Team page).
-- The app works without it; ticks stay on that computer until this has been run, then upload by themselves.
alter table public.events add column if not exists done boolean not null default false;
alter table public.events add column if not exists done_at timestamptz;
alter table public.events add column if not exists done_by uuid references public.profiles(id);
create index if not exists events_done_idx on public.events (done_at) where done;

create or replace function public.stamp_done() returns trigger language plpgsql set search_path = '' as $$
begin
  if new.done and (tg_op = 'INSERT' or not old.done) then
    new.done_by := coalesce(auth.uid(), new.done_by);      -- always the person who actually ticked it
    new.done_at := coalesce(new.done_at, now());
  elsif not new.done then
    new.done_by := null; new.done_at := null;
  end if;
  return new;
end $$;
drop trigger if exists stamp_done on public.events;
create trigger stamp_done before insert or update on public.events for each row execute function public.stamp_done();
