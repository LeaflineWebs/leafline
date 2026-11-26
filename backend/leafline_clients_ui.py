"""Leafline clients (12.0): one page for every business you work for.

A client's SERVICES are its deals, its PAYMENTS are those deals' confirmed payments, and its INVOICES are the invoices
that point at those deals (or its lead). Nothing about money is copied: the client only says which deals are its own
(table client_deals), so a payment confirmed on Profits, the dashboard or here shows up everywhere at once.
The rules (who can see, add, archive, delete) live in the database: supabase/migrations/20261118000019_clients.sql."""

CLI_CSS = r'''
/* ================= Clients ================= */
@media (min-width:861px){#pg-clients{padding-bottom:40px}}
.cl-head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:4px}
.cl-head h3{font-size:20px;font-weight:800}.cl-head .muted{font-size:13px;margin-top:2px;max-width:620px;line-height:1.45}
.cl-head .acts{display:flex;gap:8px;flex-wrap:wrap}
.cl-bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:4px 0 12px}
.cl-bar .cl-q{flex:1 1 220px;min-width:0;height:40px;padding:0 14px 0 38px;border-radius:14px;background:rgba(0,0,0,.16) no-repeat 12px center;border:1px solid var(--line);color:var(--text)}
.cl-bar .cl-qw{position:relative;flex:1 1 240px;min-width:0;display:flex}.cl-bar .cl-qw .ic{position:absolute;left:12px;top:50%;transform:translateY(-50%);width:17px;height:17px;color:var(--muted);pointer-events:none}
.cl-bar select{height:40px;min-width:0}
.cl-list{display:flex;flex-direction:column;gap:6px}
.cl-row{display:grid;grid-template-columns:minmax(0,2.3fr) minmax(0,1.3fr) minmax(0,1.5fr) minmax(0,1fr) minmax(0,.9fr) minmax(0,.9fr) minmax(0,1fr) 84px;gap:12px;align-items:center;
  width:100%;text-align:left;padding:12px 14px;border-radius:18px;background:rgba(0,0,0,.14);border:1px solid var(--line);transition:background-color var(--d-hover,.15s) var(--e-out,ease),border-color var(--d-hover,.15s) var(--e-out,ease),transform var(--d-card,.3s) var(--e-spring,ease)}
.cl-row:hover{background:rgba(255,255,255,.045);border-color:var(--line2,var(--line))}
.cl-row.arch{opacity:.6}
.cl-row.hd{background:none;border:none;padding:0 14px 2px;font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted)}
.cl-row.hd:hover{background:none}
.cl-nm{display:flex;gap:12px;align-items:center;min-width:0}
.cl-av{width:40px;height:40px;border-radius:13px;display:grid;place-items:center;font-weight:800;color:#fff;flex:none;font-size:14px}
.cl-nm b{display:block;font-size:14.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cl-nm small{display:block;color:var(--muted);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cl-cell{min-width:0;font-size:13px;color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cl-cell b{color:var(--text);font-weight:700}.cl-cell .sub{display:block;font-size:11.5px;color:var(--muted);overflow:hidden;text-overflow:ellipsis}
.cl-num{font-variant-numeric:tabular-nums}
.cl-owe{color:#FF9AA0}.cl-ok{color:var(--accent-hi)}
.cl-tags{display:flex;gap:4px;flex-wrap:wrap;min-width:0}
.cl-st{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 8px;border-radius:11px;font-size:11.5px;font-weight:700;white-space:nowrap;background:rgba(255,255,255,.06);color:var(--text2);border:1px solid var(--line)}
.cl-st i{width:7px;height:7px;border-radius:50%;background:currentColor}
.cl-st.s-active{color:#5BE39A;background:rgba(91,227,154,.1);border-color:rgba(91,227,154,.3)}
.cl-st.s-pending{color:#EBC15C;background:rgba(235,193,92,.1);border-color:rgba(235,193,92,.3)}
.cl-st.s-inactive{color:var(--muted)}
.cl-st.s-completed{color:#8FC7F0;background:rgba(143,199,240,.1);border-color:rgba(143,199,240,.3)}
.cl-st.f-overdue{color:#FF9AA0;background:rgba(255,120,120,.12);border-color:rgba(255,120,120,.35)}
.cl-st.f-attn{color:#FFB070;background:rgba(255,176,112,.1);border-color:rgba(255,176,112,.32)}
.cl-st.f-high{color:#FFD60A;background:rgba(255,214,10,.08);border-color:rgba(255,214,10,.28)}
.cl-st.f-arch{color:var(--muted)}
.cl-tag{display:inline-flex;align-items:center;height:20px;padding:0 7px;border-radius:10px;font-size:11px;font-weight:700;background:var(--accent-soft);color:var(--accent-hi)}
.cl-team{display:flex;justify-content:flex-end}
.cl-team span{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:10.5px;font-weight:800;color:#fff;margin-left:-6px;border:2px solid var(--card,#111)}
.cl-empty{padding:40px 16px}
.stats.cl-sum{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:10px 0 14px}.cl-sum .stat .vl{font-size:26px}.cl-sum .stat{min-width:0}
.cl-sug{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:12px 14px;border-radius:16px;margin:0 0 12px;background:var(--accent-soft);border:1px solid var(--accent-line);font-size:13.5px}
/* profile */
.cp-top{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap;margin-bottom:12px}
.cp-back{height:38px;padding:0 12px 0 8px}
.cp-id{display:flex;gap:14px;align-items:center;min-width:0;flex:1 1 320px}
.cp-id .cl-av{width:56px;height:56px;border-radius:18px;font-size:19px}
.cp-id h2{font-size:22px;font-weight:800;overflow-wrap:anywhere}
.cp-id .sub{color:var(--muted);font-size:13.5px;margin-top:2px}
.cp-id .chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}
.cp-acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.cp-tabs{display:flex;gap:4px;padding:3px;border-radius:14px;background:rgba(0,0,0,.18);margin:4px 0 14px;width:max-content;max-width:100%;flex-wrap:wrap}
.cp-tabs button{height:36px;padding:0 16px;border-radius:11px;font-size:13.5px;font-weight:700;color:var(--muted);display:inline-flex;align-items:center;gap:7px}
.cp-tabs button.on{background:var(--card2);color:var(--text);box-shadow:0 2px 8px rgba(0,0,0,.25)}
.cp-tabs button b{min-width:19px;height:19px;padding:0 6px;border-radius:10px;background:rgba(255,255,255,.08);font-size:11px;display:grid;place-items:center}
.cp-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:14px;align-items:start}
.cp-grid>div{display:flex;flex-direction:column;gap:14px;min-width:0}
.cp-card{padding:16px 18px}
.cp-card h4{font-size:12px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:0 0 10px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.cp-kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:9px 16px;font-size:13.5px}
.cp-kv dt{color:var(--muted)}.cp-kv dd{margin:0;min-width:0;overflow-wrap:anywhere}
.cp-kv a{color:var(--accent-hi)}
.cp-money{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.cp-money>div{padding:12px;border-radius:14px;background:rgba(0,0,0,.16);border:1px solid var(--line);min-width:0}
.cp-money small{display:block;font-size:11.5px;font-weight:700;color:var(--muted)}
.cp-money b{display:block;font-size:20px;font-weight:800;margin-top:2px;font-variant-numeric:tabular-nums;overflow:hidden;text-overflow:ellipsis}
.cp-money span{display:block;font-size:11.5px;color:var(--text2);margin-top:1px}
.cp-team{display:flex;flex-direction:column;gap:8px}
.cp-team>div{display:flex;gap:10px;align-items:center;min-width:0}
.cp-team .cl-av{width:34px;height:34px;border-radius:50%;font-size:12px}
.cp-team b{display:block;font-size:13.5px}.cp-team small{display:block;font-size:12px;color:var(--muted)}
.cp-notes{white-space:pre-wrap;font-size:13.5px;line-height:1.5;color:var(--text2)}
.cp-rows{display:flex;flex-direction:column;gap:6px}
.cp-r{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 12px;align-items:center;padding:11px 12px;border-radius:14px;background:rgba(0,0,0,.14);border:1px solid var(--line)}
.cp-r b{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block}
.cp-r small{display:block;font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.cp-r .amt{font-weight:800;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.cp-r .ra{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;grid-column:1/-1}
.cp-r .ra:empty{display:none}
.cp-r.due{border-color:rgba(255,120,120,.35)}
.cp-sec{font-size:12px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:16px 4px 8px}
.cp-sec:first-child{margin-top:0}
.cp-tl{display:flex;flex-direction:column;gap:0;position:relative}
.cp-ev{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:2px 12px;padding:10px 4px;border-bottom:1px solid var(--line);align-items:start}
.cp-ev:last-child{border-bottom:none}
.cp-ev .ei{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-hi);grid-row:1/3}
.cp-ev .ei .ic{width:16px;height:16px}
.cp-ev.k-change .ei{background:rgba(255,255,255,.06);color:var(--muted)}
.cp-ev.k-pay .ei{background:rgba(91,227,154,.12);color:#5BE39A}
.cp-ev.k-inv .ei{background:rgba(143,199,240,.12);color:#8FC7F0}
.cp-ev p{margin:0;font-size:13.5px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}
.cp-ev small{font-size:12px;color:var(--muted)}
.cp-ev .x{color:var(--muted);width:28px;height:28px;border-radius:9px;display:grid;place-items:center}
.cp-comp{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:start;margin-bottom:12px}
.cp-comp textarea{min-height:42px;resize:vertical}
.cp-more{position:relative}
.cp-menu{position:absolute;right:0;top:calc(100% + 6px);z-index:30;min-width:200px;padding:6px;border-radius:16px;background:linear-gradient(180deg,color-mix(in srgb,var(--card2) 97%,transparent),color-mix(in srgb,var(--card) 97%,transparent));border:1px solid var(--line2,var(--line));box-shadow:var(--sh-lg,0 20px 40px rgba(0,0,0,.5));display:none}
.cp-menu.on{display:block}
.cp-menu button{width:100%;display:flex;gap:10px;align-items:center;padding:9px 10px;border-radius:11px;font-size:13.5px;font-weight:600;text-align:left}
.cp-menu button:hover{background:rgba(255,255,255,.06)}
.cp-menu button.bad{color:#FF9AA0}
/* editor */
.ce-team{display:flex;flex-direction:column;gap:6px;max-height:220px;overflow:auto;padding:2px}
.ce-team label{display:grid;grid-template-columns:auto auto minmax(0,1fr);gap:10px;align-items:center;font-size:13.5px}
.ce-team label .inp{height:34px;font-size:13px}
.ce-team label .cl-av{width:28px;height:28px;border-radius:50%;font-size:11px}
.cg-row{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;align-items:start;padding:10px 12px;border-radius:14px;background:rgba(0,0,0,.14);border:1px solid var(--line)}
.cg-row .inp{height:36px}
.cg-row small{display:block;color:var(--muted);font-size:12px;margin-top:4px}
.cg-list{display:flex;flex-direction:column;gap:8px;max-height:min(52vh,460px);overflow:auto;margin-top:12px}
/* dashboard + profits */
.cl-dash{padding:18px 20px;margin-top:16px}
.cl-dash .hd{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.cl-dash .nums{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 12px}
.cl-dash .nums>div{padding:10px 12px;border-radius:14px;background:rgba(0,0,0,.14);border:1px solid var(--line);min-width:0}
.cl-dash .nums small{display:block;font-size:11.5px;font-weight:700;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cl-dash .nums b{font-size:19px;font-weight:800;font-variant-numeric:tabular-nums}
.cl-dash .qa{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.cl-link{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 8px;margin-top:4px;border-radius:11px;font-size:11.5px;font-weight:700;background:var(--accent-soft);color:var(--accent-hi);border:1px solid var(--accent-line);max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cl-link .ic{width:12px;height:12px}
@media (max-width:1380px){.cl-row{grid-template-columns:minmax(0,2.2fr) minmax(0,1.3fr) minmax(0,1fr) minmax(0,.9fr) minmax(0,.9fr) minmax(0,1fr)}.cl-row>.c-svc,.cl-row>.c-team{display:none}}
@media (max-width:1100px){.cp-grid{grid-template-columns:minmax(0,1fr)}.cl-dash .nums{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:860px){
  .cl-row.hd{display:none}
  .cl-row{grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1fr);gap:8px 10px;padding:12px}
  .cl-row>.cl-nm{grid-column:1/-1}.cl-row>.c-st{grid-column:1/-1;white-space:normal}.cl-row>.c-next{grid-column:1/-1}
  .cl-row>.c-pay,.cl-row>.c-paid,.cl-row>.c-owe{padding:8px 10px;border-radius:12px;background:rgba(0,0,0,.14);white-space:normal}
  .cl-row .lbl{display:block;font-size:10.5px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:var(--muted)}
  .cl-bar select{flex:1 1 calc(50% - 8px)}
  .cl-sum{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .cp-acts{width:100%}.cp-acts .btn{flex:1 1 auto;justify-content:center}
  .cp-tabs{width:100%}.cp-tabs button{flex:1 1 auto;justify-content:center;padding:0 8px}
  .cp-comp{grid-template-columns:minmax(0,1fr) auto}.cp-comp select{grid-column:1/-1}
  .cp-money b{font-size:17px}
  .cl-dash .nums{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (min-width:861px){.cl-row .lbl{display:none}}
'''

