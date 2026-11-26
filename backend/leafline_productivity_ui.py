"""Productivity pack (11.19), added to the shared page like the other modules:
  * Automatic follow-ups: marking "No answer" sets a reminder for the next workday at a different time of day,
    "Voicemail" (Call Log) for 3 workdays later, and "Interested" opens the reminder pop-up with the notes.
  * Duplicate / do-not-call guard: warns before calling a business a teammate called in the last 14 days, or one
    that said "not interested" (17th update, lead_guard()).
  * Lead scoring: Find Leads can sort by "Best prospects" (no website, few reviews, good rating, owner known).
  * Saved searches: save a search, run it again in one click; each one is due again after 7 days.
  * Pipeline page: Called > Interested > Meeting > Proposal sent > Won > Lost, drag cards between columns, stale flags.
  * Health: each app reports its version and sync state; admins see that and which database updates have run.
"""

PROD_CSS = r'''
/* ================= productivity pack (11.19) ================= */
/* lead score */
.sc-pill{display:inline-flex;align-items:center;gap:4px;height:20px;padding:0 7px;border-radius:10px;font-size:11px;font-weight:800;flex:none;
  background:rgba(255,255,255,.06);color:var(--muted);border:1px solid var(--line)}
.sc-pill.hot{background:rgba(var(--accent-rgb),.16);color:var(--accent-hi);border-color:var(--accent-line)}
.sc-pill.warm{background:rgba(235,193,92,.13);color:#F3D27A;border-color:rgba(235,193,92,.35)}
.sc-why{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.sc-why span{font-size:12px;font-weight:600;color:var(--text2);background:rgba(255,255,255,.05);border-radius:8px;padding:3px 8px}
/* call guard */
.gd-ic{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;font-size:11px;font-weight:900;flex:none;background:rgba(235,193,92,.2);color:#F3D27A}
.gd-ic.dnc{background:rgba(240,138,138,.2);color:#F7A9A9}
.gd-ban{display:flex;gap:10px;align-items:flex-start;margin:12px 0 4px;padding:10px 12px;border-radius:14px;font-size:13px;line-height:1.45;
  background:rgba(235,193,92,.10);border:1px solid rgba(235,193,92,.32);color:var(--text)}
.gd-ban.dnc{background:rgba(240,138,138,.10);border-color:rgba(240,138,138,.38)}
.gd-ban b{display:block}.gd-ban .gd-ic{margin-top:1px}
/* saved searches */
.ss-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:10px}
.ss-chip{display:inline-flex;align-items:center;gap:0;height:32px;border-radius:16px;border:1px solid var(--line2);background:rgba(255,255,255,.04);overflow:hidden;max-width:100%}
.ss-chip>button{height:100%;padding:0 10px;font-size:12.5px;font-weight:700;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ss-chip>button:hover{color:var(--text);background:rgba(255,255,255,.05)}
.ss-chip .ss-x{padding:0 9px;color:var(--muted);border-left:1px solid var(--line)}
.ss-chip.due{border-color:rgba(235,193,92,.5)}.ss-chip.due .ss-run:after{content:"due";margin-left:6px;font-size:10.5px;font-weight:800;color:#F3D27A;text-transform:uppercase;letter-spacing:.3px}
.ss-chip small{font-weight:600;color:var(--muted);margin-left:6px}
@media (max-width:860px){.fcard:not(.open) .ss-bar{display:none}}   /* phones: folds away with the search form */
/* pipeline */
.pl-top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:4px 0 14px}
.pl-top .note{flex:1;min-width:220px}
/* sidebar: with every page listed, the list scrolls inside the sidebar on short screens so the footer stays visible */
.side .nav{flex:0 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;scrollbar-width:none;overscroll-behavior:contain}.side .nav::-webkit-scrollbar{display:none}
.side .foot{flex:none}
.pl-cols{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;overflow-x:auto;padding-bottom:10px;align-items:start}
.pl-col{border-radius:20px;padding:10px;background:rgba(0,0,0,.14);border:1px solid var(--line);min-height:160px;transition:border-color var(--d-hover) var(--e-out),background var(--d-hover) var(--e-out)}
.pl-col.over{border-color:var(--accent);background:var(--accent-soft)}
.pl-ch{display:flex;align-items:center;gap:8px;padding:4px 4px 10px;font-weight:800;font-size:13.5px}
.pl-ch i{width:9px;height:9px;border-radius:50%;flex:none}.pl-ch span{margin-left:auto;font-size:12px;color:var(--muted);font-weight:700}
.pl-list{display:grid;gap:8px}
.pl-card{position:relative;padding:11px 12px;border-radius:14px;background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);cursor:grab;
  box-shadow:0 4px 10px rgba(0,0,0,.18);transition:transform var(--d-card) var(--e-spring),border-color var(--d-hover) var(--e-out)}
.pl-card:hover{transform:translateY(-2px);border-color:var(--line2)}.pl-card.drag{opacity:.45}
.pl-card b{display:block;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:4px}
.pl-card .pl-sub{font-size:12px;color:var(--muted);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pl-meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px;font-size:11.5px;color:var(--text2);font-weight:600}
.pl-stale{color:#F3D27A;background:rgba(235,193,92,.13);border-radius:8px;padding:2px 7px;font-weight:800}
.pl-hand{color:var(--accent-hi);background:var(--accent-soft);border-radius:8px;padding:2px 7px;font-weight:800}
.pl-mv{margin-top:8px;width:100%;height:30px;font-size:12px;border-radius:10px}
.pl-empty{font-size:12.5px;color:var(--faint);text-align:center;padding:16px 6px}
.pl-col,.pl-card,.pl-list{min-width:0}.pl-card .pl-mv{width:100%;min-width:0}.pl-card b,.pl-sub{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block}
.pl-meta{flex-wrap:wrap}
.pl-jump{display:none}
@media (min-width:861px) and (max-width:1399px){.pl-cols{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:860px){.pl-cols{grid-template-columns:repeat(6,minmax(240px,82vw));scroll-snap-type:x mandatory}
.pl-jump{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;margin:0 0 10px;padding:0 0 2px;max-width:100%}.pl-jump::-webkit-scrollbar{display:none}
.pl-jump button{flex:0 0 auto;height:34px;padding:0 12px;border-radius:17px;border:1px solid var(--line);background:rgba(255,255,255,.04);font-size:12.5px;font-weight:700;display:inline-flex;align-items:center;gap:6px;color:var(--text2)}
.pl-jump button i{width:8px;height:8px;border-radius:50%}.pl-jump button.on{border-color:var(--accent-line);background:var(--accent-soft);color:var(--text)}.pl-col{scroll-snap-align:start}}
/* health */
.hl-ups{display:grid;grid-template-columns:repeat(auto-fill,minmax(84px,1fr));gap:8px;margin-top:12px}
.hl-up{display:flex;align-items:center;justify-content:center;gap:6px;height:36px;border-radius:12px;font-size:12.5px;font-weight:800;background:rgba(91,227,154,.10);color:var(--ok);border:1px solid rgba(91,227,154,.28)}
.hl-up.no{background:rgba(240,138,138,.10);color:var(--bad);border-color:rgba(240,138,138,.35)}.hl-up.unk{background:rgba(255,255,255,.05);color:var(--muted);border-color:var(--line)}
.hl-tbl{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}
.hl-tbl th{text-align:left;font-size:11.5px;color:var(--muted);font-weight:700;padding:6px 8px;border-bottom:1px solid var(--line)}
.hl-tbl td{padding:9px 8px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:top}
.hl-old{color:#F3D27A;font-weight:800}.hl-bad{color:var(--bad);font-weight:700}.hl-ok{color:var(--ok);font-weight:700}
.hl-wrap{overflow-x:auto}
'''

