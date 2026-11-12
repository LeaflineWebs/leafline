"""Leafline call reminders (11.16): set a reminder for the business you're calling (Find Leads, or a business pop-up on
Called Leads). It keeps a copy of the company details, the owner's name and your call notes. Reminders live behind the
clock button in the top bar, show as a pop-up when you open the app on their day, and appear as a notification in the
top right when their time comes while the app is open. Reminders are private to each person; the rules are enforced by
the database (supabase/migrations/20261112000015_reminders.sql)."""

REM_CSS = r'''
/* ================= Call reminders ================= */
#remBtn.due{animation:remPulse 2.4s var(--e-out,ease) infinite}
@keyframes remPulse{0%,70%,100%{box-shadow:var(--hi),0 6px 14px rgba(0,0,0,.25),0 0 0 1px var(--line)}35%{box-shadow:var(--hi),0 6px 14px rgba(0,0,0,.25),0 0 0 4px var(--accent-soft),0 0 22px var(--glow)}}
.remp{position:absolute;top:76px;right:28px;z-index:41;width:380px;max-height:min(70vh,560px);overflow:auto;padding:14px;border-radius:26px;background:var(--glass,var(--card2));
  -webkit-backdrop-filter:var(--blur,none);backdrop-filter:var(--blur,none);border:1px solid var(--line2,var(--line));box-shadow:var(--sh-lg,0 24px 50px rgba(0,0,0,.5)),var(--hi);
  transform-origin:top right;transform:translateY(-8px) scale(.96);opacity:0;pointer-events:none;transition:transform var(--d-pop,.25s) var(--e-spring,ease),opacity var(--d-pop,.25s) var(--e-out,ease)}
.remp.on{transform:none;opacity:1;pointer-events:auto}
.remp .rem-hd{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:2px 4px 10px}
.remp h4{font-size:15px;font-weight:800}
.remp .rem-sec{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:12px 6px 6px}
.remp .rem-sec.rem-od{color:#FF9AA0}
.remr{width:100%;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:2px 10px;align-items:center;padding:10px;border-radius:16px;text-align:left;transition:background-color var(--d-hover,.15s) var(--e-out,ease)}
.remr:hover{background:rgba(255,255,255,.05)}
.remr .rem-ri{grid-row:1/3;width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-hi)}
.remr .rem-ri .ic{width:18px;height:18px}.remr.rem-od .rem-ri{background:rgba(255,120,120,.14);color:#FF9AA0}.remr.done{opacity:.55}.remr.done b{text-decoration:line-through}
.remr b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px}
.remr small{grid-column:2;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.remr .rem-tm{grid-row:1/3;grid-column:3;font-size:12px;font-weight:700;color:var(--text2);text-align:right;white-space:nowrap}
.remr.rem-od .rem-tm{color:#FF9AA0}
.remp .empty{padding:24px 10px}
.remp details summary{cursor:pointer;font-size:12.5px;font-weight:700;color:var(--muted);margin:12px 6px 4px;list-style:none}
.remp details summary::-webkit-details-marker{display:none}
/* the reminder pop-up / details */
.remd .rem-rh{display:flex;gap:12px;align-items:center}
.remd .rem-rh .rem-ri{width:46px;height:46px;border-radius:15px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-hi);flex:none}
.remd .rem-rh .rem-ri .ic{width:22px;height:22px}
.remd .rem-when{font-size:13px;font-weight:700;color:var(--accent-hi);margin-top:2px}.remd .rem-when.rem-od{color:#FF9AA0}
.remd .rem-kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 14px;margin:16px 0 0;font-size:13.5px}
.remd .rem-kv dt{color:var(--muted)}.remd .rem-kv dd{margin:0;min-width:0;overflow-wrap:anywhere}
.remd .rem-nt{margin-top:14px;padding:12px 14px;border-radius:16px;background:rgba(0,0,0,.16);border:1px solid var(--line);white-space:pre-wrap;font-size:13.5px;line-height:1.5}
.remd .rem-nt h5{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
.rem-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}
.rem-acts .rem-sp{flex:1}
.rem-quick{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 0}
.rem-quick .chip.on{background:var(--accent-soft);color:var(--accent-hi);border-color:var(--accent-line)}
.rem-biz{display:flex;gap:12px;align-items:center;padding:12px 14px;border-radius:18px;background:rgba(0,0,0,.16);border:1px solid var(--line);margin-top:14px}
.rem-biz .av{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;font-weight:800;color:#fff;flex:none}
.rem-biz b{display:block}.rem-biz small{display:block;color:var(--muted);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.remlist{display:flex;flex-direction:column;gap:6px;margin-top:14px;max-height:min(56vh,520px);overflow:auto}
.remlist .remr{background:rgba(0,0,0,.14);border:1px solid var(--line)}
/* top-right notification */
.remnotes{position:fixed;top:16px;right:16px;z-index:calc(var(--z-modal,60) + 5);display:flex;flex-direction:column;gap:10px;width:min(360px,calc(100vw - 32px));pointer-events:none}
.remn{pointer-events:auto;border-radius:22px;padding:14px 14px 12px;background:var(--glass,var(--card2));-webkit-backdrop-filter:var(--blur,none);backdrop-filter:var(--blur,none);
  border:1px solid var(--accent-line);box-shadow:var(--sh-lg,0 24px 50px rgba(0,0,0,.5)),0 0 30px var(--glow-soft);animation:remIn .5s var(--e-spring,cubic-bezier(.22,1,.36,1)) both}
.remn.out{animation:remOut .25s var(--e-in,ease) both}
@keyframes remIn{from{opacity:0;transform:translateX(30px) scale(.96)}to{opacity:1;transform:none}}
@keyframes remOut{to{opacity:0;transform:translateX(30px) scale(.96)}}
.remn .rem-top2{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:2px 10px;align-items:center}
.remn .rem-ri{grid-row:1/3;width:38px;height:38px;border-radius:13px;display:grid;place-items:center;background:var(--accent);color:var(--accent-text)}
.remn .rem-ri .ic{width:19px;height:19px}
.remn .rem-lb{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--accent-hi)}
.remn b{font-size:15px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.remn .rem-x{grid-row:1/3;grid-column:3;width:30px;height:30px;border-radius:10px;display:grid;place-items:center;color:var(--muted)}.remn .rem-x:hover{background:rgba(255,255,255,.07);color:var(--text)}
.remn .rem-x .ic{width:16px;height:16px}
.remn p{margin:8px 0 0;font-size:13px;color:var(--text2);line-height:1.45;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.remn .rem-ac{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}.remn .rem-ac .btn{height:34px;padding:0 12px;font-size:12.5px}
@media (max-width:860px){
  .remp{left:12px;right:12px;width:auto;top:72px}
  .remnotes{top:calc(10px + env(safe-area-inset-top));right:10px;left:10px;width:auto}
  .rem-acts .btn{flex:1 1 calc(50% - 8px)}
}
'''