CLI_JS = r'''
/* ================= Clients (12.0) ================= */
const CLI={list:null,admin:false,missing:false,err:"",at:0,loading:null,cur:null,tab:"over",full:null,
  f:(()=>{try{return Object.assign({q:"",st:"current",svc:"all",who:"all",pay:"all",tag:"all",sort:"name"},JSON.parse(localStorage.getItem("lf_cli_f")||"{}"),{q:""})}catch(e){return {q:"",st:"current",svc:"all",who:"all",pay:"all",tag:"all",sort:"name"}}})(),
  pend:null};
const CLI_MISSING="Clients need the 19th database update. An admin opens RUN_IN_SUPABASE.sql, copies all of it into Supabase > SQL Editor and presses Run. Nothing existing is changed.";
const CLI_ST={active:"Active",pending:"Pending",inactive:"Inactive",completed:"Completed"};
const CLI_PR={low:"Low",normal:"Normal",high:"High"};
async function cliRpc(fn,args){let r;try{r=await api("sb_rpc",fn,args||{})}catch(e){r={ok:false,error:e.message}}
  r=r||{ok:false,error:"No answer from the database."};if(r.missing)CLI.missing=true;return r}
const cliErr=r=>r&&r.missing?CLI_MISSING:r&&r.offline?"You're offline. Try again when you're back online.":String((r&&r.error)||"Something went wrong.").replace(/^.*?ERROR:\s*/,"");
function cliLoad(force){
  if(!S.me)return Promise.resolve(false);
  if(!force&&CLI.list&&Date.now()-CLI.at<30000)return Promise.resolve(true);
  if(CLI.loading)return CLI.loading;
  CLI.loading=cliRpc("cli_list").then(r=>{
    if(r.ok&&r.data){CLI.list=r.data.clients||[];CLI.admin=!!r.data.admin;CLI.missing=false;CLI.err="";CLI.at=Date.now()}
    else if(r.missing){CLI.list=[];CLI.at=Date.now()}else CLI.err=cliErr(r);
    return r.ok}).finally(()=>{CLI.loading=null});
  return CLI.loading;
}
const cliFind=id=>(CLI.list||[]).find(c=>c.id===id);
const cliToday=()=>isoDay(new Date());
const cliAdd=(ds,n)=>{const d=new Date(ds+"T12:00:00");d.setDate(d.getDate()+n);return isoDay(d)};
const cliDate=s=>{if(!s)return "";const d=new Date(String(s).slice(0,10)+"T12:00:00");if(isNaN(d))return String(s);return d.toLocaleDateString("en-US",d.getFullYear()===new Date().getFullYear()?{month:"short",day:"numeric"}:{month:"short",day:"numeric",year:"numeric"})};
const cliAgo=s=>{const m=(Date.now()-new Date(s).getTime())/6e4;return m<1?"just now":m<60?Math.round(m)+" min ago":m<1440?Math.round(m/60)+" h ago":m<2880?"yesterday":cliDate(s)};
const cliAv=(name,big)=>`<span class="cl-av" style="background:${hue(name||"")}">${esc(initials(name||"?"))}</span>`;
const cliPeople=()=>new Map(teamList());
function cliPersist(){try{localStorage.setItem("lf_cli_f",JSON.stringify({...CLI.f,q:""}))}catch(e){}}

/* ---------- money: always worked out from the deals (never stored twice) ---------- */
function cliDeals(c){const ids=new Set(c&&c.deal_ids||[]);return (S.deals||[]).filter(d=>d.rid&&ids.has(d.rid))}
function cliLinkedRids(){const m=new Map();(CLI.list||[]).forEach(c=>(c.deal_ids||[]).forEach(r=>m.set(r,c)));return m}
/* every payment of a deal up to a date, with whether someone confirmed it (before the 7th update, a past payment counts as paid) */
function cliSched(d,upto){
  const out=[],up=+d.upfront||0,mo=+d.monthly||0,n=+d.months||0,has="confirmed" in d,today=cliToday();
  const cs=new Set(Array.isArray(d.confirmed)?d.confirmed:String(d.confirmed||"").split(",")),paid=(ds,k)=>has?cs.has(ds+":"+k):ds<=today;
  if(d.closed_at&&up>0&&d.closed_at<=upto)out.push({date:d.closed_at,amt:up,kind:"upfront",paid:paid(d.closed_at,"upfront"),d});
  const f=d.first_bill||d.closed_at;
  if(f&&mo>0){const [y,m,dd]=f.split("-").map(Number);
    for(let k=0;n===0||k<n;k++){const t=y*12+(m-1)+k,yy=Math.floor(t/12),mm=t%12,dim=new Date(yy,mm+1,0).getDate();
      const ds=`${yy}-${String(mm+1).padStart(2,"0")}-${String(Math.min(dd,dim)).padStart(2,"0")}`;if(ds>upto)break;out.push({date:ds,amt:mo,kind:"monthly",paid:paid(ds,"monthly"),d})}}
  return out;
}
function cliDealState(d){
  const today=cliToday(),mo=+d.monthly||0,n=+d.months||0;
  if(mo>0&&n===0)return {k:"ongoing",t:"Ongoing monthly"};
  if(mo>0){const s=cliSched(d,"9999-12-31").filter(p=>p.kind==="monthly"),last=s.length?s[s.length-1].date:"";   /* n months: the schedule ends */if(last&&last>=today)return {k:"ongoing",t:`Monthly until ${cliDate(last)}`};return {k:"done",t:"Finished"}}
  if((+d.upfront||0)>0)return d.closed_at>today?{k:"soon",t:`Starts ${cliDate(d.closed_at)}`}:{k:"done",t:"One-time"};
  return {k:"done",t:"No payments"};
}
function cliPrice(d){const p=[];if(+d.upfront>0)p.push(usd(d.upfront)+" upfront");if(+d.monthly>0)p.push(usd(d.monthly)+"/month"+(+d.months?` × ${d.months}`:""));return p.join(" + ")||"No price set"}
function cliInvoices(c){
  if(!Array.isArray(INV.list))return [];const rids=new Set(c.deal_ids||[]),nm=[c.name,c.company].filter(Boolean).map(x=>x.trim().toLowerCase());
  return INV.list.filter(i=>(i.deal_id&&rids.has(i.deal_id))||(c.lead_id&&i.lead_id===c.lead_id)||(!i.deal_id&&nm.includes(String(i.client_name||"").trim().toLowerCase())));
}
function cliMoney(c){
  const today=cliToday(),late=cliAdd(today,-7),ds=cliDeals(c),all=[];
  ds.forEach(d=>all.push(...cliSched(d,cliAdd(today,120))));all.sort((a,b)=>a.date.localeCompare(b.date));
  const past=all.filter(p=>p.date<=today),due=past.filter(p=>!p.paid),fut=all.filter(p=>p.date>today);
  const paid=past.filter(p=>p.paid).reduce((a,p)=>a+p.amt,0),owe=due.reduce((a,p)=>a+p.amt,0),overdue=due.filter(p=>p.date<late);
  const monthly=ds.filter(d=>+d.monthly>0&&cliDealState(d).k==="ongoing").reduce((a,d)=>a+(+d.monthly||0),0);
  const upfront=ds.reduce((a,d)=>a+(+d.upfront||0),0);
  /* invoices that aren't for one of its deals (an invoice for a deal is the paperwork for that deal's payment, not extra money) */
  const inv=cliInvoices(c),loose=inv.filter(i=>!i.deal_id&&i.status==="sent"),invOwe=loose.reduce((a,i)=>a+Math.max(0,(+i.total||0)-(+i.paid_amount||0)),0),
    invLate=loose.filter(i=>i.due_date&&String(i.due_date).slice(0,10)<today);
  return {deals:ds,all,past,due,fut,paid,owe:owe+invOwe,dealOwe:owe,invOwe,overdue:overdue.length+invLate.length,overdueAmt:overdue.reduce((a,p)=>a+p.amt,0),monthly,upfront,
    freq:monthly>0?"Monthly":ds.length?"One-time":"",next:fut[0]||null,inv,invLate};
}
function cliFlags(c,m){
  const f=[],today=cliToday();
  if(m.overdue)f.push(["f-overdue","Payment overdue"]);
  const attn=!c.archived_at&&c.status!=="completed"&&(m.overdue||(c.next_date&&c.next_date<=cliAdd(today,2))||(c.status==="pending"&&c.created_at&&c.created_at.slice(0,10)<cliAdd(today,-14)));
  if(attn&&!m.overdue)f.push(["f-attn","Needs attention"]);
  if(c.priority==="high")f.push(["f-high","High priority"]);
  if(c.archived_at)f.push(["f-arch","Archived"]);
  return {list:f,attn:!!attn};
}
const cliStChip=c=>`<span class="cl-st s-${esc(c.status)}"><i></i>${esc(CLI_ST[c.status]||c.status)}</span>`;
const cliFlagChips=fl=>fl.list.map(([k,t])=>`<span class="cl-st ${k}">${esc(t)}</span>`).join("");

/* ---------- the list ---------- */
function cliMatches(c,m){
  const f=CLI.f,q=f.q.trim().toLowerCase();
  if(f.st==="current"&&c.archived_at)return false;
  if(f.st==="archived"&&!c.archived_at)return false;
  if(CLI_ST[f.st]&&(c.status!==f.st||c.archived_at))return false;
  if(f.svc==="monthly"&&!(m.monthly>0))return false;if(f.svc==="once"&&!(m.deals.length&&!m.monthly))return false;if(f.svc==="none"&&m.deals.length)return false;
  if(f.who==="me"&&!(c.team||[]).some(t=>t.id===(S.me&&S.me.id)))return false;
  if(f.who!=="all"&&f.who!=="me"&&f.who!=="none"&&!(c.team||[]).some(t=>t.id===f.who))return false;
  if(f.who==="none"&&(c.team||[]).length)return false;
  if(f.pay==="overdue"&&!m.overdue)return false;if(f.pay==="owing"&&!(m.owe>0))return false;if(f.pay==="clear"&&m.owe>0)return false;
  if(f.pay==="attn"&&!cliFlags(c,m).attn)return false;
  if(f.tag!=="all"&&!(c.tags||[]).includes(f.tag))return false;
  if(q){const hay=[c.name,c.company,c.contact,c.email,c.phone,c.address,c.notes,...(c.tags||[]),...m.deals.map(d=>d.client+" "+(d.notes||""))].join(" ").toLowerCase();if(!q.split(/\s+/).every(w=>hay.includes(w)))return false}
  return true;
}
function cliSort(rows){
  const s=CLI.f.sort,pr={high:0,normal:1,low:2};
  const by={name:(a,b)=>a.c.name.localeCompare(b.c.name),value:(a,b)=>b.m.monthly-a.m.monthly||b.m.paid-a.m.paid,paid:(a,b)=>b.m.paid-a.m.paid,owe:(a,b)=>b.m.owe-a.m.owe||b.m.overdue-a.m.overdue,
    next:(a,b)=>(a.nx||"9999").localeCompare(b.nx||"9999"),updated:(a,b)=>String(b.c.updated_at).localeCompare(String(a.c.updated_at)),priority:(a,b)=>pr[a.c.priority]-pr[b.c.priority]||a.c.name.localeCompare(b.c.name)}[s]||((a,b)=>0);
  return rows.sort((a,b)=>(!!a.c.archived_at-!!b.c.archived_at)||by(a,b));
}
const cliNext=(c,m)=>{const a=[];if(c.next_date)a.push([c.next_date,c.next_label||"Next date"]);if(m.next)a.push([m.next.date,`${usd(m.next.amt)} payment`]);a.sort((x,y)=>x[0].localeCompare(y[0]));return a[0]||null};
function cliRowHTML(c,m){
  const ppl=cliPeople(),fl=cliFlags(c,m),nx=cliNext(c,m),today=cliToday();
  return `<div role="listitem" tabindex="0" class="cl-row${c.archived_at?" arch":""}" data-cli="${esc(c.id)}" aria-label="${esc(c.name)}, open">
    <div class="cl-nm">${cliAv(c.name)}<div style="min-width:0"><b>${esc(c.name)}</b><small>${esc([c.company&&c.company!==c.name?c.company:"",c.contact].filter(Boolean).join(" · ")||c.email||c.phone||"No contact details yet")}</small></div></div>
    <div class="cl-cell c-st"><div class="cl-tags">${cliStChip(c)}${cliFlagChips(fl)}</div></div>
    <div class="cl-cell c-svc">${m.deals.length?`<b>${m.deals.length} service${m.deals.length===1?"":"s"}</b><span class="sub">${esc(m.deals.map(d=>d.client).join(", "))}</span>`:'<span class="muted">No services yet</span>'}</div>
    <div class="cl-cell c-pay cl-num"><span class="lbl">Pays</span>${m.monthly?`<b>${usd(m.monthly)}</b>/mo`:m.upfront?`<b>${usd(m.upfront)}</b><span class="sub">one-time</span>`:'<span class="muted">—</span>'}</div>
    <div class="cl-cell c-paid cl-num"><span class="lbl">Paid</span><b>${usd(m.paid)}</b></div>
    <div class="cl-cell c-owe cl-num"><span class="lbl">Owing</span>${m.owe>0?`<b class="cl-owe">${usd(m.owe)}</b>`:'<span class="cl-ok">Paid up</span>'}</div>
    <div class="cl-cell c-next"><span class="lbl">Next</span>${nx?`<b${nx[0]<today?' class="cl-owe"':""}>${esc(cliDate(nx[0]))}</b><span class="sub">${esc(nx[1])}</span>`:'<span class="muted">Nothing scheduled</span>'}</div>
    <div class="cl-team c-team">${(c.team||[]).slice(0,4).map(t=>{const n=ppl.get(t.id)||"?";return `<span style="background:${hue(n)}" title="${esc(n+(t.role?" · "+t.role:""))}">${esc(initials(n))}</span>`}).join("")}</div>
  </div>`;
}
function cliUnlinked(){const ln=cliLinkedRids();return (S.deals||[]).filter(d=>d.rid&&!ln.has(d.rid))}
async function renderClients(q){
  const pg=$("#pg-clients");if(!pg)return;
  if(CLI.cur)return cliProfile(CLI.cur,!!q&&!!pg.querySelector(".cp-top"));
  if(!CLI.list&&!pg.firstElementChild)pg.innerHTML=`<div class="card empty pop" style="margin-top:30px"><b>Loading your clients…</b></div>`;
  await Promise.all([cliLoad(!q),invLoad(false).catch(()=>{})]);
  if(S.page!=="clients"||CLI.cur)return;
  if(CLI.missing){pg.dataset.sig="";pg.innerHTML=`<div class="cl-head"><div><h3>Clients</h3></div></div><div class="card cl-empty empty pop"><div class="bub">${ic("briefcase")}</div><b>Not switched on yet</b><div>${esc(CLI_MISSING)}</div></div>`;hydrateIcons(pg);return}
  if(CLI.err&&!CLI.list){pg.innerHTML=`<div class="card cl-empty empty pop"><b>Couldn't load clients</b><div>${esc(CLI.err)}</div><button class="btn" id="clRetry">Try again</button></div>`;$("#clRetry",pg).onclick=()=>renderClients(false);return}
  const all=(CLI.list||[]).map(c=>{const m=cliMoney(c),nx=cliNext(c,m);return {c,m,nx:nx&&nx[0]}});
  const cur=all.filter(x=>!x.c.archived_at),act=cur.filter(x=>x.c.status==="active");
  const tot={n:act.length,pend:cur.filter(x=>x.c.status==="pending").length,mrr:cur.reduce((a,x)=>a+x.m.monthly,0),paid:all.reduce((a,x)=>a+x.m.paid,0),owe:cur.reduce((a,x)=>a+x.m.owe,0),od:cur.filter(x=>x.m.overdue).length,
    month:all.reduce((a,x)=>a+x.m.past.filter(p=>p.paid&&p.date.slice(0,7)===cliToday().slice(0,7)).reduce((s,p)=>s+p.amt,0),0)};
  const rows=cliSort(all.filter(x=>cliMatches(x.c,x.m)));
  const tags=[...new Set((CLI.list||[]).flatMap(c=>c.tags||[]))].sort((a,b)=>a.localeCompare(b)),ppl=teamList(),unl=cliUnlinked();
  const f=CLI.f,sig=JSON.stringify([CLI.list,S.deals,(INV.list||[]).map(i=>[i.id,i.status,i.paid_amount]),f,cliToday()]);
  if(q&&pg.dataset.sig===sig)return;pg.dataset.sig=sig;
  const hadFocus=document.activeElement&&document.activeElement.id==="clQ",selS=hadFocus?[document.activeElement.selectionStart,document.activeElement.selectionEnd]:null,top=pg.scrollTop;
  const opt=(v,t,cur)=>`<option value="${esc(v)}"${cur===v?" selected":""}>${esc(t)}</option>`;
  pg.innerHTML=`<div class="cl-head pop"><div><div class="muted">Everyone you work for. Services and payments come straight from your deals on Profits, so a payment confirmed anywhere shows up here.</div></div>
     <div class="acts">${unl.length?`<button class="btn" id="clGroup">${ic("users")}Set up from deals</button>`:""}<button class="btn pri" id="clAdd">${ic("plus")}Add client</button></div></div>
   <div class="stats cl-sum pop">
     <div class="stat"><div class="ico tone-g"><i class="ic">${svg("briefcase")}</i></div><div class="lb">Active clients</div><div class="vl">${num(tot.n)}</div><div class="dl">${tot.pend?`${num(tot.pend)} pending`:"&nbsp;"}</div></div>
     <div class="stat"><div class="ico tone-g"><i class="ic">${svg("repeat")}</i></div><div class="lb">Monthly recurring</div><div class="vl">${usd(tot.mrr)}</div><div class="dl">from active services</div></div>
     <div class="stat"><div class="ico tone-y"><i class="ic">${svg("dollar")}</i></div><div class="lb">Collected</div><div class="vl">${usd(tot.paid)}</div><div class="dl">${usd(tot.month)} this month</div></div>
     <div class="stat"><div class="ico tone-o"><i class="ic">${svg("bell")}</i></div><div class="lb">Outstanding</div><div class="vl${tot.owe>0?" cl-owe":""}">${usd(tot.owe)}</div><div class="dl">${tot.od?`${num(tot.od)} client${tot.od===1?"":"s"} overdue`:"Nothing overdue"}</div></div></div>
   ${unl.length&&!(CLI.list||[]).length?`<div class="cl-sug pop"><span>You have <b>${num(unl.length)}</b> deal${unl.length===1?"":"s"} on Profits. Turn them into clients in one step; nothing about the deals changes.</span><button class="btn pri sm" id="clGroup2">Set up clients</button></div>`:""}
   <div class="cl-bar pop" role="search">
     <div class="cl-qw">${ic("search")}<input class="cl-q" id="clQ" placeholder="Search clients, contacts, services, tags" value="${esc(f.q)}" aria-label="Search clients" autocomplete="off"></div>
     <select id="clSt" aria-label="Status">${opt("current","All current",f.st)}${opt("active","Active",f.st)}${opt("pending","Pending",f.st)}${opt("inactive","Inactive",f.st)}${opt("completed","Completed",f.st)}${opt("archived","Archived",f.st)}${opt("everything","Everything",f.st)}</select>
     <select id="clPay" aria-label="Payments">${opt("all","Any payments",f.pay)}${opt("overdue","Payment overdue",f.pay)}${opt("owing","Owes money",f.pay)}${opt("clear","Paid up",f.pay)}${opt("attn","Needs attention",f.pay)}</select>
     <select id="clSvc" aria-label="Services">${opt("all","Any service",f.svc)}${opt("monthly","Monthly services",f.svc)}${opt("once","One-time only",f.svc)}${opt("none","No services yet",f.svc)}</select>
     <select id="clWho" aria-label="Team">${opt("all","Whole team",f.who)}${opt("me","Mine",f.who)}${ppl.filter(p=>p[0]!==(S.me&&S.me.id)).map(p=>opt(p[0],p[1],f.who)).join("")}${opt("none","Nobody assigned",f.who)}</select>
     ${tags.length?`<select id="clTag" aria-label="Tag">${opt("all","Any tag",f.tag)}${tags.map(t=>opt(t,"#"+t,f.tag)).join("")}</select>`:""}
     <select id="clSort" aria-label="Sort">${opt("name","Name A–Z",f.sort)}${opt("value","Biggest monthly",f.sort)}${opt("owe","Most owing",f.sort)}${opt("paid","Most paid",f.sort)}${opt("next","Next date",f.sort)}${opt("priority","Priority",f.sort)}${opt("updated","Recently changed",f.sort)}</select></div>
   ${(CLI.list||[]).length?`<div class="cl-list pop" role="list">
       <div class="cl-row hd" aria-hidden="true"><div>Client</div><div>Status</div><div class="c-svc">Services</div><div>Pays</div><div>Paid</div><div>Owing</div><div>Next</div><div class="c-team" style="text-align:right">Team</div></div>
       ${rows.length?rows.map(x=>cliRowHTML(x.c,x.m)).join(""):`<div class="card empty cl-empty"><b>No clients match</b><div>Try another search or filter.</div><button class="btn" id="clClear">Clear filters</button></div>`}</div>`
     :`<div class="card empty cl-empty pop"><div class="bub">${ic("briefcase")}</div><b>No clients yet</b><div>Add the businesses you work for, then add their services. ${unl.length?"Or set them up from the deals you already have.":""}</div><button class="btn pri" id="clAdd2">${ic("plus")}Add your first client</button></div>`}`;
  hydrateIcons(pg);pg.scrollTop=top;
  const set=(k,v)=>{CLI.f[k]=v;cliPersist();renderClients(true)};
  const qi=$("#clQ",pg);let qt;qi.oninput=()=>{clearTimeout(qt);qt=setTimeout(()=>{CLI.f.q=qi.value;renderClients(true)},140)};
  if(hadFocus){qi.focus();try{qi.setSelectionRange(selS[0],selS[1])}catch(e){}}
  [["clSt","st"],["clPay","pay"],["clSvc","svc"],["clWho","who"],["clTag","tag"],["clSort","sort"]].forEach(([id,k])=>{const s=$("#"+id,pg);if(s)s.onchange=()=>set(k,s.value)});
  [$("#clAdd",pg),$("#clAdd2",pg)].forEach(b=>b&&(b.onclick=()=>cliEdit(null)));
  [$("#clGroup",pg),$("#clGroup2",pg)].forEach(b=>b&&(b.onclick=()=>cliGroupModal()));
  const cl=$("#clClear",pg);if(cl)cl.onclick=()=>{CLI.f={...CLI.f,q:"",st:"current",svc:"all",who:"all",pay:"all",tag:"all"};cliPersist();renderClients(true)};
  $$("[data-cli]",pg).forEach(b=>{b.onclick=()=>cliOpen(b.dataset.cli);b.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();cliOpen(b.dataset.cli)}}});
}
/* the sidebar's Clients always starts at the list; a client opened from elsewhere opens its profile */
{const _go=go;go=async function(p,force){
  const opening=CLI.opening;CLI.opening=false;
  if(p==="clients"&&!opening){if(S.page==="clients"&&CLI.cur&&!force){cliBack();return}CLI.cur=null}
  return _go.apply(this,arguments)}}
function cliOpen(id,tab){CLI.cur=id;CLI.tab=tab||"over";CLI.full=null;if(S.page!=="clients"){CLI.opening=true;go("clients")}else{const pg=$("#pg-clients");pg.dataset.sig="";pg.scrollTop=0;cliProfile(id,false)}}
function cliBack(){CLI.cur=null;CLI.full=null;const pg=$("#pg-clients");pg.dataset.sig="";pg.innerHTML="";renderClients(false)}

/* ---------- one client ---------- */
async function cliProfile(id,q){
  const pg=$("#pg-clients");if(!pg)return;
  const [r]=await Promise.all([cliRpc("cli_get",{p_id:id}),CLI.list?null:cliLoad(false),invLoad(false).catch(()=>{})]);
  if(S.page!=="clients"||CLI.cur!==id)return;
  if(!r.ok){CLI.cur=null;toast(cliErr(r),{bad:1});return renderClients(false)}
  const c=r.data;CLI.full=c;const i=(CLI.list||[]).findIndex(x=>x.id===c.id);if(i>=0)CLI.list[i]={...CLI.list[i],...c,timeline:undefined};
  const m=cliMoney(c),fl=cliFlags(c,m),ppl=cliPeople(),today=cliToday(),tab=CLI.tab;
  const sig=JSON.stringify([c,S.deals,(INV.list||[]).map(x=>[x.id,x.status,x.paid_amount]),tab,today]);if(q&&pg.dataset.sig===sig)return;pg.dataset.sig=sig;
  const tl=cliTimeline(c,m),top=q?pg.scrollTop:0,draft=$("#cpBody",pg)?$("#cpBody",pg).value:"";
  const tabs=[["over","Overview",""],["svc","Services",m.deals.length],["money","Money",m.due.length||""],["act","Activity",c.timeline.filter(e=>e.kind!=="change").length||""]];
  pg.innerHTML=`<div class="cp-top pop">
     <button class="btn cp-back" id="cpBack" aria-label="Back to all clients">${ic("back")}Clients</button>
     <div class="cp-id">${cliAv(c.name)}<div style="min-width:0"><h2>${esc(c.name)}</h2><div class="sub">${esc([c.company&&c.company!==c.name?c.company:"",c.contact].filter(Boolean).join(" · ")||"No contact person yet")}</div>
       <div class="chips">${cliStChip(c)}${cliFlagChips(fl)}${(c.tags||[]).map(t=>`<span class="cl-tag">#${esc(t)}</span>`).join("")}</div></div></div>
     <div class="cp-acts">${m.due.length?`<button class="btn pri" data-a="pay">${ic("check")}Record payment</button>`:""}
       ${c.phone?callBtn(c.phone):""}${c.email?`<button class="btn" data-a="mail">${ic("mail")}Email</button>`:""}
       <button class="btn${m.due.length?"":" pri"}" data-a="note">${ic("note")}Add note</button><button class="btn" data-a="edit">${ic("edit")}Edit</button>
       <div class="cp-more"><button class="btn" data-a="more" aria-label="More actions" aria-haspopup="true">${ic("dots")}</button><div class="cp-menu" role="menu">
         <button data-a="svc">${ic("plus")}Add a service</button><button data-a="inv">${ic("receipt")}New invoice</button><button data-a="rem">${ic("clock")}Set a reminder</button>
         ${c.lead_id&&((S.called||[]).some(l=>l.id===c.lead_id)||(S.find||[]).some(l=>l.id===c.lead_id))?`<button data-a="lead">${ic("phone")}Open the lead</button>`:""}
         ${c.archived_at?`<button data-a="unarch">${ic("undo")}Reactivate</button>`:`<button data-a="arch">${ic("download")}Archive</button>`}
         ${CLI.admin?`<button data-a="del" class="bad">${ic("trash")}Delete client</button>`:""}</div></div></div></div>
   <div class="cp-tabs pop" role="tablist">${tabs.map(([k,n,b])=>`<button role="tab" data-tab="${k}" class="${tab===k?"on":""}" aria-selected="${tab===k}">${n}${b!==""&&b!==0?`<b>${b}</b>`:""}</button>`).join("")}</div>
   <div class="cp-body pop">${tab==="svc"?cliSvcTab(c,m):tab==="money"?cliMoneyTab(c,m):tab==="act"?cliActTab(c,tl):cliOverTab(c,m,ppl,tl)}</div>`;
  hydrateIcons(pg);pg.scrollTop=top;
  const bd=$("#cpBody",pg);if(bd&&draft)bd.value=draft;
  $("#cpBack",pg).onclick=cliBack;
  $$("[data-tab]",pg).forEach(b=>b.onclick=()=>{CLI.tab=b.dataset.tab;pg.dataset.sig="";cliProfile(id,true)});
  const menu=$(".cp-menu",pg);
  $$("[data-a]",pg).forEach(b=>b.onclick=e=>{e.stopPropagation();cliAct(c,m,b.dataset.a,b,menu)});
  wirePay(pg);   /* the same as Profits: Confirm asks who gets credit (profit splits), Undo takes it back */
  $$("[data-dedit]",pg).forEach(b=>b.onclick=()=>{const d=(S.deals||[]).find(x=>String(x.id)===b.dataset.dedit);d&&dealModal(d)});
  $$("[data-dinv]",pg).forEach(b=>b.onclick=()=>{const d=(S.deals||[]).find(x=>String(x.id)===b.dataset.dinv);d&&cliInvoice(c,d)});
  $$("[data-doff]",pg).forEach(b=>b.onclick=async()=>{const d=(S.deals||[]).find(x=>x.rid===b.dataset.doff);if(!d||!confirm(`Take "${d.client}" off ${c.name}? The deal and its payments stay on Profits.`))return;
    b.disabled=true;const r=await cliRpc("cli_link",{p_client:c.id,p_deal:d.rid,p_on:false});if(!r.ok){b.disabled=false;return toast(cliErr(r),{bad:1})}toast("Service taken off");cliChanged(c.id)});
  $$("[data-inv]",pg).forEach(b=>b.onclick=()=>{CLI.back=c.id;invLoad(false).then(()=>{go("invoices");setTimeout(()=>invOpen(b.dataset.inv),260)})});
  $$("[data-evx]",pg).forEach(b=>b.onclick=async()=>{if(!confirm("Remove this entry?"))return;const r=await cliRpc("cli_note_delete",{p_id:b.dataset.evx});if(!r.ok)return toast(cliErr(r),{bad:1});toast("Removed");cliChanged(c.id)});
  const add=$("#cpAdd",pg);if(add)add.onclick=async()=>{const body=$("#cpBody",pg).value.trim(),kind=$("#cpKind",pg).value;if(!body)return $("#cpBody",pg).focus();
    add.disabled=true;const r=await cliRpc("cli_note",{p_client:c.id,p_kind:kind,p_body:body});add.disabled=false;if(!r.ok)return toast(cliErr(r),{bad:1});
    $("#cpBody",pg).value="";toast("Added to the timeline");logNote(`${c.name}: ${body.slice(0,60)}`);cliChanged(c.id)};
  const svcB=$("#cpSvc",pg);if(svcB)svcB.onclick=()=>cliAddService(c);
}
document.addEventListener("click",e=>{const mn=$("#pg-clients .cp-menu.on");if(mn&&!e.target.closest(".cp-more"))mn.classList.remove("on")});
function cliChanged(id){cliLoad(true).then(()=>{if(S.page==="clients"){const pg=$("#pg-clients");pg.dataset.sig="";if(CLI.cur===id)cliProfile(id,true);else renderClients(true)}})}
function cliAct(c,m,a,btn,menu){
  if(a==="more"){menu.classList.toggle("on");return}
  menu.classList.remove("on");
  const lead={id:c.lead_id||null,name:c.name,owner:c.contact||NA,phone:c.phone||"",address:c.address||NA,website:c.website||NA,btype:(c.tags||[])[0]||"",notes:"",email:c.email||NA};
  if(a==="edit")cliEdit(c);
  else if(a==="note"){CLI.tab="act";const pg=$("#pg-clients");pg.dataset.sig="";cliProfile(c.id,true).then(()=>{const t=$("#cpBody");t&&t.focus()})}
  else if(a==="pay"){CLI.tab="money";const pg=$("#pg-clients");pg.dataset.sig="";cliProfile(c.id,true)}
  else if(a==="mail")emailModal(lead,{to:c.email});
  else if(a==="rem")remSet(lead);
  else if(a==="inv")cliInvoice(c,null);
  else if(a==="svc")cliAddService(c);
  else if(a==="lead"){const l=(S.called||[]).find(x=>x.id===c.lead_id);if(l)leadModal(l);else{go("find");S.active=c.lead_id;setTimeout(()=>{lastDetail=null;renderFind()},300)}}
  else if(a==="arch"||a==="unarch")(async()=>{const r=await cliRpc("cli_archive",{p_id:c.id,p_on:a==="arch"});if(!r.ok)return toast(cliErr(r),{bad:1});
    toast(a==="arch"?`${c.name} archived. Its deals and payments are unchanged.`:`${c.name} is back`,a==="arch"?{action:{label:"Undo",fn:()=>cliAct(c,m,"unarch",btn,menu)}}:{});cliChanged(c.id)})();
  else if(a==="del")openModal(`<h2>Delete ${esc(c.name)}?</h2><p class="muted" style="margin:10px 0 0;line-height:1.55">The client, its timeline and tags are removed for everyone. <b>Its ${m.deals.length} deal${m.deals.length===1?"":"s"}, payments and invoices are kept</b> on Profits and Invoices; they just won't belong to a client any more. This can't be undone. To keep everything, archive the client instead.</p>
     <label style="display:flex;gap:8px;align-items:center;margin-top:14px;font-size:13.5px"><input type="checkbox" id="cdOk"> I understand, delete it</label>
     <div class="rem-acts"><span class="rem-sp"></span><button class="btn" data-x>Cancel</button><button class="btn" data-arch>${ic("download")}Archive instead</button><button class="btn pri" data-del disabled style="background:#c2484f">${ic("trash")}Delete</button></div>`,(ov,close)=>{
     $("[data-x]",ov).onclick=close;$("#cdOk",ov).onchange=e=>$("[data-del]",ov).disabled=!e.target.checked;
     $("[data-arch]",ov).onclick=()=>{close();cliAct(c,m,"arch",btn,menu)};
     $("[data-del]",ov).onclick=async()=>{const b=$("[data-del]",ov);b.disabled=true;const r=await cliRpc("cli_delete",{p_id:c.id});if(!r.ok){b.disabled=false;return toast(cliErr(r),{bad:1})}
       close();toast(`${c.name} deleted`);logNote(`Deleted client ${c.name}`);CLI.cur=null;cliLoad(true).then(()=>{const pg=$("#pg-clients");pg.dataset.sig="";renderClients(false)})}});
}
function cliInvoice(c,d){
  const items=[];if(d){if(+d.upfront>0)items.push({description:d.client+" (upfront)",details:d.notes||"",qty:1,unit_price:(+d.upfront).toFixed(2),taxable:true});
    if(+d.monthly>0)items.push({description:d.client+" (monthly)",details:d.months?`${d.months} months`:"Billed every month",qty:1,unit_price:(+d.monthly).toFixed(2),taxable:true})}
  invLoad(false).then(()=>invStart({client_name:c.company||c.name,client_contact:c.contact||"",client_email:c.email||"",client_phone:c.phone||"",client_address:c.address||"",
    lead_id:c.lead_id||null,deal_id:d&&d.rid||null,items:items.length?items:[invBlankItem()]}));
}
function cliOverTab(c,m,ppl,tl){
  const nx=cliNext(c,m);
  const kv=(k,v)=>v?`<dt>${k}</dt><dd>${v}</dd>`:"";
  return `<div class="cp-grid"><div>
    <div class="card cp-card"><h4>Contact</h4><dl class="cp-kv">${kv("Contact",esc(c.contact))}${kv("Phone",c.phone?telLink(c.phone):"")}${kv("Email",c.email?`<a href="mailto:${esc(c.email)}">${esc(c.email)}</a>`:"")}
      ${kv("Business",esc(c.company&&c.company!==c.name?c.company:""))}${kv("Address",esc(c.address))}${kv("Website",c.website?`<a href="${esc(/^https?:/i.test(c.website)?c.website:"https://"+c.website)}" target="_blank" rel="noopener">${esc(c.website.replace(/^https?:\/\//i,""))}</a>`:"")}</dl>
      ${!c.contact&&!c.phone&&!c.email?`<div class="muted" style="font-size:13px">No contact details yet. <button class="btn sm" data-a="edit">Add them</button></div>`:""}</div>
    <div class="card cp-card"><h4>Details</h4><dl class="cp-kv">${kv("Status",cliStChip(c))}${kv("Priority",esc(CLI_PR[c.priority]||c.priority))}${kv("Client since",esc(cliDate(c.start_date)))}
      ${kv("Next date",c.next_date?`<b${c.next_date<cliToday()?' class="cl-owe"':""}>${esc(cliDate(c.next_date))}</b>${c.next_label?" · "+esc(c.next_label):""}`:"")}${kv("Tags",(c.tags||[]).map(t=>`<span class="cl-tag">#${esc(t)}</span>`).join(" "))}${kv("Added by",esc(c.created_name||""))}</dl></div>
    ${c.notes?`<div class="card cp-card"><h4>Internal notes</h4><div class="cp-notes">${esc(c.notes)}</div></div>`:""}
   </div><div>
    <div class="card cp-card"><h4>Money <button class="btn sm" data-tab="money">Details</button></h4><div class="cp-money">
      <div><small>Pays</small><b>${m.monthly?usd(m.monthly)+"/mo":m.upfront?usd(m.upfront):"—"}</b><span>${esc(m.freq||"No services yet")}</span></div>
      <div><small>Paid so far</small><b>${usd(m.paid)}</b><span>${m.past.filter(p=>p.paid).length} payment${m.past.filter(p=>p.paid).length===1?"":"s"}</span></div>
      <div><small>Owing</small><b class="${m.owe>0?"cl-owe":"cl-ok"}">${m.owe>0?usd(m.owe):"Paid up"}</b><span>${m.overdue?`${m.overdue} overdue`:m.due.length?`${m.due.length} to confirm`:"Nothing due"}</span></div>
      <div><small>Next payment</small><b>${m.next?usd(m.next.amt):"—"}</b><span>${m.next?esc(cliDate(m.next.date)):"None scheduled"}</span></div></div></div>
    <div class="card cp-card"><h4>Team <button class="btn sm" data-a="edit">Change</button></h4>${(c.team||[]).length?`<div class="cp-team">${c.team.map(t=>{const n=ppl.get(t.id)||"Former teammate";return `<div>${cliAv(n)}<div style="min-width:0"><b>${esc(n)}</b><small>${esc(t.role||"No responsibility written")}</small></div></div>`}).join("")}</div>`:`<div class="muted" style="font-size:13px">Nobody assigned yet.</div>`}</div>
    <div class="card cp-card"><h4>Latest <button class="btn sm" data-tab="act">All activity</button></h4>${tl.length?`<div class="cp-tl">${tl.slice(0,4).map(cliEvHTML).join("")}</div>`:'<div class="muted" style="font-size:13px">Nothing yet.</div>'}</div>
   </div></div>`;
}
function cliSvcTab(c,m){
  const today=cliToday();
  return `<div class="card cp-card"><h4>Services <button class="btn sm pri" id="cpSvc">${ic("plus")}Add a service</button></h4>
    ${m.deals.length?`<div class="cp-rows">${m.deals.map(d=>{const s=cliSched(d,today),paid=s.filter(p=>p.paid).reduce((a,p)=>a+p.amt,0),owe=s.filter(p=>!p.paid).reduce((a,p)=>a+p.amt,0),stt=cliDealState(d);
      return `<div class="cp-r"><div style="min-width:0"><b>${esc(d.client)}</b><small>${esc(cliPrice(d))} · ${esc(stt.t)} · since ${esc(cliDate(d.closed_at))}${d.notes?" · "+esc(d.notes):""}</small></div>
        <div class="amt">${usd(paid)}<small>${owe>0?`<span class="cl-owe">${usd(owe)} owing</span>`:"paid so far"}</small></div>
        <div class="ra"><button class="btn sm" data-dedit="${esc(String(d.id))}">${ic("edit")}Edit price</button><button class="btn sm" data-dinv="${esc(String(d.id))}">${ic("receipt")}Invoice</button><button class="btn sm" data-doff="${esc(d.rid)}">${ic("x")}Take off</button></div></div>`}).join("")}</div>`
      :`<div class="empty" style="padding:22px 10px"><div class="bub">${ic("briefcase")}</div><b>No services yet</b><div>A service is a deal: what they pay upfront and every month. Add one, or attach a deal you already have on Profits.</div></div>`}</div>`;
}
function cliMoneyTab(c,m){
  const today=cliToday(),hist=m.past.filter(p=>p.paid).slice().reverse(),payBtn=p=>`<button class="btn sm${p.paid?"":" pri"}" data-pay="${esc(String(p.d.id))}|${p.date}|${p.kind}|${p.paid?0:1}">${p.paid?ic("undo")+"Undo":ic("check")+"Confirm received"}</button>`;
  const row=(p,btn)=>`<div class="cp-r${!p.paid&&p.date<=today?" due":""}"><div style="min-width:0"><b>${esc(p.d.client)}</b><small>${esc(cliDate(p.date))} · ${p.kind==="upfront"?"Upfront":"Monthly"}${!p.paid&&p.date<cliAdd(today,-7)?' · <span class="cl-owe">overdue</span>':""}</small></div><div class="amt">${usd(p.amt)}</div>${btn?`<div class="ra">${btn}</div>`:""}</div>`;
  const inv=m.inv.slice().sort((a,b)=>String(b.issue_date).localeCompare(String(a.issue_date)));
  return `<div class="cp-money" style="grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px">
      <div><small>Agreed price</small><b>${m.monthly?usd(m.monthly)+"/mo":m.upfront?usd(m.upfront):"—"}</b><span>${m.monthly&&m.upfront?usd(m.upfront)+" upfront too":esc(m.freq||"No services")}</span></div>
      <div><small>Total revenue</small><b>${usd(m.paid)}</b><span>confirmed payments</span></div>
      <div><small>Outstanding</small><b class="${m.owe>0?"cl-owe":"cl-ok"}">${usd(m.owe)}</b><span>${m.invOwe>0?`${usd(m.invOwe)} on invoices`:m.overdue?`${m.overdue} overdue`:"due and not confirmed"}</span></div>
      <div><small>Upcoming</small><b>${usd(m.fut.reduce((a,p)=>a+p.amt,0))}</b><span>next 4 months</span></div></div>
    <div class="card cp-card">
      <div class="cp-sec">Waiting for confirmation</div>${m.due.length?`<div class="cp-rows">${m.due.slice().reverse().map(p=>row(p,payBtn(p))).join("")}</div>`:'<div class="muted" style="font-size:13px;padding:0 4px">Every payment that was due has been confirmed.</div>'}
      <div class="cp-sec">Coming up</div>${m.fut.length?`<div class="cp-rows">${m.fut.slice(0,6).map(p=>row(p,"")).join("")}</div>`:'<div class="muted" style="font-size:13px;padding:0 4px">Nothing scheduled.</div>'}
      <div class="cp-sec">Payment history</div>${hist.length?`<div class="cp-rows">${hist.slice(0,24).map(p=>row(p,payBtn(p))).join("")}</div>${hist.length>24?`<div class="muted" style="font-size:12.5px;margin:8px 4px 0">${hist.length-24} older payment${hist.length-24===1?"":"s"} not shown.</div>`:""}`:'<div class="muted" style="font-size:13px;padding:0 4px">No payments confirmed yet.</div>'}
      <div class="cp-sec">Invoices</div>${INV.missing?'<div class="muted" style="font-size:13px;padding:0 4px">Invoices need the 14th database update.</div>':inv.length?`<div class="cp-rows">${inv.map(i=>`<div class="cp-r"><div style="min-width:0"><b>Invoice ${esc(i.number)}</b><small>${esc(invShort(i.issue_date))} · ${esc({draft:"Draft",sent:i.due_date&&String(i.due_date).slice(0,10)<today?"Overdue":"Sent",paid:"Paid",void:"Void"}[i.status]||i.status)}${i.deal_id?" · for a service":""}</small></div><div class="amt">${esc(invMoney(i.total,i.currency))}</div><div class="ra"><button class="btn sm" data-inv="${esc(i.id)}">Open</button></div></div>`).join("")}</div>`:'<div class="muted" style="font-size:13px;padding:0 4px">No invoices you can see for this client. <button class="btn sm" data-a="inv">New invoice</button></div>'}
    </div>`;
}
/* the timeline: notes and changes from the database, plus payments and invoices worked out from the deals */
function cliTimeline(c,m){
  const ev=(c.timeline||[]).map(e=>({...e,at:e.created_at}));
  m.past.filter(p=>p.paid).forEach(p=>ev.push({id:"p"+p.d.id+p.date+p.kind,kind:"pay",body:`Payment received: ${usd(p.amt)} for ${p.d.client} (${p.kind==="upfront"?"upfront":"monthly"})`,at:p.date+"T12:00:00",auto:1}));
  m.inv.forEach(i=>{ev.push({id:"i"+i.id,kind:"inv",body:`Invoice ${i.number} ${i.status==="paid"?"paid":i.status==="void"?"voided":i.status==="draft"?"drafted":"sent"}: ${invMoney(i.total,i.currency)}`,at:(i.paid_on&&i.status==="paid"?String(i.paid_on).slice(0,10)+"T12:00:00":i.updated_at||i.issue_date),auto:1})});
  return ev.sort((a,b)=>String(b.at).localeCompare(String(a.at)));
}
const CLI_EVI={note:"note",call:"phone",meeting:"cal",update:"bulb",change:"edit",pay:"dollar",inv:"receipt"};
const CLI_EVN={note:"Note",call:"Call",meeting:"Meeting",update:"Update",change:"Change",pay:"Payment",inv:"Invoice"};
function cliEvHTML(e){
  const mine=!e.auto&&e.kind!=="change"&&(e.created_by===(S.me&&S.me.id)||CLI.admin);
  return `<div class="cp-ev k-${esc(e.kind)}"><span class="ei">${ic(CLI_EVI[e.kind]||"note")}</span><p>${esc(e.body)}</p>${mine?`<button class="x" data-evx="${esc(e.id)}" aria-label="Remove">${ic("x")}</button>`:"<span></span>"}
    <small>${esc(CLI_EVN[e.kind]||"")} · ${esc(e.auto?cliDate(e.at):cliAgo(e.at))}${e.created_name?" · "+esc(e.created_name):""}</small></div>`;
}
function cliActTab(c,tl){
  return `<div class="card cp-card"><div class="cp-comp"><select class="inp" id="cpKind" aria-label="What kind of entry"><option value="note">Note</option><option value="call">Call</option><option value="meeting">Meeting</option><option value="update">Update</option></select>
     <textarea class="inp" id="cpBody" rows="2" maxlength="4000" placeholder="What happened? A conversation, a change, something the team should know" aria-label="Write an entry"></textarea><button class="btn pri" id="cpAdd">${ic("plus")}Add</button></div>
    ${tl.length?`<div class="cp-tl">${tl.map(cliEvHTML).join("")}</div>`:'<div class="muted" style="font-size:13px">Nothing yet.</div>'}</div>`;
}

/* ---------- add / edit ---------- */
function cliEdit(c,from){
  const isNew=!c;c=c||Object.assign({name:"",company:"",contact:"",phone:"",email:"",address:"",website:"",status:"active",priority:"normal",tags:[],team:S.me?[{id:S.me.id,role:""}]:[],notes:"",start_date:cliToday(),next_date:"",next_label:"",lead_id:null},from||{});
  const ppl=teamList(),onT=new Map((c.team||[]).map(t=>[t.id,t.role||""]));
  openModal(`<h2>${isNew?"Add a client":"Edit "+esc(c.name)}</h2><p class="muted" style="margin:6px 0 0;font-size:13px">Only the name is needed. Add services (what they pay) after saving.</p>
   <div class="fg">
    <div style="grid-column:1/3"><label class="l" for="ceName">Client name</label><input class="inp" id="ceName" maxlength="120" value="${esc(c.name)}" placeholder="e.g. Maple Roofing"></div>
    <div><label class="l" for="ceCo">Business / company</label><input class="inp" id="ceCo" maxlength="120" value="${esc(c.company)}" placeholder="If different"></div>
    <div><label class="l" for="ceCt">Contact person</label><input class="inp" id="ceCt" maxlength="120" value="${esc(c.contact)}" placeholder="Who you talk to"></div>
    <div><label class="l" for="cePh">Phone</label><input class="inp" id="cePh" maxlength="40" inputmode="tel" value="${esc(c.phone)}"></div>
    <div><label class="l" for="ceEm">Email</label><input class="inp" id="ceEm" maxlength="160" type="email" value="${esc(c.email)}"></div>
    <div style="grid-column:1/3"><label class="l" for="ceAd">Address</label><input class="inp" id="ceAd" maxlength="300" value="${esc(c.address)}"></div>
    <div><label class="l" for="ceWeb">Website</label><input class="inp" id="ceWeb" maxlength="300" value="${esc(c.website)}"></div>
    <div><label class="l" for="ceTags">Tags</label><input class="inp" id="ceTags" maxlength="300" value="${esc((c.tags||[]).join(", "))}" placeholder="e.g. Website, SEO, Roofing"></div>
    <div><label class="l" for="ceSt">Status</label><select class="inp" id="ceSt">${Object.entries(CLI_ST).map(([k,n])=>`<option value="${k}"${c.status===k?" selected":""}>${n}</option>`).join("")}</select></div>
    <div><label class="l" for="cePr">Priority</label><select class="inp" id="cePr">${Object.entries(CLI_PR).map(([k,n])=>`<option value="${k}"${c.priority===k?" selected":""}>${n}</option>`).join("")}</select></div>
    <div><label class="l" for="ceStart">Client since</label><input class="inp" id="ceStart" type="date" value="${esc(c.start_date||"")}"></div>
    <div><label class="l" for="ceNext">Next important date</label><input class="inp" id="ceNext" type="date" value="${esc(c.next_date||"")}"></div>
    <div style="grid-column:1/3"><label class="l" for="ceNextL">What's on that date</label><input class="inp" id="ceNextL" maxlength="80" value="${esc(c.next_label)}" placeholder="e.g. Monthly check-in, renewal, site launch"></div>
    <div style="grid-column:1/3"><div class="l">Team on this client <span class="muted">(and what each one does)</span></div><div class="ce-team">${ppl.map(([id,n])=>`<label><input type="checkbox" data-tm="${esc(id)}"${onT.has(id)?" checked":""}>${cliAv(n)}<span style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:8px;align-items:center;min-width:0"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(n)}</span><input class="inp" data-tr="${esc(id)}" maxlength="80" value="${esc(onT.get(id)||"")}" placeholder="Responsibility"></span></label>`).join("")}</div></div>
    <div style="grid-column:1/3"><label class="l" for="ceNotes">Internal notes</label><textarea class="inp" id="ceNotes" rows="3" maxlength="4000" placeholder="Only your team sees these">${esc(c.notes)}</textarea></div>
   </div><div id="ceErr" role="alert" style="color:#FF9AA0;font-size:13px;min-height:18px"></div>
   <div class="rem-acts"><span class="rem-sp"></span><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>${ic("check")}${isNew?"Add client":"Save"}</button></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $$("[data-tr]",ov).forEach(i=>i.oninput=()=>{const cb=$(`[data-tm="${CSS.escape(i.dataset.tr)}"]`,ov);if(i.value.trim()&&cb)cb.checked=true});
    $("[data-ok]",ov).onclick=async()=>{const e=$("#ceErr",ov),b=$("[data-ok]",ov),v=s=>$(s,ov).value.trim();e.textContent="";
      if(!v("#ceName")){e.textContent="Type the client's name.";return $("#ceName",ov).focus()}
      const em=v("#ceEm");if(em&&!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(em)){e.textContent="That email doesn't look right.";return $("#ceEm",ov).focus()}
      const p={id:c.id||null,name:v("#ceName"),company:v("#ceCo"),contact:v("#ceCt"),phone:v("#cePh"),email:em,address:v("#ceAd"),website:v("#ceWeb"),
        tags:v("#ceTags").split(",").map(t=>t.trim().replace(/^#/,"")).filter(Boolean).slice(0,12),status:$("#ceSt",ov).value,priority:$("#cePr",ov).value,
        start_date:v("#ceStart"),next_date:v("#ceNext"),next_label:v("#ceNextL"),notes:$("#ceNotes",ov).value,lead_id:c.lead_id||null,
        team:$$("[data-tm]",ov).filter(x=>x.checked).map(x=>({id:x.dataset.tm,role:($(`[data-tr="${CSS.escape(x.dataset.tm)}"]`,ov)||{value:""}).value.trim()}))};
      b.disabled=true;b.textContent="Saving…";const r=await cliRpc("cli_save",{p});b.disabled=false;b.innerHTML=ic("check")+(isNew?"Add client":"Save");
      if(!r.ok)return e.textContent=cliErr(r);
      close();toast(isNew?`${r.data.name} added`:"Saved");logNote(isNew?`New client: ${r.data.name}`:`Updated client: ${r.data.name}`);
      await cliLoad(true);
      if(isNew&&from&&from._deals&&from._deals.length){for(const rid of from._deals)await cliRpc("cli_link",{p_client:r.data.id,p_deal:rid,p_on:true});await cliLoad(true)}
      if(isNew)cliOpen(r.data.id,isNew&&!(from&&from._deals&&from._deals.length)?"svc":"over");else cliChanged(r.data.id)};
    setTimeout(()=>$("#ceName",ov).focus(),140)});
}
/* a client from a lead (Pipeline "Won", Called Leads) */
function cliFromLead(l){
  const ex=(CLI.list||[]).find(c=>c.lead_id===l.id||c.name.trim().toLowerCase()===String(l.name||"").trim().toLowerCase());
  if(ex)return cliOpen(ex.id);
  const known=v=>v&&v!==NA?v:"",rids=(S.deals||[]).filter(d=>d.rid&&!cliLinkedRids().has(d.rid)&&(d.lead_id===l.id||String(d.client||"").toLowerCase().includes(String(l.name||"").toLowerCase()))).map(d=>d.rid);
  cliEdit(null,{name:l.name||"",company:"",contact:known(l.owner),phone:l.phone||"",email:known(l.email),address:known(l.address),website:known(l.website),tags:l.btype?[l.btype]:[],lead_id:l.id,notes:l.notes||"",_deals:rids});
}
/* add a service: a new deal (added on Profits' form, then attached here once it's saved) or a deal you already have */
function cliAddService(c){
  const unl=cliUnlinked(),nm=c.name.toLowerCase(),score=d=>String(d.client).toLowerCase().includes(nm)||nm.includes(String(d.client).toLowerCase())?0:1;
  unl.sort((a,b)=>score(a)-score(b)||String(a.client).localeCompare(String(b.client)));
  openModal(`<h2>Add a service to ${esc(c.name)}</h2><p class="muted" style="margin:6px 0 0;font-size:13px;line-height:1.5">A service is a deal: what they pay upfront and each month. Payments are confirmed on the client's Money tab or on Profits.</p>
   <div class="rem-acts" style="margin-top:14px"><button class="btn pri" data-new>${ic("plus")}New service (new deal)</button></div>
   ${unl.length?`<div class="cp-sec" style="margin-top:18px">Or attach a deal you already have</div><div class="cg-list" style="margin-top:0">${unl.slice(0,40).map(d=>`<button type="button" class="cp-r" data-link="${esc(d.rid)}" style="text-align:left"><div style="min-width:0"><b>${esc(d.client)}</b><small>${esc(cliPrice(d))} · ${esc(cliDate(d.closed_at))}</small></div><div class="amt">${ic("plus")}</div></button>`).join("")}</div>`:""}
   ${(S.deals||[]).some(d=>!d.rid)?'<p class="muted" style="font-size:12.5px;margin-top:10px">Deals added in the last few seconds appear here once they have synced.</p>':""}
   <div class="rem-acts"><span class="rem-sp"></span><button class="btn" data-x>Close</button></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $("[data-new]",ov).onclick=()=>{close();CLI.pend={client:c.id,name:c.name,at:Date.now(),known:new Set((S.deals||[]).map(d=>String(d.id)))};setTimeout(()=>{dealModal({id:0,client:c.name,upfront:0,monthly:0,months:0,closed_at:cliToday(),first_bill:"",notes:""});
      const h=$(".ov.on .dlg h2");if(h)h.textContent="New service for "+c.name},260)};
    $$("[data-link]",ov).forEach(b=>b.onclick=async()=>{b.disabled=true;const r=await cliRpc("cli_link",{p_client:c.id,p_deal:b.dataset.link,p_on:true});if(!r.ok){b.disabled=false;return toast(cliErr(r),{bad:1})}
      close();toast("Service added");CLI.tab="svc";cliChanged(c.id)})});
}
/* a deal added with "New service" is attached to its client as soon as it has synced (has its shared id) */
async function cliPending(){
  const p=CLI.pend;if(!p)return;if(Date.now()-p.at>15*60000){CLI.pend=null;return}
  const d=(S.deals||[]).find(x=>!p.known.has(String(x.id)));if(!d)return;
  if(!d.rid)return;   // not uploaded yet: next reload
  CLI.pend=null;const r=await cliRpc("cli_link",{p_client:p.client,p_deal:d.rid,p_on:true});
  if(r.ok){toast(`Added to ${p.name}`);CLI.tab="svc";cliChanged(p.client)}else toast(cliErr(r),{bad:1});
}
/* set up clients from the deals you already have: one client per business name */
function cliGroupModal(){
  const unl=cliUnlinked(),key=s=>String(s||"").toLowerCase().replace(/\s*[-–—:|(].*$/,"").replace(/[^a-z0-9& ]/g,"").replace(/\s+/g," ").trim(),groups=new Map();
  unl.forEach(d=>{const k=key(d.client)||String(d.client).toLowerCase();if(!groups.has(k))groups.set(k,{name:String(d.client).replace(/\s*[-–—:|(].*$/,"").trim()||d.client,deals:[]});groups.get(k).deals.push(d)});
  const g=[...groups.values()].sort((a,b)=>a.name.localeCompare(b.name)),pending=(S.deals||[]).filter(d=>!d.rid).length;
  openModal(`<h2>Set up clients from your deals</h2><p class="muted" style="margin:6px 0 0;font-size:13px;line-height:1.5">Deals with the same business name become one client. Check the names, untick any you don't want, then press Create. <b>Nothing about the deals or their payments changes.</b></p>
   <div class="cg-list">${g.map((x,i)=>`<label class="cg-row"><input type="checkbox" data-g="${i}" checked><div style="min-width:0"><input class="inp" data-gn="${i}" maxlength="120" value="${esc(x.name)}" aria-label="Client name"><small>${x.deals.map(d=>esc(d.client)+" ("+esc(cliPrice(d))+")").join(" · ")}</small></div></label>`).join("")}</div>
   ${pending?`<p class="muted" style="font-size:12.5px;margin-top:10px">${pending} deal${pending===1?" is":"s are"} still syncing and will be listed here later.</p>`:""}
   <div id="cgErr" role="alert" style="color:#FF9AA0;font-size:13px;min-height:18px"></div>
   <div class="rem-acts"><span class="rem-sp"></span><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>${ic("check")}Create clients</button></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $("[data-ok]",ov).onclick=async()=>{const b=$("[data-ok]",ov),e=$("#cgErr",ov);b.disabled=true;let n=0;
      for(let i=0;i<g.length;i++){if(!$(`[data-g="${i}"]`,ov).checked)continue;const nm=$(`[data-gn="${i}"]`,ov).value.trim();if(!nm)continue;
        b.textContent=`Creating ${n+1}…`;const ex=(CLI.list||[]).find(c=>c.name.trim().toLowerCase()===nm.toLowerCase());
        const r=ex?{ok:true,data:ex}:await cliRpc("cli_save",{p:{name:nm,status:"active",team:S.me?[{id:S.me.id,role:""}]:[],start_date:g[i].deals.map(d=>d.closed_at).filter(Boolean).sort()[0]||cliToday()}});
        if(!r.ok){e.textContent=cliErr(r);b.disabled=false;b.innerHTML=ic("check")+"Create clients";return}
        for(const d of g[i].deals)await cliRpc("cli_link",{p_client:r.data.id,p_deal:d.rid,p_on:true});n++}
      close();toast(`${n} client${n===1?"":"s"} set up`);logNote(`Set up ${n} clients from deals`);await cliLoad(true);const pg=$("#pg-clients");if(pg){pg.dataset.sig="";renderClients(false)}};
  });
}

/* ---------- connections ---------- */
/* reload (after any sync / payment / deal change): keep the client page fresh and attach new services */
{const _reload=reload;reload=async function(){const r=await _reload.apply(this,arguments);try{await cliPending();if(S.page==="clients"&&!$(".ov.on")){const pg=$("#pg-clients");if(CLI.cur)cliProfile(CLI.cur,true);else renderClients(true)}}catch(e){}return r}}
/* Pipeline: moving a business to Won offers to make it a client */
{const _mv=plMove;plMove=async function(id,stage){const r=await _mv.apply(this,arguments);if(stage==="won"&&!CLI.missing){const l=(S.called||[]).find(x=>x.id===id);
  if(l){await cliLoad(false);const ex=(CLI.list||[]).find(c=>c.lead_id===l.id);toast(ex?`${l.name} is already a client`:`${l.name} won. Add them as a client?`,{ms:9000,action:{label:ex?"Open client":"Add client",fn:()=>ex?cliOpen(ex.id):cliFromLead(l)}})}}return r}}
/* Profits: each deal shows which client it belongs to */
{const _rp=renderProfits;renderProfits=function(){const r=_rp.apply(this,arguments);cliLoad(false).then(cliDecorateDeals);return r}}
function cliDecorateDeals(){
  if(S.page!=="profits"||CLI.missing)return;const ln=cliLinkedRids();
  $$("#pg-profits .dr[data-id]").forEach(row=>{const d=(S.deals||[]).find(x=>String(x.id)===row.dataset.id),c=d&&d.rid&&ln.get(d.rid),box=row.firstElementChild;if(!box)return;
    let ch=$(".cl-link",row);if(!c){ch&&ch.remove();return}
    if(!ch){ch=document.createElement("button");ch.type="button";ch.className="cl-link";box.appendChild(ch)}
    if(ch.dataset.c!==c.id){ch.dataset.c=c.id;ch.innerHTML=ic("briefcase")+esc(c.name);hydrateIcons(ch)}
    ch.onclick=e=>{e.stopPropagation();cliOpen(c.id,"money")}});
}
/* Invoices made from a deal now point at that deal (its shared id is "rid") */
if(typeof invFromDeal==="function"){const _ifd=invFromDeal;invFromDeal=function(d){return _ifd.call(this,d&&d.rid?{...d,uuid:d.rid}:d)}}
/* Dashboard: clients at a glance */
{const _rd=renderDash;renderDash=function(q){const r=_rd.apply(this,arguments);cliLoad(false).then(()=>cliDash());return r}}
function cliDash(){
  const pg=$("#pg-dash");if(!pg||S.page!=="dash"||CLI.missing||!CLI.list)return;
  const cur=CLI.list.filter(c=>!c.archived_at).map(c=>({c,m:cliMoney(c)})),act=cur.filter(x=>x.c.status==="active");
  const attn=cur.filter(x=>cliFlags(x.c,x.m).attn).sort((a,b)=>b.m.overdue-a.m.overdue||b.m.owe-a.m.owe).slice(0,4);
  const mrr=cur.reduce((a,x)=>a+x.m.monthly,0),owe=cur.reduce((a,x)=>a+x.m.owe,0),od=cur.filter(x=>x.m.overdue).length;
  const html=`<div class="card cl-dash pop" id="clDash"><div class="hd"><h3>Clients</h3><button class="btn sm" data-go="clients">All clients</button></div>
    ${CLI.list.length?`<div class="nums"><div><small>Active clients</small><b>${num(act.length)}</b></div><div><small>Monthly recurring</small><b>${usd(mrr)}</b></div><div><small>Outstanding</small><b class="${owe>0?"cl-owe":""}">${usd(owe)}</b></div><div><small>Overdue</small><b class="${od?"cl-owe":""}">${num(od)}</b></div></div>
    ${attn.length?`<div class="cp-sec">Needs attention</div><div class="cp-rows">${attn.map(x=>{const nx=cliNext(x.c,x.m);return `<button type="button" class="cp-r" data-dcl="${esc(x.c.id)}" style="text-align:left"><div style="min-width:0"><b>${esc(x.c.name)}</b><small>${x.m.overdue?`<span class="cl-owe">${usd(x.m.owe)} overdue</span>`:nx?esc(cliDate(nx[0])+" · "+nx[1]):"Pending for a while"}</small></div><div class="amt">${ic("next")}</div></button>`}).join("")}</div>`:'<div class="muted" style="font-size:13px">Nothing needs attention. Every client is paid up.</div>'}`
    :'<div class="muted" style="font-size:13px;margin-top:6px">Keep track of who you work for, what they pay and what they owe.</div>'}
    <div class="qa"><button class="btn pri sm" data-qa="add">${ic("plus")}Add client</button>${cur.some(x=>x.m.due.length)?`<button class="btn sm" data-qa="pay">${ic("check")}Record a payment</button>`:""}<button class="btn sm" data-qa="inv">${ic("receipt")}New invoice</button></div></div>`;
  let el=$("#clDash",pg);const tmp=document.createElement("div");tmp.innerHTML=html;const nu=tmp.firstElementChild;
  if(el){if(el.innerHTML===nu.innerHTML)return;el.replaceWith(nu)}else{const at=$(".stats",pg);if(!at)return;nu.classList.remove("pop");at.after(nu)}
  el=nu;hydrateIcons(el);
  $$("[data-go]",el).forEach(b=>b.onclick=()=>go(b.dataset.go));
  $$("[data-dcl]",el).forEach(b=>b.onclick=()=>cliOpen(b.dataset.dcl,"money"));
  $$("[data-qa]",el).forEach(b=>b.onclick=()=>{const a=b.dataset.qa;if(a==="add")cliEdit(null);else if(a==="inv")invLoad(false).then(()=>invStart(null));
    else{const x=cur.find(y=>y.m.due.length);if(x)cliOpen(x.c.id,"money")}});
}
/* keep the list fresh while it's open (other people add clients and notes too) */
setInterval(()=>{if(S.ready&&S.page==="clients"&&!document.hidden&&!$(".ov.on")&&!(document.activeElement&&document.activeElement.id==="cpBody"&&document.activeElement.value))cliLoad(true).then(()=>{if(CLI.cur)cliProfile(CLI.cur,true);else renderClients(true)})},60000);
'''


def inject(ui):
    """Adds Clients to the shared page."""
    css_at, js_at = "</style>\n</head>", "</script>\n</body>"
    assert ui.count(css_at) == 1 and ui.count(js_at) == 1
    return ui.replace(css_at, CLI_CSS + css_at, 1).replace(js_at, CLI_JS + js_at, 1)