PROD_JS = r'''
/* ================= productivity pack (11.19) ================= */
const PPdays=n=>n===1?"1 day":n+" days";
const PPago=iso=>{if(!iso)return "";const t=new Date(String(iso).replace(" ","T")).getTime();if(!isFinite(t))return "";const d=Math.floor((Date.now()-t)/864e5);
  if(d<=0){const h=Math.floor((Date.now()-t)/36e5);return h<=0?"just now":h===1?"1 hour ago":h+" hours ago"}return d===1?"yesterday":d+" days ago"};
const PPkey=ph=>String(ph||"").replace(/\D/g,"").slice(-10);
const OUTC={no_answer:"No answer",voicemail:"Voicemail",interested:"Interested",not_interested:"Not interested",follow_up:"Follow up",meeting_booked:"Meeting booked",sale_completed:"Sale"};

/* ---------- lead score: how good a prospect a business looks, from what we already know ---------- */
function leadScore(l){
  const why=[];let s=0;const has=v=>v&&v!==NA;
  if(!has(l.website)){s+=40;why.push("No website")}
  const rv=parseInt(String(l.reviews).replace(/\D/g,""),10),rt=parseFloat(l.rating);
  if(!has(l.reviews)||!isFinite(rv)){s+=10;why.push("No Google reviews yet")}
  else if(rv<10){s+=25;why.push(`Very few reviews (${rv})`)}else if(rv<30){s+=15;why.push(`Few reviews (${rv})`)}else if(rv<100)s+=5;
  if(isFinite(rt)){if(rt>=4.5){s+=15;why.push(`Great rating (${rt}★)`)}else if(rt>=4){s+=10;why.push(`Good rating (${rt}★)`)}else if(rt<3.5){s+=5;why.push(`Low rating (${rt}★): could use help`)}}
  if(has(l.owner)){s+=10;why.push("Owner's name known")}
  if(has(l.email)){s+=5;why.push("Email known")}
  s=Math.min(100,s);return {s,lvl:s>=70?"hot":s>=45?"warm":"cool",why};
}
function scorePill(l){const c=leadScore(l);return `<span class="sc-pill ${c.lvl}" title="Prospect score ${c.s}/100${c.why.length?": "+c.why.join(", "):""}">${c.s}</span>`}
function scoreFactHTML(l){const c=leadScore(l);
  return `<div class="fact span"><div class="k">Prospect score</div><div class="v">${scorePill(l)}<span style="font-size:13px;font-weight:600;color:var(--text2)">${c.lvl==="hot"?"Strong prospect":c.lvl==="warm"?"Worth a call":"Lower priority"}</span></div>
    ${c.why.length?`<div class="sc-why">${c.why.map(w=>`<span>${esc(w)}</span>`).join("")}</div>`:""}</div>`}
function paintScore(n,l){const t=$(".lt",n);if(!t)return;let p=$(".sc-pill",t);const h=scorePill(l);if(!p){t.insertAdjacentHTML("beforeend",h);return}if(p.outerHTML!==h)p.outerHTML=h}
(function(){const sel=$("#sort");if(sel&&!sel.querySelector('option[value="score"]'))sel.insertAdjacentHTML("beforeend",'<option value="score">Best prospects</option>');})();

/* ---------- duplicate / do-not-call guard (17th update) ---------- */
const GUARD={by:{},key:{},at:{},missing:false,busy:false,ack:{}};
async function guardLoad(leads,force){
  if(GUARD.missing||!S.me||!leads||!leads.length)return;
  const now=Date.now(),want=leads.filter(l=>l&&l.id&&(force||!GUARD.at[l.id]||now-GUARD.at[l.id]>120000)).slice(0,300);
  if(!want.length||GUARD.busy)return;GUARD.busy=true;
  try{const r=await api("sb_rpc","lead_guard",{p_leads:want.map(l=>({id:l.id,key:PPkey(l.phone)}))});
    if(r&&r.missing){GUARD.missing=true;return}if(!r||!r.ok)return;
    want.forEach(l=>{GUARD.at[l.id]=now;delete GUARD.by[l.id];const k=PPkey(l.phone);if(k)delete GUARD.key[k]});
    (r.data||[]).forEach(g=>{GUARD.by[g.id]=g;const l=want.find(x=>x.id===g.id),k=l&&PPkey(l.phone);if(k)GUARD.key[k]=Object.assign({name:l.name},g)});
    guardPaint();
  }catch(e){}finally{GUARD.busy=false}
}
function guardText(g){if(!g)return null;
  if(g.dnc_at)return {dnc:true,title:"Said not interested",line:`${g.dnc_name?esc(g.dnc_name)+" was told":"They said"} "not interested" ${esc(PPago(g.dnc_at))}.`+(g.last_at?` ${esc(g.last_name||"A teammate")} also called ${esc(PPago(g.last_at))} (${esc(OUTC[g.last_outcome]||g.last_outcome)}).`:"")};
  return {dnc:false,title:"A teammate called recently",line:`${esc(g.last_name||"A teammate")} called ${esc(PPago(g.last_at))} (${esc(OUTC[g.last_outcome]||g.last_outcome)}).`};
}
function guardBanner(l){const t=guardText(l&&GUARD.by[l.id]);if(!t)return "";
  return `<div class="gd-ban${t.dnc?" dnc":""}" role="note"><span class="gd-ic${t.dnc?" dnc":""}" aria-hidden="true">!</span><div><b>${t.title}</b>${t.line} Check before calling again.</div></div>`}
function guardIcon(l){const t=guardText(l&&GUARD.by[l.id]);return t?`<span class="gd-ic${t.dnc?" dnc":""}" title="${esc(t.title)}" aria-label="${esc(t.title)}">!</span>`:""}
function paintGuardRow(n,l){const t=$(".lt",n);if(!t)return;let g=$(".gd-ic",t);const h=guardIcon(l);if(!h){g&&g.remove();return}if(!g){const b=$("b",t);b?b.insertAdjacentHTML("afterend",h):t.insertAdjacentHTML("afterbegin",h);return}if(g.outerHTML!==h)g.outerHTML=h}
function guardPaint(){
  $$("#list .li[data-id]").forEach(n=>{const l=S.find.find(x=>x.id===n.dataset.id);if(l)paintGuardRow(n,l)});
  const d=$("#detail"),l=d&&S.find.find(x=>x.id===d.dataset.id),slot=d&&$("#gdSlot",d);if(l&&slot){const h=guardBanner(l);if(slot.innerHTML!==h)slot.innerHTML=h}
  const ms=$(".ov.on #gdSlotM");if(ms&&ms.dataset.id){const lead=(S.called||[]).find(x=>x.id===ms.dataset.id)||S.find.find(x=>x.id===ms.dataset.id);if(lead)ms.innerHTML=guardBanner(lead)}
}
/* ask before calling a business that's flagged */
document.addEventListener("click",e=>{
  const a=e.target.closest&&e.target.closest("a.tel");if(!a||!S.me)return;const k=PPkey(a.dataset.ph||a.getAttribute("href"));const g=k&&GUARD.key[k];
  if(!g||(GUARD.ack[k]&&Date.now()-GUARD.ack[k]<600000))return;
  e.preventDefault();e.stopImmediatePropagation();const t=guardText(g);
  openModal(`<h2>${t.dnc?"They said not interested":"Called recently"}</h2><p class="muted" style="margin:10px 0 0;line-height:1.55"><b style="color:var(--text)">${esc(g.name||"This business")}</b>: ${t.line}</p>
    <div style="display:flex;gap:10px;margin-top:18px;justify-content:flex-end;flex-wrap:wrap"><button class="btn" data-x>Don't call</button><button class="btn pri" data-ok>${ic("phone")}Call anyway</button></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;$("[data-ok]",ov).onclick=()=>{GUARD.ack[k]=Date.now();close();setTimeout(()=>a.click(),60)}});
},true);
setInterval(()=>{if(!S.ready||document.hidden)return;if(S.page==="find")guardLoad(S.find.slice(0,300));else if(S.page==="called"||S.page==="pipeline")guardLoad((S.called||[]).slice(0,300))},120000);

/* ---------- automatic follow-ups ---------- */
const autoFollowOn=()=>getP("autoFollow",true)!==false;
function nextWorkday(from,days){const d=new Date(from);let n=days;while(n>0){d.setDate(d.getDate()+1);if(d.getDay()%6)n--}return d}
function followAt(days){const now=new Date(),d=nextWorkday(now,days);d.setHours(now.getHours()<12?14:10,0,0,0);return d}   // a different time of day than this call
async function autoFollow(kind,leads){
  if(!autoFollowOn()||!leads.length||typeof remSet!=="function")return;
  if(kind==="interested"){if(leads.length===1)setTimeout(()=>remSet(leads[0]),450);return}
  const days=kind==="voicemail"?3:1,at=followAt(days);
  try{await loadRem(true)}catch(e){}
  /* one open reminder per business is enough (matched by business, or by phone when it hasn't uploaded yet) */
  const openR=((typeof REM!=="undefined"&&REM.list)||[]).filter(r=>!r.done_at),open=new Set(openR.map(r=>r.lead_id).filter(Boolean)),openK=new Set(openR.map(r=>PPkey(r.phone)).filter(k=>k.length>=7));
  const todo=leads.filter(l=>!open.has(l.id)&&!openK.has(PPkey(l.phone))).slice(0,20);if(!todo.length)return;
  const made=[];
  for(const l of todo){const r=await api("sb_rpc","rem_save",{p:{lead_id:l.id,remind_at:at.toISOString(),company:l.name||"",owner_name:l.owner&&l.owner!==NA?l.owner:"",phone:l.phone||"",
      address:l.address&&l.address!==NA?l.address:"",website:l.website&&l.website!==NA?l.website:"",btype:l.btype||"",notes:l.notes||""}}).catch(()=>null);
    if(r&&r.missing)return;if(r&&r.ok&&r.data&&r.data.id)made.push(r.data.id)}
  if(!made.length)return;
  try{await loadRem(true)}catch(e){}
  const when=at.toLocaleDateString([],{weekday:"short",month:"short",day:"numeric"})+" at "+at.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"});
  setTimeout(()=>toast(`Follow-up set for ${when}${made.length>1?" ("+made.length+" businesses)":""}`,{action:{label:"Undo",fn:async()=>{for(const id of made)await api("sb_rpc","rem_delete",{p_id:id}).catch(()=>null);try{await loadRem(true)}catch(e){}toast("Follow-up removed")}}}),2600);
}
/* marking a result in Find Leads / Called Leads */
{const base=markLeads;markLeads=async function(status,fromBoard){
  const ids=fromBoard||(S.sel.size?[...S.sel]:S.active?[S.active]:[]);
  const before=ids.map(id=>S.find.find(x=>x.id===id)||(S.called||[]).find(x=>x.id===id)).filter(Boolean).map(l=>({...l}));
  const det=$("#detail"),o=$("#dOwner"),nt=$("#dNotes");if(det&&before.length===1&&det.dataset.id===before[0].id){if(o)before[0].owner=o.value.trim()||NA;if(nt)before[0].notes=nt.value}
  await base(status,fromBoard);
  autoFollow(status==="orange"?"no_answer":status==="yellow"?"interested":"",before).catch(()=>{});
}}

/* ---------- saved searches ---------- */
const SS_WEEK=7*864e5;
const ssList=()=>{const v=getP("savedSearches",[]);return Array.isArray(v)?v:[]};
const ssSave=v=>setP("savedSearches",v.slice(0,20));
const ssLabel=s=>[s.type,[s.city,s.state,s.country].filter(Boolean).join(", ")].filter(Boolean).join(" in ");
const ssDue=s=>!s.last||Date.now()-s.last>=SS_WEEK;
let SSrun=null;const SSq=[];
function ssPaint(){
  const box=$("#ssBar");if(!box)return;const L=ssList(),sig=JSON.stringify([L,L.map(ssDue)]);if(box.dataset.sig===sig)return;box.dataset.sig=sig;
  box.innerHTML=`<button class="btn sm" id="ssAdd" title="Save the area and business type above">${ic("plus")}Save this search</button>`+L.map(s=>`<span class="ss-chip${ssDue(s)?" due":""}">
    <button class="ss-run" data-ss="${esc(s.id)}" title="${esc(ssLabel(s))}${s.last?" · last run "+esc(PPago(new Date(s.last).toISOString()))+(s.lastNew!=null?" · "+s.lastNew+" new":""):" · not run yet"}">${esc(ssLabel(s))}${s.last&&s.lastNew!=null?`<small>${s.lastNew} new</small>`:""}</button>
    <button class="ss-x" data-ssdel="${esc(s.id)}" aria-label="Remove saved search ${esc(ssLabel(s))}">×</button></span>`).join("")+
    (L.some(ssDue)&&L.length>1?`<button class="btn sm" id="ssDueAll">Run ${L.filter(ssDue).length} due</button>`:"");
  hydrateIcons(box);
  $("#ssAdd",box).onclick=()=>{const v=id=>($("#"+id)||{}).value?.trim()||"",s={id:Math.random().toString(36).slice(2,10),country:v("fCountry"),state:v("fState"),city:v("fCity"),type:v("fType"),last:0,lastNew:null};
    if(!s.type||!(s.country||s.state||s.city))return toast("Fill in a business type and an area first.",{bad:1});
    const L2=ssList();if(L2.some(x=>ssLabel(x).toLowerCase()===ssLabel(s).toLowerCase()))return toast("That search is already saved.");
    if(L2.length>=20)return toast("You can keep up to 20 saved searches.",{bad:1});
    ssSave([...L2,s]);ssPaint();toast("Saved. Run it again any time; it's due again every 7 days.")};
  $$("[data-ss]",box).forEach(b=>b.onclick=()=>ssRun(b.dataset.ss));
  $$("[data-ssdel]",box).forEach(b=>b.onclick=()=>{ssSave(ssList().filter(x=>x.id!==b.dataset.ssdel));ssPaint()});
  const all=$("#ssDueAll",box);if(all)all.onclick=()=>{SSq.length=0;ssList().filter(ssDue).forEach(s=>SSq.push(s.id));ssNext()};
}
function ssRun(id){
  const s=ssList().find(x=>x.id===id);if(!s)return;if(S.running)return toast("A search is already running. Wait for it to finish.",{bad:1});
  const set=(k,v)=>{const e=$("#"+k);if(e)e.value=v||""};set("fCountry",s.country);set("fState",s.state);set("fCity",s.city);set("fType",s.type);
  SSrun=id;if(S.page!=="find")go("find");setTimeout(()=>startSearch(),S.page==="find"?0:500);
}
function ssNext(){const id=SSq.shift();if(id)ssRun(id)}
function ssDone(d){
  if(!SSrun)return;const id=SSrun;SSrun=null;
  if(!d||!d.stopped){const L=ssList().map(x=>x.id===id?{...x,last:Date.now(),lastNew:+d.n||0}:x);ssSave(L);ssPaint()}
  if(SSq.length&&!(d&&d.stopped))setTimeout(ssNext,1500);else SSq.length=0;
}
{const base=window.onPy;window.onPy=function(m){const r=base(m);try{if(m&&m.e==="search_done")ssDone(m.d||{});else if(m&&m.e==="search_error"&&SSrun){SSrun=null;SSq.length=0}}catch(e){}return r}}
(function(){const form=$("#pg-find .fcard .sline");if(form&&!$("#ssBar"))form.insertAdjacentHTML("beforebegin",'<div class="ss-bar" id="ssBar" aria-label="Saved searches"></div>')})();
let ssNudged=false;
setInterval(()=>{if(!S.ready||!S.me||ssNudged)return;ssPaint();const due=ssList().filter(ssDue).filter(s=>s.last);if(!due.length){ssNudged=true;return}
  if($(".ov.on"))return;ssNudged=true;
  toast(`${due.length} saved search${due.length===1?" is":"es are"} due for their weekly refresh`,{action:{label:"Run now",fn:()=>{SSq.length=0;due.forEach(s=>SSq.push(s.id));ssNext()}}})},6000);

/* ---------- Pipeline ---------- */
const PL=[["called","Called","#EE9A5A"],["interested","Interested","#EBC15C"],["meeting","Meeting","#5BE39A"],["proposal","Proposal sent","#8FC7F0"],["won","Won","#4ADE8B"],["lost","Lost","#F08A8A"]];
const PLauto={orange:"called",yellow:"interested",green:"meeting",red:"lost"};
const PLs={list:[],at:0,missing:false,busy:null,hold:0};
const plTime=v=>{if(!v)return 0;const t=new Date(String(v).replace(" ","T")).getTime();return isFinite(t)?t:0};
async function plLoad(force){
  if(PLs.hold)return;   // a move is being saved: don't let an older copy from the database put the card back
  if(PLs.busy)return PLs.busy;if(!force&&Date.now()-PLs.at<20000)return;
  PLs.busy=api("sb_rpc","lead_stage_list",{}).then(r=>{if(r&&r.missing){PLs.missing=true;PLs.list=[]}else if(r&&r.ok){PLs.missing=false;PLs.list=r.data||[]}PLs.at=Date.now()}).catch(()=>{}).finally(()=>{PLs.busy=null});
  return PLs.busy;
}
function plStage(l){
  const o=PLs.list.find(x=>x.lead_id===l.id),ct=plTime(l.called_at);
  if(o&&plTime(o.updated_at)>=ct-60000)return {st:o.stage,hand:true,at:Math.max(plTime(o.updated_at),ct)};
  const won=(S.deals||[]).some(d=>String(d.client||"").trim().toLowerCase()===String(l.name||"").trim().toLowerCase());
  return {st:won?"won":(PLauto[l.status]||"called"),hand:false,at:ct};
}
async function renderPipeline(q){
  const pg=$("#pg-pipeline");if(!pg)return;
  if(!pg.querySelector(".pl-cols"))pg.innerHTML=`<div class="card empty pop" style="margin-top:30px"><b>Loading the pipeline…</b></div>`;
  await plLoad(!q);if(S.page!=="pipeline")return;
  const me=S.me&&S.me.id,mine=getP("plMine",false),staleOnly=!!PLs.stale;
  const rows=(S.called||[]).filter(l=>l.status!=="none"&&(!mine||l.called_by===me)&&(typeof match!=="function"||match(l))).map(l=>{const s=plStage(l),age=s.at?Math.floor((Date.now()-s.at)/864e5):0;
      return {l,...s,age,stale:!["won","lost"].includes(s.st)&&age>=7}});
  const nStale=rows.filter(r=>r.stale).length,show=staleOnly?rows.filter(r=>r.stale):rows;
  const sig=JSON.stringify([show.map(r=>[r.l.id,r.st,r.hand,r.age,r.l.called_by]),mine,staleOnly,PLs.missing,Object.keys(GUARD.by).length]);
  if(q&&pg.dataset.sig===sig)return;pg.dataset.sig=sig;
  const card=r=>`<div class="pl-card" draggable="true" data-pl="${esc(r.l.id)}" tabindex="0" role="button" aria-label="${esc(r.l.name)}, ${esc((PL.find(x=>x[0]===r.st)||[])[1]||"")}">
      <b>${esc(r.l.name)}</b><div class="pl-sub">${esc(r.l.btype||"")}${r.l.phone?" · "+esc(r.l.phone):""}</div>
      <div class="pl-meta">${guardIcon(r.l)}<span>${esc(r.l.called_by?splitName(r.l.called_by).split(" ")[0]:"Unassigned")}</span><span>· ${r.age?PPdays(r.age)+" ago":"today"}</span>${r.stale?'<span class="pl-stale">Stale</span>':""}${r.hand?'<span class="pl-hand" title="Moved here by hand">Moved</span>':""}</div>
      <select class="inp pl-mv" data-mv="${esc(r.l.id)}" aria-label="Move ${esc(r.l.name)} to another stage"><option value="">Move to…</option>${PL.filter(x=>x[0]!==r.st).map(x=>`<option value="${x[0]}">${x[1]}</option>`).join("")}</select></div>`;
  pg.innerHTML=`<div class="pl-top pop"><div class="note">Every business you've called, by where it stands. Drag a card to move it (or use <b>Move to</b>). Cards with no change for 7 days are marked <b>Stale</b>.${PLs.missing?" <b>Moving cards by hand needs the 17th database update.</b>":""}</div>
     <div style="display:flex;gap:6px" role="group" aria-label="Whose businesses"><button class="chip${mine?"":" on"}" data-plm="0" aria-pressed="${!mine}">Everyone</button><button class="chip${mine?" on":""}" data-plm="1" aria-pressed="${mine}">Mine</button></div>
     <button class="chip${staleOnly?" on":""}" id="plStale">Stale only${nStale?` (${nStale})`:""}</button></div>
    <div class="pl-jump" role="group" aria-label="Go to a stage">${PL.map(([k,n,c])=>`<button type="button" data-plj="${k}"><i style="background:${c}"></i>${n} ${show.filter(r=>r.st===k).length}</button>`).join("")}</div>
    <div class="pl-cols">${PL.map(([k,n,c])=>{const list=show.filter(r=>r.st===k).sort((a,b)=>b.stale-a.stale||a.age-b.age);
      return `<div class="pl-col" data-col="${k}"><div class="pl-ch"><i style="background:${c}"></i>${n}<span>${list.length}</span></div><div class="pl-list">${list.length?list.map(card).join(""):'<div class="pl-empty">Nothing here</div>'}</div></div>`}).join("")}</div>`;
  hydrateIcons(pg);
  $$("[data-plm]",pg).forEach(b=>b.onclick=()=>{setP("plMine",b.dataset.plm==="1");renderPipeline(false)});
  $("#plStale",pg).onclick=()=>{PLs.stale=!PLs.stale;renderPipeline(false)};
  {const cols=$(".pl-cols",pg),jb=$$("[data-plj]",pg),mark=()=>{const x=cols.scrollLeft+8;let on=PL[0][0];$$(".pl-col",cols).forEach(c=>{if(c.offsetLeft-cols.offsetLeft<=x)on=c.dataset.col});jb.forEach(b=>b.classList.toggle("on",b.dataset.plj===on))};
   jb.forEach(b=>b.onclick=()=>{const c=$(`.pl-col[data-col="${b.dataset.plj}"]`,cols);if(c)cols.scrollTo({left:c.offsetLeft-cols.offsetLeft,behavior:REDUCE?"auto":"smooth"})});
   cols.addEventListener("scroll",()=>requestAnimationFrame(mark),{passive:true});mark()}
  $$(".pl-card",pg).forEach(c=>{
    c.onclick=e=>{if(e.target.closest(".pl-mv"))return;const l=(S.called||[]).find(x=>x.id===c.dataset.pl);l&&leadModal(l)};
    c.onkeydown=e=>{if(e.key==="Enter"&&!e.target.closest(".pl-mv"))c.click()};
    c.ondragstart=e=>{e.dataTransfer.setData("text/plain",c.dataset.pl);e.dataTransfer.effectAllowed="move";c.classList.add("drag")};
    c.ondragend=()=>c.classList.remove("drag")});
  $$(".pl-col",pg).forEach(col=>{col.ondragover=e=>{e.preventDefault();col.classList.add("over")};col.ondragleave=e=>{if(!col.contains(e.relatedTarget))col.classList.remove("over")};
    col.ondrop=e=>{e.preventDefault();col.classList.remove("over");const id=e.dataTransfer.getData("text/plain");if(id)plMove(id,col.dataset.col)}});
  $$("[data-mv]",pg).forEach(s=>s.onchange=()=>{if(s.value)plMove(s.dataset.mv,s.value)});
  guardLoad((S.called||[]).slice(0,300));
}
async function plMove(id,stage){
  const l=(S.called||[]).find(x=>x.id===id);if(!l)return;const cur=plStage(l);if(cur.st===stage)return;
  if(PLs.missing)return toast("Moving cards by hand needs the 17th database update. Ask an admin to run it (see SETUP_SUPABASE.md).",{bad:1,ms:7000});
  const auto=(()=>{const save=PLs.list;PLs.list=PLs.list.filter(x=>x.lead_id!==id);const a=plStage(l).st;PLs.list=save;return a})();
  const send=stage===auto?"":stage,prev=PLs.list.slice(),pg=$("#pg-pipeline");
  PLs.hold++;await PLs.busy;   // wait for any load already on its way, then keep the list as we set it
  PLs.list=PLs.list.filter(x=>x.lead_id!==id);if(send)PLs.list.push({lead_id:id,stage,updated_by:S.me&&S.me.id,updated_at:new Date().toISOString()});
  if(pg)pg.dataset.sig="";renderPipeline(true);
  const r=await api("sb_rpc","lead_stage_set",{p_lead:id,p_stage:send}).catch(e=>({ok:false,error:e.message}));
  PLs.hold--;
  if(!r||!r.ok){PLs.list=prev;if(pg)pg.dataset.sig="";renderPipeline(true);return toast((r&&r.missing)?"Moving cards by hand needs the 17th database update.":((r&&r.error)||"Couldn't move it."),{bad:1})}
  PLs.at=Date.now();
  const n=(PL.find(x=>x[0]===stage)||[])[1];toast(`${l.name} moved to ${n}`);logNote(`Pipeline: ${l.name} moved to ${n}`);
}
setInterval(()=>{if(S.ready&&S.page==="pipeline"&&!document.hidden&&!$(".ov.on")&&!$(".pl-card.drag"))renderPipeline(true)},60000);

/* ---------- health: each app reports its version + sync state; admins see everyone ---------- */
const HL={missing:false,last:0,sig:""};
async function reportStatus(force){
  if(HL.missing||!S.me||typeof UPS==="undefined")return;
  const s=S.sync||{},p={version:UPS.version||"",platform:UPS.platform||(window.LF_API?"web":"desktop"),sync_state:s.state||"",pending:+s.pending||0,last_error:String(s.error||"").slice(0,300)};
  const sig=JSON.stringify(p);if(!force&&sig===HL.sig&&Date.now()-HL.last<600000)return;if(!force&&Date.now()-HL.last<30000)return;
  HL.sig=sig;HL.last=Date.now();
  const r=await api("sb_rpc","me_status_report",{p}).catch(()=>null);if(r&&r.missing)HL.missing=true;
}
setInterval(()=>{if(S.ready&&!document.hidden)reportStatus(false)},120000);
const vcmp=(a,b)=>{const x=String(a||"0").split(".").map(Number),y=String(b||"0").split(".").map(Number);for(let i=0;i<3;i++){if((x[i]||0)!==(y[i]||0))return (x[i]||0)-(y[i]||0)}return 0};
async function healthCard(){
  const pg=$("#pg-admin");if(!pg||!isAdmin())return;let el=$("#hlCard",pg);
  if(!el){el=document.createElement("div");el.className="card form";el.id="hlCard";el.style.marginTop="16px";(pg.querySelector(".ad")||pg).appendChild(el)}
  el.innerHTML=`<h3>System health</h3><div class="note">Checking…</div>`;
  const r=await api("sb_rpc","team_health",{}).catch(e=>({ok:false,error:e.message}));if(S.page!=="admin")return;
  if(!r||!r.ok){el.innerHTML=`<h3>System health</h3><div class="note">${(r&&r.missing)?"This needs the 17th database update. Run <b>RUN_IN_SUPABASE.sql</b> in Supabase (see SETUP_SUPABASE.md).":esc((r&&r.error)||"Couldn't load it.")}</div>`;return}
  const d=r.data||{},U=d.updates||{},nums=Object.keys(U).map(Number).sort((a,b)=>a-b),miss=nums.filter(n=>U[n]===false);
  const latest=[UPS&&UPS.latest,UPS&&UPS.version,...(d.people||[]).map(p=>p.version)].filter(Boolean).reduce((a,b)=>vcmp(a,b)>=0?a:b,"0");
  const ppl=(d.people||[]).filter(p=>p.active);
  el.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><h3>System health</h3><button class="btn sm" id="hlRe">Refresh</button></div>
    <div class="note">${miss.length?`<span class="hl-bad">Database update${miss.length===1?"":"s"} ${miss.join(", ")} ${miss.length===1?"has":"have"} not been run.</span> Paste <b>RUN_IN_SUPABASE.sql</b> into Supabase &gt; SQL Editor and press Run (safe to run again).`:"Every database update has been run."}</div>
    <div class="hl-ups">${nums.map(n=>`<div class="hl-up${U[n]===false?" no":U[n]==null?" unk":""}" title="${U[n]==null?"Can't be checked from here (storage setting)":U[n]?"Installed":"Not run yet"}">#${n} ${U[n]===false?"✗":U[n]==null?"?":"✓"}</div>`).join("")}</div>
    <div class="hl-wrap"><table class="hl-tbl"><tr><th>Person</th><th>App</th><th>Sync</th><th>Last seen</th></tr>${ppl.map(p=>{const old=p.version&&vcmp(p.version,latest)<0;
      return `<tr><td><b>${esc(p.name||p.username)}</b><div class="muted" style="font-size:12px">${p.role==="admin"?"Admin":"Rep"}</div></td>
        <td>${p.version?`<span class="${old?"hl-old":""}">${esc(p.version)}</span> <span class="muted">${esc(p.platform==="web"?"website":p.platform||"")}</span>${old?`<div class="hl-old" style="font-size:12px">Behind (latest ${esc(latest)})</div>`:""}`:'<span class="muted">Not reported yet</span>'}</td>
        <td>${p.sync_state?`<span class="${p.sync_state==="synced"?"hl-ok":["error","attention"].includes(p.sync_state)?"hl-bad":""}">${esc({synced:"Synced",syncing:"Syncing",offline:"Offline",error:"Sync problem",attention:"Needs attention",signed_out:"Signed out"}[p.sync_state]||p.sync_state)}</span>${p.pending?` · ${num(p.pending)} waiting`:""}${p.last_error?`<div class="hl-bad" style="font-size:12px">${esc(p.last_error)}</div>`:""}${p.reported_at?`<div class="muted" style="font-size:12px">reported ${esc(PPago(p.reported_at))}</div>`:""}`:'<span class="muted">—</span>'}</td>
        <td>${p.last_seen?esc(PPago(p.last_seen)):'<span class="muted">Never</span>'}</td></tr>`}).join("")}</table></div>`;
  $("#hlRe",el).onclick=()=>healthCard();
}
{const base=renderAdmin;renderAdmin=async function(){await base.apply(this,arguments);if(S.page==="admin"&&isAdmin())healthCard()}}

/* ---------- Settings: automatic follow-ups switch ---------- */
function callingCardHTML(){return `<div class="card form pop" id="callCard"><h3>Calling</h3>
  <div class="lfg-row" style="margin-top:12px"><div><b>Automatic follow-ups</b><div class="note">Mark "No answer" and Leafline sets a reminder for the next workday at a different time of day. "Voicemail" in the Call Log sets one 3 workdays later. "Interested" opens the reminder so you can pick the time.</div></div><button type="button" class="tgl${autoFollowOn()?" on":""}" id="afTgl" role="switch" aria-checked="${autoFollowOn()}" aria-label="Automatic follow-ups"></button></div></div>`}
function wireCallingCard(root){const b=$("#afTgl",root);if(!b)return;b.onclick=()=>{const on=!autoFollowOn();setP("autoFollow",on);b.classList.toggle("on",on);b.setAttribute("aria-checked",on);toast(on?"Automatic follow-ups on":"Automatic follow-ups off")}}
'''


def inject(ui):
    """Adds the productivity pack to the shared page."""
    css_at, js_at = "</style>\n</head>", "</script>\n</body>"
    assert ui.count(css_at) == 1 and ui.count(js_at) == 1
    return ui.replace(css_at, PROD_CSS + css_at, 1).replace(js_at, PROD_JS + js_at, 1)