REM_JS = r'''
/* ================= Call reminders (11.16) =================
   Private to you (15th database update). The clock button in the top bar lists them; on the day, they pop up when you
   open the app; while the app is open you get a notification in the top right when one is due. */
const REM={list:null,at:0,missing:false,loading:null,popped:false,primed:false,
  seen:(()=>{try{return JSON.parse(localStorage.getItem("lf_rem_seen")||"{}")||{}}catch(e){return {}}})()};
const REM_MISSING="Reminders need the 15th database update. An admin opens RUN_IN_SUPABASE.sql, copies all of it into Supabase > SQL Editor and presses Run.";
async function remRpc(fn,args){let r;try{r=await api("sb_rpc",fn,args||{})}catch(e){r={ok:false,error:e.message}}r=r||{ok:false,error:"No answer."};if(r.missing)REM.missing=true;return r}
const remErr=r=>r&&r.missing?REM_MISSING:r&&r.offline?"You're offline. Try again when you're back online.":String((r&&r.error)||"Something went wrong.").replace(/^.*?ERROR:\s*/,"");
function loadRem(force){
  if(!S.me)return Promise.resolve(REM.list||[]);
  if(!force&&REM.at&&Date.now()-REM.at<60000)return Promise.resolve(REM.list||[]);
  if(REM.loading)return REM.loading;
  REM.loading=remRpc("rem_list").then(r=>{if(r.ok&&Array.isArray(r.data)){REM.list=r.data;REM.at=Date.now();REM.missing=false}else if(r.missing){REM.list=[];REM.at=Date.now()}
    paintRem();return REM.list||[]}).finally(()=>{REM.loading=null});
  return REM.loading;
}
const remOpen=()=>(REM.list||[]).filter(r=>!r.done_at);
const remDayEnd=()=>{const d=new Date();d.setHours(23,59,59,999);return d.getTime()};
const remToday=()=>remOpen().filter(r=>new Date(r.remind_at).getTime()<=remDayEnd()).sort((a,b)=>a.remind_at.localeCompare(b.remind_at));
const remOver=r=>!r.done_at&&new Date(r.remind_at).getTime()<=Date.now();
function remWhen(iso){const d=new Date(iso),t=d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"}),day=isoDay(d),td=isoDay(new Date()),tm=isoDay(new Date(Date.now()+864e5)),yd=isoDay(new Date(Date.now()-864e5));
  return (day===td?"Today":day===tm?"Tomorrow":day===yd?"Yesterday":d.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"}))+" · "+t}
function paintRem(){const n=remToday().length,c=$("#remCnt"),b=$("#remBtn");if(!c||!b)return;if(c.textContent!==String(n)){c.textContent=n;if(n)bump(c)}c.classList.toggle("on",n>0);
  b.classList.toggle("due",remOpen().some(remOver));b.setAttribute("aria-label",n?`Reminders: ${n} for today`:"Reminders");
  const p=$("#remPanel");if(p&&p.classList.contains("on"))remPanelDraw()}
const remRowHTML=r=>`<button type="button" class="remr${remOver(r)?" rem-od":""}${r.done_at?" done":""}" data-rem="${esc(r.id)}"><span class="rem-ri">${ic(r.done_at?"check":"clock")}</span><b>${esc(r.company)}</b>
   <small>${esc([r.owner_name,r.notes&&r.notes.split("\n")[0]].filter(Boolean).join(" · ")||r.phone||r.btype||"")}</small><span class="rem-tm">${esc(remWhen(r.remind_at))}</span></button>`;

/* ---------- the top-bar list ---------- */
function remPanelDraw(){
  const p=$("#remPanel");if(!p)return;
  if(REM.missing){p.innerHTML=`<div class="rem-hd"><h4>Reminders</h4></div><div class="note" style="padding:4px 6px 8px">${esc(REM_MISSING)}</div>`;return}
  const open=remOpen().sort((a,b)=>a.remind_at.localeCompare(b.remind_at)),od=open.filter(remOver),td=open.filter(r=>!remOver(r)&&new Date(r.remind_at).getTime()<=remDayEnd()),later=open.filter(r=>new Date(r.remind_at).getTime()>remDayEnd()),done=(REM.list||[]).filter(r=>r.done_at).slice(-10).reverse();
  p.innerHTML=`<div class="rem-hd"><h4>Reminders</h4><span class="muted" style="font-size:12px;font-weight:600">Only you can see these</span></div>
   ${open.length?`${od.length?`<div class="rem-sec rem-od">Due now</div>${od.map(remRowHTML).join("")}`:""}${td.length?`<div class="rem-sec">Later today</div>${td.map(remRowHTML).join("")}`:""}${later.length?`<div class="rem-sec">Coming up</div>${later.map(remRowHTML).join("")}`:""}`
    :`<div class="empty"><div class="bub">${ic("clock")}</div><b>No reminders</b>In Find Leads, press <b>Set reminder</b> on the business you're calling.</div>`}
   ${done.length?`<details><summary>Done (${done.length})</summary>${done.map(remRowHTML).join("")}</details>`:""}`;
  hydrateIcons(p);
  $$("[data-rem]",p).forEach(b=>b.onclick=()=>{const r=(REM.list||[]).find(x=>x.id===b.dataset.rem);p.classList.remove("on");r&&remDetail(r)});
}
function remToggle(){const p=$("#remPanel");$("#bell")&&$("#bell").classList.remove("on");const on=!p.classList.contains("on");if(on){remPanelDraw();loadRem(true)}p.classList.toggle("on",on)}
document.addEventListener("click",e=>{const p=$("#remPanel");if(p&&p.classList.contains("on")&&!e.target.closest("#remPanel")&&!e.target.closest("#remBtn"))p.classList.remove("on")});
document.addEventListener("keydown",e=>{if(e.key==="Escape"){const p=$("#remPanel");if(p)p.classList.remove("on")}});

/* ---------- set a reminder for a business ---------- */
function remDefault(){const d=new Date();d.setDate(d.getDate()+1);d.setHours(10,0,0,0);return d}
const remLocal=d=>isoDay(d)+"T"+String(d.getHours()).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0");
function remSet(l,existing){
  const r=existing||{id:null,lead_id:l.id||null,company:l.name||"",owner_name:l.owner&&l.owner!==NA?l.owner:"",phone:l.phone||"",address:l.address&&l.address!==NA?l.address:"",
    website:l.website&&l.website!==NA?l.website:"",btype:l.btype||"",notes:l.notes||"",remind_at:remDefault().toISOString()};
  const QUICK=[["1h","In 1 hour",()=>new Date(Date.now()+36e5)],["3h","In 3 hours",()=>new Date(Date.now()+3*36e5)],["tm","Tomorrow 9 am",()=>{const d=new Date();d.setDate(d.getDate()+1);d.setHours(9,0,0,0);return d}],
    ["3d","In 3 days",()=>{const d=new Date();d.setDate(d.getDate()+3);d.setHours(10,0,0,0);return d}],["1w","Next week",()=>{const d=new Date();d.setDate(d.getDate()+7);d.setHours(10,0,0,0);return d}]];
  openModal(`<div class="remd"><h2>${existing?"Edit reminder":"Set a reminder"}</h2><div class="muted" style="font-size:13.5px;margin-top:4px">It pops up when you open Leafline that day, and you get a notification when the time comes. Only you can see it.</div>
   <div class="rem-biz"><div class="av" style="background:${hue(r.btype)}">${esc(initials(r.company))}</div><div style="min-width:0"><b>${esc(r.company)}</b><small>${esc([r.btype,r.phone,r.address].filter(Boolean).join(" · "))}</small></div></div>
   <div class="fg" style="margin-bottom:6px"><div style="grid-column:1/3"><label class="l" for="rmAt">When</label><input class="inp" id="rmAt" type="datetime-local" value="${esc(remLocal(new Date(r.remind_at)))}" style="width:100%">
     <div class="rem-quick" role="group" aria-label="Quick times">${QUICK.map(([k,n])=>`<button type="button" class="chip" data-q="${k}">${n}</button>`).join("")}</div></div>
    <div style="grid-column:1/3"><label class="l" for="rmOwner">Owner / contact</label><input class="inp" id="rmOwner" maxlength="120" value="${esc(r.owner_name)}" placeholder="Who to ask for" style="width:100%"></div>
    <div style="grid-column:1/3"><label class="l" for="rmNotes">Call notes</label><textarea class="inp" id="rmNotes" rows="4" maxlength="4000" placeholder="What was said, what to bring up next time" style="width:100%">${esc(r.notes)}</textarea></div></div>
   <div id="rmErr" role="alert" style="color:#FF9AA0;font-size:13px;min-height:18px"></div>
   <div class="rem-acts"><span class="rem-sp"></span><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>${ic("clock")}${existing?"Save reminder":"Set reminder"}</button></div></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $$("[data-q]",ov).forEach(b=>b.onclick=()=>{const q=QUICK.find(x=>x[0]===b.dataset.q);$("#rmAt",ov).value=remLocal(q[2]());$$("[data-q]",ov).forEach(x=>x.classList.toggle("on",x===b))});
    $("#rmAt",ov).oninput=()=>$$("[data-q]",ov).forEach(x=>x.classList.remove("on"));
    $("[data-ok]",ov).onclick=async()=>{const e=$("#rmErr",ov),v=$("#rmAt",ov).value,b=$("[data-ok]",ov);e.textContent="";
      const at=new Date(v);if(!v||isNaN(at))return e.textContent="Pick a date and time.",$("#rmAt",ov).focus();
      b.disabled=true;b.textContent="Saving...";
      const res=await remRpc("rem_save",{p:{...r,owner_name:$("#rmOwner",ov).value.trim(),notes:$("#rmNotes",ov).value,remind_at:at.toISOString()}});
      b.disabled=false;b.innerHTML=ic("clock")+(existing?"Save reminder":"Set reminder");
      if(!res.ok)return e.textContent=remErr(res);
      delete REM.seen[res.data.id];remSeenSave();close();await loadRem(true);
      toast(`Reminder set for ${remWhen(res.data.remind_at)}`);logNote(`Reminder: ${r.company} (${remWhen(res.data.remind_at)})`);
      const btn=$("#remBtn");if(btn&&!REDUCE)btn.animate([{transform:"scale(1)"},{transform:"scale(1.18)"},{transform:"scale(1)"}],{duration:520,easing:EASE.spring||"ease"})};
    setTimeout(()=>$("#rmAt",ov).focus(),140)});
}
/* the lead the reminder is about, wherever it is now */
function remLead(r){return r.lead_id&&((S.find||[]).find(x=>x.id===r.lead_id)||(S.called||[]).find(x=>x.id===r.lead_id))}
function remGoto(r){
  const l=remLead(r);if(!l)return toast("That business isn't in your lists any more. Its details are saved in the reminder.");
  if((S.find||[]).some(x=>x.id===l.id)){S.q="";const g=$("#gq");if(g)g.value="";if(S.scope!=="all"&&!S.find.some(x=>x.id===l.id&&match(x))){S.scope="all";const sc=$("#scope");if(sc)sc.value="all"}
    go("find");S.active=l.id;S.sel.clear();lastDetail=null;renderFind();setTimeout(()=>{const li=$(`.li[data-id="${CSS.escape(l.id)}"]`);li&&li.scrollIntoView({block:"center"});openDetailSheet()},350)}
  else leadModal(l);
}
async function remDone(r,done=true){const res=await remRpc("rem_done",{p_id:r.id,p_done:done});if(!res.ok){toast(remErr(res),{bad:1});return false}
  await loadRem(true);toast(done?`Done: ${r.company}`:"Moved back to your reminders",done?{action:{label:"Undo",fn:()=>remDone(r,false)}}:{});return true}
async function remSnooze(r,ms){const at=new Date(Date.now()+ms);const res=await remRpc("rem_snooze",{p_id:r.id,p_at:at.toISOString()});if(!res.ok){toast(remErr(res),{bad:1});return false}
  delete REM.seen[r.id];remSeenSave();await loadRem(true);toast(`Snoozed until ${remWhen(at.toISOString())}`);return true}
function remDetail(r){
  const l=remLead(r),od=remOver(r);
  openModal(`<div class="remd"><div class="rem-rh"><div class="rem-ri">${ic("clock")}</div><div style="min-width:0"><h2>${esc(r.company)}</h2><div class="rem-when${od?" rem-od":""}">${r.done_at?"Done · ":od?"Due · ":""}${esc(remWhen(r.remind_at))}</div></div></div>
   <dl class="rem-kv">${r.owner_name?`<dt>Owner</dt><dd>${esc(r.owner_name)}</dd>`:""}${r.phone?`<dt>Phone</dt><dd>${telLink(r.phone)}</dd>`:""}${r.btype?`<dt>Type</dt><dd>${esc(r.btype)}</dd>`:""}
    ${r.address?`<dt>Address</dt><dd>${esc(r.address)}</dd>`:""}${r.website?`<dt>Website</dt><dd>${esc(r.website)}</dd>`:""}</dl>
   ${r.notes?`<div class="rem-nt"><h5>Call notes</h5>${esc(r.notes)}</div>`:""}
   <div class="rem-acts">${r.phone?callBtn(r.phone):""}${l?`<button class="btn" data-a="open">${ic("search")}Open business</button>`:""}<button class="btn" data-a="edit">${ic("edit")}Edit</button>
    ${r.done_at?`<button class="btn" data-a="undo">${ic("undo")}Not done</button>`:`<button class="btn" data-a="s1">${ic("clock")}In 1 hour</button><button class="btn" data-a="stm">${ic("cal")}Tomorrow</button>`}
    <button class="btn" data-a="del" style="color:#FF9AA0">${ic("trash")}Delete</button><span class="rem-sp"></span>${r.done_at?`<button class="btn pri" data-x>Close</button>`:`<button class="btn pri" data-a="done">${ic("check")}Done</button>`}</div></div>`,(ov,close)=>{
    const x=$("[data-x]",ov);if(x)x.onclick=close;
    const tm=()=>{const d=new Date();d.setDate(d.getDate()+1);d.setHours(9,0,0,0);return d.getTime()-Date.now()};
    $$("[data-a]",ov).forEach(b=>b.onclick=async()=>{const a=b.dataset.a;
      if(a==="open"){close();setTimeout(()=>remGoto(r),220)}
      else if(a==="edit"){close();setTimeout(()=>remSet(null,r),220)}
      else if(a==="done"){if(await remDone(r,true))close()}
      else if(a==="undo"){if(await remDone(r,false))close()}
      else if(a==="s1"){if(await remSnooze(r,36e5))close()}
      else if(a==="stm"){if(await remSnooze(r,tm()))close()}
      else if(a==="del"){if(!confirm(`Delete the reminder for ${r.company}?`))return;const res=await remRpc("rem_delete",{p_id:r.id});if(!res.ok)return toast(remErr(res),{bad:1});close();await loadRem(true);toast("Reminder deleted")}})});
}

/* ---------- on the day: a pop-up when you open the app ---------- */
async function maybeRemPopup(){
  if(REM.popped||!S.me)return;
  if(navigator.webdriver&&!/[?&]rem(&|$)/.test(location.search))return;      // automated test runs ask for it explicitly
  REM.popped=true;
  await loadRem(true);remPrime();
  /* wait for "What's new" and the meetings/payments pop-up (it may take a few seconds to appear), so they never stack */
  for(let i=0;i<240&&(i<6||document.querySelector(".ov.on")||(!S.dueShown&&i<20));i++)await new Promise(r=>setTimeout(r,500));
  if(document.querySelector(".ov.on"))return;
  const list=remToday();if(!list.length)return;
  openModal(`<div class="remd"><div class="rem-rh"><div class="rem-ri">${ic("clock")}</div><div><h2>Today's reminders</h2><div class="muted" style="font-size:13.5px;margin-top:2px">${list.length===1?"One business to get back to":list.length+" businesses to get back to"}. Open one to see your notes.</div></div></div>
   <div class="remlist">${list.map(remRowHTML).join("")}</div>
   <div class="rem-acts"><span class="rem-sp"></span><button class="btn pri" data-x>Got it</button></div></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;hydrateIcons(ov);
    $$("[data-rem]",ov).forEach(b=>b.onclick=()=>{const r=(REM.list||[]).find(x=>x.id===b.dataset.rem);close();setTimeout(()=>r&&remDetail(r),220)})});
}

/* ---------- when the time comes: a notification in the top right ---------- */
function remSeenSave(){try{const keep={};for(const r of REM.list||[])if(REM.seen[r.id])keep[r.id]=REM.seen[r.id];REM.seen=keep;localStorage.setItem("lf_rem_seen",JSON.stringify(keep))}catch(e){}}
/* reminders already due when the app opens are shown in the pop-up, not as a burst of notifications */
function remPrime(){if(REM.primed)return;REM.primed=true;for(const r of remOpen())if(remOver(r))REM.seen[r.id]=r.remind_at;remSeenSave()}
function remNotify(r){
  let box=$("#remNotes");if(!box){box=document.createElement("div");box.id="remNotes";box.className="remnotes";box.setAttribute("aria-live","assertive");document.body.appendChild(box)}
  if($(`.remn[data-id="${CSS.escape(r.id)}"]`,box))return;
  const el=document.createElement("div");el.className="remn";el.dataset.id=r.id;el.setAttribute("role","alert");
  el.innerHTML=`<div class="rem-top2"><span class="rem-ri">${ic("clock")}</span><span class="rem-lb">Reminder · ${esc(new Date(r.remind_at).toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"}))}</span><button class="rem-x" data-n="x" aria-label="Dismiss">${ic("x")}</button><b>${esc(r.company)}</b></div>
    ${r.owner_name||r.notes?`<p>${esc([r.owner_name?"Ask for "+r.owner_name:"",r.notes].filter(Boolean).join(" · "))}</p>`:""}
    <div class="rem-ac"><button class="btn pri" data-n="open">${ic("note")}Open</button>${r.phone?callBtn(r.phone):""}<button class="btn" data-n="done">${ic("check")}Done</button><button class="btn" data-n="snz">${ic("clock")}10 min</button></div>`;
  box.appendChild(el);hydrateIcons(el);
  const gone=()=>{el.classList.add("out");setTimeout(()=>el.remove(),260)};
  el.addEventListener("click",async e=>{const b=e.target.closest("[data-n]");if(!b)return;const a=b.dataset.n;
    if(a==="x")gone();else if(a==="open"){gone();remDetail(r)}else if(a==="done"){if(await remDone(r,true))gone()}else if(a==="snz"){if(await remSnooze(r,6e5))gone()}});
  if(document.hidden&&"Notification" in window&&Notification.permission==="granted"){try{const n=new Notification("Leafline reminder: "+r.company,{body:[r.owner_name?"Ask for "+r.owner_name:"",r.notes].filter(Boolean).join(" · ").slice(0,180),tag:"lf-rem-"+r.id});n.onclick=()=>{window.focus();remDetail(r);n.close()}}catch(e){}}
  logNote(`Reminder: ${r.company}`);
}
function remTick(){
  if(!S.me||!REM.list)return;if(!REM.primed)remPrime();
  let any=false;for(const r of remOpen()){if(remOver(r)&&REM.seen[r.id]!==r.remind_at){REM.seen[r.id]=r.remind_at;any=true;remNotify(r)}}
  if(any)remSeenSave();paintRem();
}
setInterval(remTick,15000);
setInterval(()=>{if(S.me&&!document.hidden)loadRem(true).then(remTick)},180000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&S.me)loadRem(false).then(remTick)});
(function remStart(){const t=setInterval(()=>{if(!S.me||!S.ready)return;clearInterval(t);loadRem(true).then(()=>{remTick();setTimeout(maybeRemPopup,3400)})},800)})();
'''


def inject(ui):
    """Adds call reminders to the shared page."""
    css_at, js_at = "</style>\n</head>", "</script>\n</body>"
    assert ui.count(css_at) == 1 and ui.count(js_at) == 1
    return ui.replace(css_at, REM_CSS + css_at, 1).replace(js_at, REM_JS + js_at, 1)
