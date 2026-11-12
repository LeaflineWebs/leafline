"""Leafline Invoices (11.15): the styles and page code for invoices, invoice templates, invoice settings, and the
PDF maker. They are added to the shared page (UI_HTML), so the desktop app and the website get the same Invoices page.
Every rule (who sees which invoice, who can mark one paid, who edits templates and settings) and every total is
enforced by the database (supabase/migrations/20261111000014_invoices_team.sql); this is only the interface.

The PDF is written directly (real text, lines and the vector Leafline logo, in the standard Helvetica font), not a
screenshot: text can be selected and copied, it prints sharp, and the e-Transfer email is a clickable mailto link."""

INV_CSS = r'''
/* ================= Invoices ================= */
.iv{max-width:1180px;margin:0 auto}
.iv .pg-head{flex-wrap:wrap}
.iv-acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.iv-warn{margin:14px 0 0;padding:12px 16px;border-radius:18px;background:rgba(233,193,90,.10);border:1px solid rgba(233,193,90,.28);color:#F1D58A;font-size:13px;line-height:1.5;display:flex;gap:10px;align-items:flex-start}
.iv-warn .ic{width:18px;height:18px;flex:none;margin-top:1px}
.iv-warn button{color:var(--accent-hi);font-weight:700;text-decoration:underline;text-underline-offset:2px}
.iv-list{padding:6px 0 8px;margin-top:4px}
.iv-bar{display:flex;flex-direction:column;gap:12px;padding:12px 18px 12px}
.iv-tabs{display:flex;gap:4px;padding:3px;border-radius:14px;background:rgba(0,0,0,.18);overflow-x:auto;scrollbar-width:none}
.iv-tabs::-webkit-scrollbar{display:none}
.iv-tabs button{flex:1 0 auto;height:34px;padding:0 14px;border-radius:11px;font-size:13px;font-weight:700;color:var(--muted);display:inline-flex;align-items:center;justify-content:center;gap:7px;white-space:nowrap;transition:background-color var(--d-hover) var(--e-out),color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.iv-tabs button:hover{color:var(--text)}.iv-tabs button:active{transform:scale(.95)}
.iv-tabs button.on{background:var(--card2);color:var(--text);box-shadow:0 2px 8px rgba(0,0,0,.25)}
.iv-tabs button b{min-width:19px;height:19px;padding:0 6px;border-radius:10px;background:rgba(255,255,255,.08);font-size:11px;display:grid;place-items:center}
.iv-tabs button.on b{background:var(--accent-soft);color:var(--accent-hi)}
.iv-tabs button.od b{background:rgba(255,120,120,.16);color:#FF9AA0}
.iv-f{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1.3fr) minmax(0,1fr) minmax(0,1fr) auto;gap:8px;align-items:center}
.iv-f .iv-srch{position:relative}.iv-f .iv-srch .ic{position:absolute;left:12px;top:11px;width:18px;height:18px;color:var(--muted);pointer-events:none}
.iv-f .iv-srch .inp{width:100%;padding-left:38px}
.iv-f select,.iv-f .inp{width:100%;min-width:0}
.iv-f .iv-clr{height:40px;padding:0 12px;border-radius:14px;color:var(--muted);font-weight:700;font-size:13px}.iv-f .iv-clr:hover{color:var(--text);background:rgba(255,255,255,.05)}
.iv-rows{padding:0 8px}
.iv-r{width:100%;display:grid;grid-template-columns:118px minmax(0,1fr) 108px 120px 110px 128px;gap:12px;align-items:center;padding:12px 12px;border-radius:16px;text-align:left;border-top:1px solid var(--line);transition:background-color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.iv-r:first-child{border-top:0}.iv-r:hover{background:rgba(255,255,255,.035)}.iv-r:active{transform:scale(.995)}
.iv-r.h{font-size:11.5px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:var(--faint,var(--muted));padding-top:4px;padding-bottom:6px;cursor:default}
.iv-r.h:hover{background:none}
.iv-r .iv-no{font-weight:800;font-size:13.5px;font-variant-numeric:tabular-nums}
.iv-r .iv-cl{min-width:0}.iv-r .iv-cl b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.iv-r .iv-cl small{display:block;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.iv-r .iv-dt{font-size:13px;font-weight:500;color:var(--text2)}
.iv-r .iv-amt{font-weight:800;text-align:right;font-variant-numeric:tabular-nums}
.iv-st{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border-radius:12px;font-size:12px;font-weight:800;white-space:nowrap}
.iv-st i{width:7px;height:7px;border-radius:50%;background:currentColor}
.iv-st.draft{background:rgba(163,187,172,.14);color:var(--text2)}
.iv-st.sent{background:rgba(127,182,255,.14);color:#A9CCFF}
.iv-st.overdue{background:rgba(255,120,120,.15);color:#FF9AA0}
.iv-st.paid{background:rgba(63,212,135,.16);color:#7DF0A8}
.iv-st.void{background:rgba(255,255,255,.06);color:var(--muted);text-decoration:line-through}
.iv-empty{padding:40px 20px}
@media (max-width:860px){
  .iv-f{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
  .iv-f .iv-srch{grid-column:1/3}
  .iv-f .iv-clr{grid-column:1/3}
  .iv-bar{padding:10px 12px}
  .iv-rows{padding:0 4px}
  .iv-r{grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;padding:12px 10px}
  .iv-r.h{display:none}
  .iv-r .iv-no{grid-column:1;font-size:12.5px;color:var(--muted)}
  .iv-r .iv-stc{grid-column:2;grid-row:1;justify-self:end}
  .iv-r .iv-cl{grid-column:1}.iv-r .iv-amt{grid-column:2;grid-row:2}
  .iv-r .iv-dt{grid-column:1/3;font-size:12px}
  .iv-r .iv-di{display:none}
}
/* editor + view */
.iv-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.iv-top h3{font-size:20px;font-weight:800;margin-right:auto;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.iv-back{width:40px;height:40px;border-radius:14px;display:grid;place-items:center;color:var(--text2);transition:background-color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.iv-back:hover{background:rgba(255,255,255,.06);color:var(--text)}.iv-back:active{transform:scale(.92)}.iv-back .ic{width:20px;height:20px}
.iv-grid{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:16px;align-items:start}
.iv-sec{padding:18px 20px;margin-bottom:16px}
.iv-sec>h4{font-size:12px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:0 0 12px;display:flex;align-items:center;gap:8px}
.iv-sec>h4 .ic{width:16px;height:16px}
.iv-sec .fg{margin:0}
.iv-side{position:sticky;top:6px}
.iv-cwrap{position:relative}
.iv-sug{position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:30;border-radius:16px;background:var(--card2);border:1px solid var(--line2,var(--line));box-shadow:var(--sh-lg,0 20px 40px rgba(0,0,0,.4));padding:6px;max-height:300px;overflow:auto;opacity:0;transform:translateY(-6px);pointer-events:none;transition:opacity var(--d-pop,.2s) var(--e-out,ease),transform var(--d-pop,.2s) var(--e-out,ease)}
.iv-sug.on{opacity:1;transform:none;pointer-events:auto}
.iv-sug button{width:100%;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;padding:9px 12px;border-radius:11px;text-align:left}
.iv-sug button:hover,.iv-sug button.on{background:var(--accent-soft)}
.iv-sug b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.iv-sug small{grid-column:1;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.iv-sug .src{grid-column:2;grid-row:1/3;align-self:center;font-size:11px;font-weight:800;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.iv-link{font-size:12.5px;color:var(--accent-hi);margin:8px 0 0 4px;display:flex;align-items:center;gap:6px}
.iv-link button{color:var(--muted);text-decoration:underline}
.iv-tpls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.iv-tpls .chip.on{background:var(--accent-soft);color:var(--accent-hi);border-color:var(--accent-line)}
.iv-items{display:flex;flex-direction:column;gap:10px}
.iv-it{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:12px;border-radius:18px;background:rgba(0,0,0,.14);border:1px solid var(--line);transition:border-color var(--d-hover) var(--e-out)}
.iv-it:focus-within{border-color:var(--accent-line)}
.iv-it .m{display:flex;flex-direction:column;gap:8px;min-width:0}
.iv-it .m .inp{width:100%}
.iv-it textarea.inp{min-height:40px;font-size:13px}
.iv-it .n{display:grid;grid-template-columns:80px 110px auto;gap:8px;align-items:start}
.iv-it .n label{display:flex;flex-direction:column;gap:4px;font-size:11.5px;font-weight:700;color:var(--muted)}
.iv-it .n label .inp{width:100%;text-align:right;font-variant-numeric:tabular-nums}
.iv-it .n .tx{flex-direction:row;align-items:center;gap:6px;height:40px;margin-top:19px;cursor:pointer;user-select:none}
.iv-it .n .tx input{width:17px;height:17px;accent-color:var(--accent)}
.iv-it .ft{grid-column:1/3;display:flex;align-items:center;gap:8px;justify-content:flex-end;font-size:13px;color:var(--muted)}
.iv-it .ft b{font-size:15px;color:var(--text);font-variant-numeric:tabular-nums;min-width:90px;text-align:right}
.iv-it .ft .rm{margin-right:auto;height:30px;padding:0 10px;border-radius:10px;color:var(--muted);display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12.5px}
.iv-it .ft .rm:hover{color:#FF9AA0;background:rgba(255,120,120,.08)}.iv-it .ft .rm .ic{width:15px;height:15px}
.iv-it.new{animation:ivIn var(--d-card,.4s) var(--e-spring,ease) both}
@keyframes ivIn{from{opacity:0;transform:translateY(-6px) scale(.98)}to{opacity:1;transform:none}}
.iv-add{margin-top:10px}
.iv-tot{display:flex;flex-direction:column;gap:2px}
.iv-tot .r{display:flex;justify-content:space-between;gap:10px;padding:7px 2px;font-size:14px;color:var(--text2)}
.iv-tot .r b{color:var(--text);font-variant-numeric:tabular-nums}
.iv-tot .r.t{border-top:1px solid var(--line);margin-top:6px;padding-top:12px;font-size:16px;font-weight:800;color:var(--text)}
.iv-tot .r.t b{font-size:22px;letter-spacing:-.3px}
.iv-tot .r.neg b{color:#FF9AA0}
.iv-dc{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px;margin:12px 0 4px}
.iv-dc .inp,.iv-dc select{width:100%}
.iv-save{display:flex;flex-direction:column;gap:8px;margin-top:14px}
.iv-save .btn{width:100%}
.iv-err{color:#FF9AA0;font-size:13px;min-height:18px;margin-top:6px}
.iv-txt textarea.inp{width:100%;min-height:90px}
.iv-txt label.l{margin-top:12px}.iv-txt label.l:first-child{margin-top:0}
/* view */
.iv-hero{padding:22px 24px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 20px;align-items:center;margin-bottom:16px}
.iv-hero .big{font-size:34px;font-weight:800;letter-spacing:-.6px;font-variant-numeric:tabular-nums;text-align:right}
.iv-hero .who b{font-size:18px}.iv-hero .who div{color:var(--muted);font-size:13px;margin-top:2px}
.iv-hero .iv-due{text-align:right;color:var(--muted);font-size:13px}
.iv-hero .iv-due.od{color:#FF9AA0;font-weight:700}
.iv-btns{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.iv-btns .btn{height:40px}
.iv-btns .btn.danger{color:#FF9AA0}
.iv-btns .btn .ic{width:17px;height:17px}
.iv-btns .btn.busy{pointer-events:none;opacity:.75}
.iv-btns .btn.busy .ic{animation:ivSpin .9s linear infinite}
@keyframes ivSpin{to{transform:rotate(360deg)}}
.iv-dl{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 16px;font-size:13.5px}
.iv-dl dt{color:var(--muted)}.iv-dl dd{margin:0;min-width:0;overflow-wrap:anywhere;white-space:pre-wrap}
.iv-tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.iv-tbl th{font-size:11.5px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:var(--muted);text-align:left;padding:0 8px 8px}
.iv-tbl td{padding:10px 8px;border-top:1px solid var(--line);vertical-align:top}
.iv-tbl .r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.iv-tbl small{display:block;color:var(--muted);font-size:12.5px;margin-top:3px;white-space:pre-wrap}
.iv-pay{border-radius:20px;padding:16px 18px;background:var(--accent-soft);border:1px solid var(--accent-line)}
.iv-pay h5{font-size:14px;font-weight:800;margin:0 0 10px;display:flex;align-items:center;gap:8px}
.iv-pay .em{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-weight:800;font-size:15px;margin:6px 0}
.iv-pay .em button{height:30px;padding:0 10px;border-radius:10px;background:rgba(0,0,0,.2);font-size:12.5px;font-weight:700;display:inline-flex;align-items:center;gap:6px}
.iv-pay .em button .ic{width:14px;height:14px}
.iv-pay p{margin:4px 0 0;font-size:13px;color:var(--text2);line-height:1.5}
.iv-long{white-space:pre-wrap;font-size:13px;line-height:1.55;color:var(--text2)}
.iv-sec details summary{cursor:pointer;font-weight:700;font-size:13.5px;color:var(--text2);list-style:none;display:flex;align-items:center;gap:8px}
.iv-sec details summary::-webkit-details-marker{display:none}
.iv-sec details summary .ic{width:16px;height:16px;transition:transform var(--d-hover) var(--e-out)}
.iv-sec details[open] summary .ic{transform:rotate(90deg)}
.iv-sec details .iv-long{margin-top:10px}
@media (max-width:1060px){.iv-grid{grid-template-columns:minmax(0,1fr)}.iv-side{position:static}}
@media (max-width:860px){
  .iv-sec{padding:16px 14px}
  .iv-it{grid-template-columns:minmax(0,1fr);padding:10px}
  .iv-it .n{grid-template-columns:minmax(0,1fr) minmax(0,1.3fr) auto}
  .iv-it .ft{grid-column:1}
  .iv-hero{grid-template-columns:minmax(0,1fr);padding:18px 16px}.iv-hero .big,.iv-hero .iv-due{text-align:left}.iv-hero .big{font-size:28px}
  .iv-btns .btn{flex:1 1 calc(50% - 8px)}
  .iv-tbl .hq{display:none}
  .iv-top h3{font-size:18px}
}
/* templates + settings dialogs */
.iv-tl{display:flex;flex-direction:column;gap:6px;margin:14px 0}
.iv-tl .t{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;align-items:center;padding:12px 14px;border-radius:16px;background:rgba(0,0,0,.14);border:1px solid var(--line)}
.iv-tl .t b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.iv-tl .t small{color:var(--muted);font-size:12px}
.iv-tl .t .a{grid-row:1/3;grid-column:2;display:flex;gap:6px}
.iv-tl .t.arch{opacity:.6}
.dlg .iv-items .iv-it .n{grid-template-columns:70px 100px auto}
.iv-set h5{font-size:12px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:18px 0 0}
.iv-set .fg{margin:10px 0}
'''

INV_JS = r'''
/* ================= Invoices (11.15) =================
   Every rule and every total lives in the database (14th update). This page shows them, collects what you type, and
   makes the PDF. Admins see every invoice; everyone else sees the invoices they made. */
const INV={list:null,today:"",admin:false,settings:null,tpls:null,missing:false,err:"",at:0,loading:null,view:"list",cur:null,E:null,dirty:false,
  f:{tab:"all",q:"",client:"",from:"",to:""}};
const INV_MISSING="Invoices need the 14th database update. An admin opens RUN_IN_SUPABASE.sql, copies all of it into Supabase > SQL Editor and presses Run.";
const INV_METHODS=["e-Transfer","Cash","Cheque","Credit card","Bank transfer","Other"];
async function invRpc(fn,args){let r;try{r=await api("sb_rpc",fn,args||{})}catch(e){r={ok:false,error:e.message}}
  r=r||{ok:false,error:"No answer from the database."};if(r.missing)INV.missing=true;return r}
const invErr=r=>r&&r.missing?INV_MISSING:r&&r.offline?"You're offline. Try again when you're back online.":String((r&&r.error)||"Something went wrong.").replace(/^.*?ERROR:\s*/,"");
function invLoad(force){
  if(!S.me)return Promise.resolve(false);
  if(!force&&INV.at&&Date.now()-INV.at<30000&&INV.list)return Promise.resolve(true);
  if(INV.loading)return INV.loading;
  INV.loading=Promise.all([invRpc("inv_list"),invRpc("inv_settings"),invRpc("inv_tpl_list")]).then(([l,s,t])=>{
    if(l.ok&&l.data){INV.list=l.data.invoices||[];INV.today=String(l.data.today||"").slice(0,10);INV.admin=!!l.data.admin;INV.missing=false;INV.err="";INV.at=Date.now()}
    else if(!l.missing)INV.err=invErr(l);
    if(s.ok&&s.data)INV.settings=s.data;
    if(t.ok&&Array.isArray(t.data))INV.tpls=t.data;
    return l.ok}).finally(()=>{INV.loading=null});
  return INV.loading;
}
const invToday=()=>INV.today||isoDay(new Date());
const invAddDays=(d,n)=>{const x=new Date(d+"T12:00:00");x.setDate(x.getDate()+(+n||0));return isoDay(x)};
const invLong=s=>{const d=new Date(String(s||"").slice(0,10)+"T12:00:00");return isNaN(d)?String(s||""):d.toLocaleDateString("en-US",{month:"long",day:"numeric",year:"numeric"})};
const invShort=s=>{const d=new Date(String(s||"").slice(0,10)+"T12:00:00");return isNaN(d)?"":d.toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"})};
/* exact decimal parsing (no floating point surprises): "25.505" -> 2551 hundredths */
function invFix(x,dp){const s=String(x==null?"":x).replace(/[$,\s]/g,"");const m=/^(\d*)(?:\.(\d*))?$/.exec(s);if(!m||(m[1]===""&&!m[2]))return 0;
  const f=(m[2]||"")+"0".repeat(dp+1),n=parseInt((m[1]||"0")+f.slice(0,dp),10)+(+f[dp]>=5?1:0);return n}
/* same calculation as the database (inv_totals), in whole cents */
function invCalc(items,kind,val,rate){
  let sub=0,tx=0;const lines=[];
  for(const it of items||[]){const q=invFix(it.qty===""||it.qty==null?1:it.qty,2),p=invFix(it.unit_price,2);
    if(!String(it.description||"").trim()&&!String(it.details||"").trim()&&!p){lines.push(0);continue}
    const line=Math.round(q*p/100);lines.push(line);sub+=line;if(it.taxable!==false)tx+=line}
  let disc=0;if(kind==="percent")disc=Math.round(sub*Math.min(invFix(val,2),10000)/10000);else if(kind==="amount")disc=Math.min(invFix(val,2),sub);
  const base=sub>0?tx-Math.round(disc*tx/sub):0,tax=Math.round(base*invFix(rate,3)/100000);
  return {lines:lines.map(c=>c/100),subtotal:sub/100,discount:disc/100,tax:tax/100,total:(sub-disc+tax)/100};
}
function invMoney(n,cur){n=Math.round((+n||0)*100)/100;const a=Math.abs(n).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
  return (n<0?"−":"")+"$"+a+(cur==="USD"?" USD":"")}
const invRate=r=>{const n=+r||0;return (Math.round(n*1000)/1000).toString()};
const invState=i=>i.status==="sent"&&i.overdue?"overdue":i.status;
const INV_ST={draft:"Draft",sent:"Unpaid",overdue:"Overdue",paid:"Paid",void:"Void"};
const invPill=i=>{const s=invState(i);return `<span class="iv-st ${s}"><i></i>${INV_ST[s]}</span>`};
function invCopy(t,msg){
  const done=()=>toast(msg||"Copied");
  if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(t).then(done,fb);else fb();
  function fb(){const a=document.createElement("textarea");a.value=t;a.style.cssText="position:fixed;opacity:0";document.body.appendChild(a);a.select();try{document.execCommand("copy");done()}catch(e){toast("Couldn't copy",{bad:1})}a.remove()}
}
function invBusy(b,on,label){if(!b)return;if(on){b.dataset.h=b.innerHTML;b.classList.add("busy");b.disabled=true;if(label)b.innerHTML=ic("repeat")+esc(label)}
  else{b.classList.remove("busy");b.disabled=false;if(b.dataset.h!=null)b.innerHTML=b.dataset.h}}

/* ---------- page ---------- */
async function renderInvoices(q){
  const pg=$("#pg-invoices");if(!pg)return;
  if(!INV.tabSet){INV.tabSet=1;const t=getP("invTab","all");if(["all","draft","unpaid","overdue","paid","void"].includes(t))INV.f.tab=t}
  if(INV.view==="edit"&&INV.E)return q?null:invEditor();
  if(INV.view==="view"&&INV.cur)return q?null:invView();
  if(!INV.list&&!q)pg.innerHTML=`<div class="iv">${skel([[64],[120,4],[300]])}</div>`;
  const ok=await invLoad(!q);if(S.page!=="invoices"||INV.view!=="list")return;
  if(INV.missing){pg.innerHTML=`<div class="iv"><div class="card empty iv-empty pop" style="margin-top:30px"><div class="bub">${ic("receipt")}</div><b>Invoices aren't set up yet</b>${esc(INV_MISSING)}</div></div>`;hydrateIcons(pg);return}
  if(!INV.list){pg.innerHTML=`<div class="iv"><div class="card empty iv-empty pop" style="margin-top:30px"><b>Invoices couldn't load</b>${esc(INV.err||"Check your connection and try again.")}<button class="btn" style="margin-top:8px" data-retry>Try again</button></div></div>`;
    $("[data-retry]",pg).onclick=()=>renderInvoices(false);return}
  invListPage(pg,q);
}
function invFiltered(tab){
  const f=INV.f,t=tab||f.tab,qq=f.q.trim().toLowerCase();
  return (INV.list||[]).filter(i=>{
    if(f.client&&i.client_name!==f.client)return false;
    const d=String(i.issue_date).slice(0,10);if(f.from&&d<f.from)return false;if(f.to&&d>f.to)return false;
    if(qq&&!(i.number+" "+i.client_name+" "+(i.client_contact||"")+" "+(i.client_email||"")+" "+(i.created_name||"")).toLowerCase().includes(qq))return false;
    if(t==="all")return true;if(t==="unpaid")return i.status==="sent";if(t==="overdue")return i.status==="sent"&&i.overdue;return i.status===t});
}
function invSum(list,key){const by={};list.forEach(i=>{const c=i.currency||"CAD";by[c]=(by[c]||0)+(+(key==="paid"?(i.paid_amount??i.total):i.total)||0)});
  const ks=Object.keys(by);if(!ks.length)return {v:0,txt:invMoney(0)};
  return {v:by.CAD||by[ks[0]]||0,txt:ks.map(k=>invMoney(by[k],k)).join(" · ")}}
function invListPage(pg,q){
  const f=INV.f,base=invFiltered("all"),sent=base.filter(i=>i.status==="sent"),od=sent.filter(i=>i.overdue),paid=base.filter(i=>i.status==="paid"),issued=base.filter(i=>i.status==="sent"||i.status==="paid");
  const sig=JSON.stringify([INV.list,f,INV.settings,INV.admin]);if(q&&pg.dataset.sig===sig)return;pg.dataset.sig=sig;
  const tabs=[["all","All",base.length],["draft","Drafts",base.filter(i=>i.status==="draft").length],["unpaid","Unpaid",sent.length],["overdue","Overdue",od.length],["paid","Paid",paid.length],["void","Void",base.filter(i=>i.status==="void").length]];
  const list=invFiltered(),clients=[...new Set((INV.list||[]).map(i=>i.client_name))].sort((a,b)=>a.localeCompare(b));
  const T=(c,tone,ico,lb,s,dl)=>`<div class="stat ${c} pop"><div class="ico ${tone}"><i class="ic">${svg(ico)}</i></div><div class="lb">${lb}</div><div class="vl" style="font-size:26px">${esc(s.txt)}</div><div class="dl">${esc(dl)}</div></div>`;
  const st=INV.settings||{},noPay=!st.etransfer_email;
  const row=i=>`<button class="iv-r" data-iv="${esc(i.id)}"><span class="iv-no">${esc(i.number)}</span><span class="iv-cl"><b>${esc(i.client_name)}</b><small>${esc([i.client_contact,INV.admin&&i.created_name?"by "+i.created_name:""].filter(Boolean).join(" · ")||(i.template_name||""))}</small></span>
     <span class="iv-dt iv-di">${esc(invShort(i.issue_date))}</span><span class="iv-dt">${i.status==="paid"?"Paid "+esc(invShort(i.paid_on)):i.status==="void"?"Voided":"Due "+esc(invShort(i.due_date))}</span><span class="iv-stc">${invPill(i)}</span><span class="iv-amt">${esc(invMoney(i.total,i.currency))}</span></button>`;
  pg.innerHTML=`<div class="iv">
   <div class="pg-head pop"><div><h3 style="font-size:20px;font-weight:800">Invoices &amp; payments</h3><div class="muted" style="font-size:13px;margin-top:2px;max-width:640px">${INV.admin?"Every invoice on the team. Mark one paid once the money is really in.":"The invoices you've made. An admin marks them paid once the money is in."}</div></div>
    <div class="iv-acts">${INV.admin?`<button class="btn" data-tpl>${ic("note")}Templates</button><button class="btn" data-set>${ic("gear")}Settings</button>`:""}<button class="btn pri" data-new>${ic("plus")}New invoice</button></div></div>
   ${noPay?`<div class="iv-warn pop">${ic("bell")}<div>No e-Transfer email is set yet, so invoices won't show where to send payment. ${INV.admin?`<button data-set>Add it in Settings</button>`:"Ask an admin to add it in Invoices > Settings."}</div></div>`:""}
   <div class="stats">${T("s1","tone-g","receipt","Total invoiced",invSum(issued),`${num(issued.length)} invoice${issued.length===1?"":"s"} issued`)}${T("s2","tone-y","clock","Outstanding",invSum(sent),`${num(sent.length)} waiting for payment`)}${T("s3","tone-o","bell","Overdue",invSum(od),od.length?`${num(od.length)} past the due date`:"Nothing overdue")}${T("s4","tone-g","check","Paid",invSum(paid,"paid"),`${num(paid.length)} paid`)}</div>
   <div class="card iv-list pop"><div class="iv-bar"><div class="iv-tabs" role="tablist" aria-label="Show">${tabs.map(([k,n,c])=>`<button role="tab" data-tab="${k}" class="${f.tab===k?"on":""}${k==="overdue"&&c?" od":""}" aria-selected="${f.tab===k}">${n}<b>${num(c)}</b></button>`).join("")}</div>
     <div class="iv-f"><div class="iv-srch">${ic("search")}<input class="inp" id="ivQ" placeholder="Search number, client or email" value="${esc(f.q)}" aria-label="Search invoices" autocomplete="off"></div>
      <select id="ivC" aria-label="Client"><option value="">All clients</option>${clients.map(c=>`<option${c===f.client?" selected":""}>${esc(c)}</option>`).join("")}</select>
      <input class="inp" type="date" id="ivFrom" value="${esc(f.from)}" aria-label="Invoice date from" title="Invoice date from"><input class="inp" type="date" id="ivTo" value="${esc(f.to)}" aria-label="Invoice date to" title="Invoice date to">
      ${f.q||f.client||f.from||f.to?`<button class="iv-clr" data-clr>Clear</button>`:""}</div></div>
    <div class="iv-rows">${list.length?`<div class="iv-r h" aria-hidden="true"><span>Number</span><span>Client</span><span class="iv-di">Date</span><span>Due</span><span>Status</span><span style="text-align:right">Amount</span></div>${list.map(row).join("")}`
      :`<div class="empty iv-empty"><div class="bub">${ic("receipt")}</div><b>${(INV.list||[]).length?"No invoices match":"No invoices yet"}</b>${(INV.list||[]).length?"Try another tab or clear the filters.":"Make your first one with New invoice."}${(INV.list||[]).length?"":`<button class="btn pri" data-new style="margin-top:8px">${ic("plus")}New invoice</button>`}</div>`}</div></div></div>`;
  hydrateIcons(pg);if(q)quiet(pg);
  $$("[data-new]",pg).forEach(b=>b.onclick=()=>invStart());
  $$("[data-set]",pg).forEach(b=>b.onclick=invSettingsModal);
  const tp=$("[data-tpl]",pg);if(tp)tp.onclick=invTplModal;
  $$("[data-tab]",pg).forEach(b=>b.onclick=()=>{INV.f.tab=b.dataset.tab;setP("invTab",INV.f.tab);invListPage(pg,true)});
  $$("[data-iv]",pg).forEach(b=>b.onclick=()=>invOpen(b.dataset.iv));
  let tq;$("#ivQ",pg).oninput=e=>{clearTimeout(tq);tq=setTimeout(()=>{INV.f.q=e.target.value;invListPage(pg,true);const n=$("#ivQ",pg);n.focus();n.setSelectionRange(n.value.length,n.value.length)},180)};
  $("#ivC",pg).onchange=e=>{INV.f.client=e.target.value;invListPage(pg,true)};
  $("#ivFrom",pg).onchange=e=>{INV.f.from=e.target.value;invListPage(pg,true)};
  $("#ivTo",pg).onchange=e=>{INV.f.to=e.target.value;invListPage(pg,true)};
  const c=$("[data-clr]",pg);if(c)c.onclick=()=>{Object.assign(INV.f,{q:"",client:"",from:"",to:""});invListPage(pg,true)};
}
async function invOpen(id){
  const r=await invRpc("inv_get",{p_id:id});if(!r.ok)return toast(invErr(r),{bad:1});
  INV.cur=r.data;INV.view="view";invView();
}
function invBackToList(){INV.view="list";INV.cur=null;INV.E=null;INV.dirty=false;const pg=$("#pg-invoices");pg.dataset.sig="";renderInvoices(false);pg.scrollTop=0}

/* ---------- editor ---------- */
const invBlankItem=()=>({description:"",details:"",qty:1,unit_price:"",taxable:true});
function invStart(from){
  const st=INV.settings||{},t=invToday();
  INV.E=Object.assign({id:null,version:null,status:"draft",number:"",template_id:null,lead_id:null,deal_id:null,client_name:"",client_contact:"",client_email:"",client_phone:"",client_address:"",
    issue_date:t,due_date:invAddDays(t,st.default_due_days??14),currency:st.currency||"CAD",items:[invBlankItem()],discount_kind:"none",discount_value:"",tax_label:st.tax_label||"HST",tax_rate:+st.tax_rate||0,
    payment_terms:"",notes:"",terms:""},from||{});
  INV.dirty=!!from;INV.view="edit";if(S.page!=="invoices")go("invoices");else invEditor();
}
function invEditFrom(i){INV.E=JSON.parse(JSON.stringify(i));INV.E.items=(INV.E.items||[]).map(x=>({...x}));if(!INV.E.items.length)INV.E.items=[invBlankItem()];INV.dirty=false;INV.view="edit";invEditor()}
function invItemHTML(it,k,cur,isNew){
  return `<div class="iv-it${isNew?" new":""}" data-k="${k}"><div class="m"><input class="inp" data-f="description" maxlength="200" placeholder="Item or service, e.g. Website design" value="${esc(it.description)}" aria-label="Item ${k+1} description">
    <textarea class="inp" data-f="details" maxlength="2000" rows="1" placeholder="Details (optional): what's included" aria-label="Item ${k+1} details">${esc(it.details||"")}</textarea></div>
   <div class="n"><label>Qty<input class="inp" data-f="qty" inputmode="decimal" value="${esc(it.qty??1)}" aria-label="Item ${k+1} quantity"></label><label>Price ($)<input class="inp" data-f="unit_price" inputmode="decimal" placeholder="0.00" value="${esc(it.unit_price??"")}" aria-label="Item ${k+1} price"></label>
    <label class="tx" title="Charge tax on this item"><input type="checkbox" data-f="taxable"${it.taxable!==false?" checked":""}>Tax</label></div>
   <div class="ft"><button type="button" class="rm" data-rm="${k}" aria-label="Remove item ${k+1}">${ic("trash")}Remove</button><span>Amount</span><b data-amt="${k}">${esc(invMoney(0,cur))}</b></div></div>`;
}
function invTplChips(E){const ts=(INV.tpls||[]).filter(t=>!t.archived);if(!ts.length)return "";
  return `<div class="iv-tpls" role="group" aria-label="Start from a template"><button type="button" class="chip${!E.template_id?" on":""}" data-tplpick="">Blank</button>${ts.map(t=>`<button type="button" class="chip${E.template_id===t.id?" on":""}" data-tplpick="${esc(t.id)}" title="${esc(t.summary||t.category||"")}">${esc(t.name)}</button>`).join("")}</div>`}
function invEditor(){
  const pg=$("#pg-invoices"),E=INV.E,st=INV.settings||{},isNew=!E.id;pg.dataset.sig="";
  const fld=(id,lb,val,o={})=>`<div${o.wide?' style="grid-column:1/3"':""}><label class="l" for="${id}">${lb}</label>${o.area?`<textarea class="inp" id="${id}" rows="${o.rows||2}" maxlength="${o.max||400}"${o.ph?` placeholder="${esc(o.ph)}"`:""}>${esc(val)}</textarea>`:`<input class="inp" id="${id}" ${o.type?`type="${o.type}"`:""} maxlength="${o.max||160}"${o.ph?` placeholder="${esc(o.ph)}"`:""}${o.im?` inputmode="${o.im}"`:""} value="${esc(val)}" autocomplete="off">`}</div>`;
  pg.innerHTML=`<div class="iv"><div class="iv-top pop"><button class="iv-back" data-back aria-label="Back to invoices">${ic("back")}</button><h3>${isNew?"New invoice":"Edit "+esc(E.number)}${isNew?"":invPill(E)}</h3></div>
   <div class="iv-grid"><div>
    ${invTplChips(E)?`<div class="card iv-sec pop"><h4>${ic("note")}Start from a template</h4>${invTplChips(E)}<div class="note">A template fills in the items, payment terms, notes and terms. You can change anything afterwards.</div></div>`:""}
    <div class="card iv-sec pop"><h4>${ic("user")}Client</h4><div class="fg">
      <div class="iv-cwrap" style="grid-column:1/3"><label class="l" for="ivCn">Client or business name</label><input class="inp" id="ivCn" maxlength="120" placeholder="Start typing to pick an existing client, or type a new one" value="${esc(E.client_name)}" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="ivSug" style="width:100%"><div class="iv-sug" id="ivSug" role="listbox"></div>
       <div class="iv-link" id="ivLinked">${E.lead_id||E.deal_id?`${ic("check")}Linked to ${E.deal_id?"a deal":"a lead"} in Leafline <button type="button" data-unlink>Unlink</button>`:""}</div></div>
      ${fld("ivCc","Contact person",E.client_contact,{max:120,ph:"e.g. Sam Lee"})}${fld("ivCe","Email",E.client_email,{type:"email",ph:"name@business.com"})}
      ${fld("ivCp","Phone",E.client_phone,{type:"tel",max:40})}${fld("ivCa","Address",E.client_address,{area:1,max:400,ph:"Street, city, province, postal code"})}</div></div>
    <div class="card iv-sec pop"><h4>${ic("cal")}Dates</h4><div class="fg">
      ${fld("ivId","Invoice date",String(E.issue_date).slice(0,10),{type:"date"})}${fld("ivDd","Payment due",String(E.due_date).slice(0,10),{type:"date"})}
      <div style="grid-column:1/3;display:flex;gap:6px;flex-wrap:wrap" role="group" aria-label="Due in">${[0,7,14,30].map(n=>`<button type="button" class="chip" data-due="${n}">${n?"In "+n+" days":"On receipt"}</button>`).join("")}</div></div></div>
    <div class="card iv-sec pop"><h4>${ic("log")}Items</h4><div class="iv-items" id="ivItems">${E.items.map((it,k)=>invItemHTML(it,k,E.currency)).join("")}</div>
      <button type="button" class="btn iv-add" data-additem>${ic("plus")}Add item</button></div>
    <div class="card iv-sec iv-txt pop"><h4>${ic("note")}Payment terms, notes and terms</h4>
      <label class="l" for="ivPt">Payment terms</label><textarea class="inp" id="ivPt" maxlength="2000" rows="2" placeholder="e.g. 50% deposit to start, the rest when the website goes live">${esc(E.payment_terms)}</textarea>
      <label class="l" for="ivNo">Notes for the client</label><textarea class="inp" id="ivNo" maxlength="4000" rows="2" placeholder="Shown on the invoice">${esc(E.notes)}</textarea>
      <label class="l" for="ivTe">Terms and conditions</label><textarea class="inp" id="ivTe" maxlength="20000" rows="5" placeholder="Shown at the end of the invoice">${esc(E.terms)}</textarea></div>
   </div>
   <div class="iv-side"><div class="card iv-sec pop"><h4>${ic("dollar")}Total</h4>
     <div class="iv-dc"><div><label class="l" for="ivDk">Discount</label><select id="ivDk"><option value="none">No discount</option><option value="percent"${E.discount_kind==="percent"?" selected":""}>Percent (%)</option><option value="amount"${E.discount_kind==="amount"?" selected":""}>Amount ($)</option></select></div>
      <div><label class="l" for="ivDv">${E.discount_kind==="percent"?"Percent":"Amount"}</label><input class="inp" id="ivDv" inputmode="decimal" placeholder="0" value="${esc(E.discount_kind==="none"?"":E.discount_value)}"${E.discount_kind==="none"?" disabled":""}></div>
      <div><label class="l" for="ivTl">Tax name</label><input class="inp" id="ivTl" maxlength="20" value="${esc(E.tax_label)}"></div>
      <div><label class="l" for="ivTr">Tax rate (%)</label><input class="inp" id="ivTr" inputmode="decimal" value="${esc(E.tax_rate)}"></div>
      <div style="grid-column:1/3"><label class="l" for="ivCu">Currency</label><select id="ivCu"><option${E.currency==="CAD"?" selected":""}>CAD</option><option${E.currency==="USD"?" selected":""}>USD</option></select></div></div>
     <div class="iv-tot" id="ivTot" aria-live="polite"></div>
     ${st.etransfer_email?`<div class="note" style="margin-top:10px">Paid by Interac e-Transfer to <b>${esc(st.etransfer_email)}</b>. The invoice shows how.</div>`:`<div class="note" style="margin-top:10px;color:#F1D58A">No e-Transfer email is set yet${INV.admin?" (Invoices > Settings)":". Ask an admin to add it"}.</div>`}
     <div class="iv-err" id="ivErr" role="alert"></div>
     <div class="iv-save">${E.status==="draft"?`<button class="btn pri" data-save="sent">${ic("send")}Save and issue</button><button class="btn" data-save="draft">${ic("check")}Save draft</button>`:`<button class="btn pri" data-save="sent">${ic("check")}Save changes</button>`}<button class="btn" data-back>Cancel</button></div></div></div></div></div>`;
  hydrateIcons(pg);pg.scrollTop=0;invWireEditor(pg);invTotals(pg);
}
function invRead(pg){
  const E=INV.E,v=id=>{const e=$("#"+id,pg);return e?e.value:""};
  Object.assign(E,{client_name:v("ivCn").trim(),client_contact:v("ivCc").trim(),client_email:v("ivCe").trim(),client_phone:v("ivCp").trim(),client_address:v("ivCa").trim(),
    issue_date:v("ivId"),due_date:v("ivDd"),discount_kind:v("ivDk"),discount_value:v("ivDv"),tax_label:v("ivTl").trim()||"Tax",tax_rate:v("ivTr"),currency:v("ivCu"),
    payment_terms:v("ivPt"),notes:v("ivNo"),terms:v("ivTe")});
  $$(".iv-it",pg).forEach(el=>{const k=+el.dataset.k,it=E.items[k];if(!it)return;$$("[data-f]",el).forEach(i=>{it[i.dataset.f]=i.type==="checkbox"?i.checked:i.value})});
  return E;
}
function invTotals(pg){
  const E=invRead(pg),c=invCalc(E.items,E.discount_kind,E.discount_value,E.tax_rate),cur=E.currency;
  c.lines.forEach((l,k)=>{const b=$(`[data-amt="${k}"]`,pg);if(b)b.textContent=invMoney(l,cur)});
  $("#ivTot",pg).innerHTML=`<div class="r"><span>Subtotal</span><b>${esc(invMoney(c.subtotal,cur))}</b></div>
   ${c.discount?`<div class="r neg"><span>Discount${E.discount_kind==="percent"?" ("+esc(invRate(E.discount_value))+"%)":""}</span><b>−${esc(invMoney(c.discount,cur))}</b></div>`:""}
   ${+E.tax_rate?`<div class="r"><span>${esc(E.tax_label)} (${esc(invRate(E.tax_rate))}%)</span><b>${esc(invMoney(c.tax,cur))}</b></div>`:""}
   <div class="r t"><span>Total</span><b>${esc(invMoney(c.total,cur))}</b></div>`;
  return c;
}
function invWireEditor(pg){
  const E=INV.E,items=$("#ivItems",pg),dirty=()=>{INV.dirty=true};
  const redrawItems=(newK)=>{invRead(pg);items.innerHTML=E.items.map((it,k)=>invItemHTML(it,k,E.currency,k===newK)).join("");hydrateIcons(items);invTotals(pg);grow()};
  const grow=()=>$$("textarea",pg).forEach(t=>{t.style.height="auto";t.style.height=Math.min(t.scrollHeight+2,t.id==="ivTe"?420:220)+"px"});
  const root=$(".iv",pg);
  root.addEventListener("input",e=>{if(e.target.closest(".iv-sug"))return;dirty();if(e.target.tagName==="TEXTAREA"){e.target.style.height="auto";e.target.style.height=Math.min(e.target.scrollHeight+2,e.target.id==="ivTe"?420:220)+"px"}
    if(e.target.closest(".iv-it")||["ivDv","ivTr","ivTl"].includes(e.target.id))invTotals(pg)});
  root.addEventListener("change",e=>{dirty();if(e.target.id==="ivDk"){const dv=$("#ivDv",pg);dv.disabled=e.target.value==="none";if(dv.disabled)dv.value="";$("label[for=ivDv]",pg).textContent=e.target.value==="percent"?"Percent":"Amount";invTotals(pg)}
    if(e.target.id==="ivCu"||e.target.dataset.f==="taxable")invTotals(pg)});
  items.addEventListener("click",e=>{const b=e.target.closest("[data-rm]");if(!b)return;invRead(pg);E.items.splice(+b.dataset.rm,1);if(!E.items.length)E.items.push(invBlankItem());dirty();redrawItems()});
  $("[data-additem]",pg).onclick=()=>{invRead(pg);if(E.items.length>=60)return toast("An invoice can have at most 60 items",{bad:1});E.items.push(invBlankItem());dirty();redrawItems(E.items.length-1);
    const n=$(`.iv-it[data-k="${E.items.length-1}"] [data-f=description]`,pg);n&&n.focus()};
  $$("[data-due]",pg).forEach(b=>b.onclick=()=>{const d=$("#ivId",pg).value||invToday();$("#ivDd",pg).value=invAddDays(d,+b.dataset.due);dirty()});
  $$("[data-back]",pg).forEach(b=>b.onclick=()=>{if(INV.dirty&&!confirm("Leave without saving? Your changes to this invoice will be lost."))return;
    if(E.id&&INV.cur&&INV.cur.id===E.id){INV.E=null;INV.dirty=false;INV.view="view";invView()}else invBackToList()});
  $$("[data-tplpick]",pg).forEach(b=>b.onclick=()=>{const t=(INV.tpls||[]).find(x=>x.id===b.dataset.tplpick);invRead(pg);
    const has=E.items.some(x=>String(x.description).trim())||E.payment_terms||E.terms||E.notes;
    if(has&&!confirm(t?`Use "${t.name}"? It replaces the items, payment terms, notes and terms you have now.`:"Start blank? This clears the items, payment terms, notes and terms."))return;
    if(t){Object.assign(E,{template_id:t.id,items:(t.items||[]).length?t.items.map(x=>({...x})):[invBlankItem()],payment_terms:t.payment_terms||"",notes:t.notes||"",terms:t.terms||""});
      E.due_date=invAddDays(E.issue_date||invToday(),t.due_days??14);if(t.tax_rate!=null)E.tax_rate=+t.tax_rate}
    else Object.assign(E,{template_id:null,items:[invBlankItem()],payment_terms:"",notes:"",terms:""});
    INV.dirty=true;invEditor();toast(t?`Filled in from "${t.name}"`:"Started blank")});
  const un=$("[data-unlink]",pg);if(un)un.onclick=()=>{E.lead_id=null;E.deal_id=null;$("#ivLinked",pg).innerHTML="";dirty()};
  invClientPicker(pg);
  $$("[data-save]",pg).forEach(b=>b.onclick=()=>invSave(pg,b.dataset.save,b));
  setTimeout(grow,0);
}
function invClientPicker(pg){
  const inp=$("#ivCn",pg),box=$("#ivSug",pg);let t,res=[],sel=-1,seq=0;
  const close=()=>{box.classList.remove("on");inp.setAttribute("aria-expanded","false");sel=-1};
  const paint=()=>{if(!res.length)return close();box.innerHTML=res.map((c,k)=>`<button type="button" role="option" data-k="${k}" class="${k===sel?"on":""}"><b>${esc(c.name)}</b><small>${esc([c.contact,c.email,c.phone].filter(Boolean).join(" · ")||c.address||"")}</small><span class="src">${c.source==="invoice"?"Past invoice":c.source==="deal"?"Deal":"Lead"}</span></button>`).join("");
    box.classList.add("on");inp.setAttribute("aria-expanded","true")};
  const pick=c=>{const E=INV.E;inp.value=c.name;const set=(id,v)=>{const e=$("#"+id,pg);if(e&&v&&!e.value.trim())e.value=v};
    set("ivCc",c.contact);set("ivCe",c.email);set("ivCp",c.phone);set("ivCa",c.address);E.lead_id=c.lead_id||null;E.deal_id=c.deal_id||null;
    $("#ivLinked",pg).innerHTML=E.lead_id||E.deal_id?`${ic("check")}Linked to ${E.deal_id?"a deal":"a lead"} in Leafline <button type="button" data-unlink>Unlink</button>`:"";
    const un=$("[data-unlink]",pg);if(un)un.onclick=()=>{E.lead_id=null;E.deal_id=null;$("#ivLinked",pg).innerHTML="";INV.dirty=true};
    INV.dirty=true;close();$("#ivCc",pg).focus()};
  inp.addEventListener("input",()=>{clearTimeout(t);const q=inp.value.trim();if(q.length<2){res=[];return close()}
    t=setTimeout(async()=>{const my=++seq,r=await invRpc("inv_clients",{p_q:q});if(my!==seq||!r.ok)return;res=(r.data||[]).slice(0,12);sel=-1;paint()},220)});
  inp.addEventListener("keydown",e=>{if(!box.classList.contains("on"))return;
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();sel=(sel+(e.key==="ArrowDown"?1:-1)+res.length)%res.length;paint()}
    else if(e.key==="Enter"&&sel>=0){e.preventDefault();pick(res[sel])}else if(e.key==="Escape"){e.stopPropagation();close()}});
  box.addEventListener("mousedown",e=>{const b=e.target.closest("[data-k]");if(!b)return;e.preventDefault();pick(res[+b.dataset.k])});
  inp.addEventListener("blur",()=>setTimeout(close,150));
}
async function invSave(pg,status,btn){
  const E=invRead(pg),err=$("#ivErr",pg);err.textContent="";
  const items=E.items.filter(x=>String(x.description).trim()||String(x.details||"").trim()||invFix(x.unit_price,2));
  if(!E.client_name){err.textContent="Enter the client's name.";return $("#ivCn",pg).focus()}
  if(!items.length){err.textContent="Add at least one item.";return}
  if(items.some(x=>!String(x.description).trim())){err.textContent="Every item needs a description.";return}
  if(items.some(x=>!(invFix(x.qty===""?1:x.qty,2)>0))){err.textContent="Quantities must be above 0.";return}
  if(!/^\d{4}-\d{2}-\d{2}$/.test(E.issue_date)||!/^\d{4}-\d{2}-\d{2}$/.test(E.due_date)){err.textContent="Pick the invoice date and the date payment is due.";return}
  if(E.due_date<E.issue_date){err.textContent="The due date can't be before the invoice date.";return}
  const body={...E,status,items:items.map(x=>({description:String(x.description).trim(),details:String(x.details||"").trim(),qty:String(x.qty===""?1:x.qty).replace(/[,\s]/g,""),unit_price:String(x.unit_price===""?0:x.unit_price).replace(/[$,\s]/g,""),taxable:x.taxable!==false})),
    discount_value:E.discount_kind==="none"?0:String(E.discount_value||0).replace(/[$,%\s]/g,""),tax_rate:String(E.tax_rate||0).replace(/[%\s]/g,"")};
  ["overdue","template_name","created_name","paid_by_name","item_count","subtotal","discount_total","tax_total","total"].forEach(k=>delete body[k]);
  $$("[data-save]",pg).forEach(b=>b.disabled=true);invBusy(btn,true,"Saving...");
  const r=await invRpc("inv_save",{p:body});
  $$("[data-save]",pg).forEach(b=>b.disabled=false);invBusy(btn,false);
  if(!r.ok){err.textContent=invErr(r);return}
  const was=E.id;INV.cur=r.data;INV.E=null;INV.dirty=false;INV.view="view";INV.at=0;invLoad(true);
  toast(was?`Saved ${r.data.number}`:status==="sent"?`Invoice ${r.data.number} issued`:`Draft ${r.data.number} saved`);
  logNote((was?"Updated":"Created")+" invoice "+r.data.number+" for "+r.data.client_name);invView();
}

/* ---------- one invoice ---------- */
function invView(){
  const pg=$("#pg-invoices"),i=INV.cur,st=INV.settings||{},s=invState(i),adm=INV.admin,cur=i.currency;pg.dataset.sig="";
  const canEdit=i.status==="draft"||i.status==="sent";
  const b=(k,icn,lb,cls)=>`<button class="btn${cls?" "+cls:""}" data-a="${k}">${ic(icn)}${lb}</button>`;
  const acts=[b("pdf","download","Download PDF","pri"),
    i.status==="draft"?b("issue","send","Issue invoice"):"",
    i.status==="sent"&&i.client_email?b("email","mail","Email client"):"",
    canEdit?b("edit","edit","Edit"):"",
    adm&&i.status==="sent"?b("pay","check","Mark paid"):"",
    adm&&i.status==="paid"?b("unpay","undo","Undo payment"):"",
    b("dup","copy","Duplicate"),
    i.status==="sent"?b("draft","undo","Back to draft"):"",
    adm&&(i.status==="sent"||i.status==="draft")?b("void","x","Void","danger"):"",
    adm&&i.status==="void"?b("restore","undo","Restore as draft"):"",
    adm?b("totpl","note","Save as template"):"",
    i.status==="draft"?b("del","trash","Delete draft","danger"):""].join("");
  const it=(i.items||[]).map(x=>`<tr><td><b>${esc(x.description)}</b>${x.details?`<small>${esc(x.details)}</small>`:""}${+i.tax_rate&&x.taxable===false?`<small>No ${esc(i.tax_label)} on this item</small>`:""}</td><td class="r hq">${esc(invRate(x.qty))}</td><td class="r hq">${esc(invMoney(x.unit_price,cur))}</td><td class="r">${esc(invMoney(Math.round(invFix(x.qty,2)*invFix(x.unit_price,2)/100)/100,cur))}</td></tr>`).join("");
  const due=i.status==="paid"?`Paid ${esc(invLong(i.paid_on))}`:i.status==="void"?`Voided${i.void_reason?": "+esc(i.void_reason):""}`:i.status==="draft"?`Draft · due ${esc(invLong(i.due_date))} once issued`:`${i.overdue?"Overdue since":"Due"} ${esc(invLong(i.due_date))}`;
  const ref=`Invoice ${i.number}`,pay=st.etransfer_email&&i.status!=="void"?`<div class="iv-pay"><h5>${ic("dollar")}${i.status==="paid"?"Paid by "+esc(i.paid_method||"payment"):"How the client pays: Interac e-Transfer"}</h5>
     ${i.status==="paid"?`<p>${esc(invMoney(i.paid_amount,cur))} received ${esc(invLong(i.paid_on))}${i.paid_ref?" · reference "+esc(i.paid_ref):""}${i.paid_by_name?" · marked paid by "+esc(i.paid_by_name):""}${i.paid_note?`<br>${esc(i.paid_note)}`:""}</p>`
     :`<div class="em">${esc(st.etransfer_email)}<button type="button" data-a="copyem">${ic("copy")}Copy email</button><button type="button" data-a="copypay">${ic("copy")}Copy payment details</button></div>
       <p>Send ${esc(invMoney(i.total,cur))} to this email from any Canadian bank${st.etransfer_name?`, payable to ${esc(st.etransfer_name)}`:""}. Put <b>${esc(ref)}</b> in the message.${st.payment_note?`<br>${esc(st.payment_note)}`:""}</p>
       <p style="font-size:12px">The PDF has a button that opens the client's email app, addressed to you, so they can tell you once they've sent it. It can't send the e-Transfer itself: that's done in their bank's app.</p>`}</div>`:"";
  pg.innerHTML=`<div class="iv"><div class="iv-top pop"><button class="iv-back" data-back aria-label="Back to invoices">${ic("back")}</button><h3>${esc(i.number)}${invPill(i)}</h3></div>
   <div class="card iv-hero pop"><div class="who"><b>${esc(i.client_name)}</b><div>${esc([i.client_contact,i.client_email,i.client_phone].filter(Boolean).join(" · "))}</div></div>
    <div><div class="big">${esc(invMoney(i.status==="paid"?i.paid_amount:i.total,cur))}</div><div class="iv-due${s==="overdue"?" od":""}">${due}</div></div></div>
   <div class="iv-btns pop">${acts}</div>
   <div class="iv-grid"><div>
    <div class="card iv-sec pop"><h4>${ic("log")}Items</h4><table class="iv-tbl"><thead><tr><th>Description</th><th class="r hq">Qty</th><th class="r hq">Price</th><th class="r">Amount</th></tr></thead><tbody>${it}</tbody></table></div>
    ${i.payment_terms||i.notes?`<div class="card iv-sec pop">${i.payment_terms?`<h4>${ic("clock")}Payment terms</h4><div class="iv-long">${esc(i.payment_terms)}</div>`:""}${i.notes?`<h4 style="margin-top:${i.payment_terms?16:0}px">${ic("note")}Notes</h4><div class="iv-long">${esc(i.notes)}</div>`:""}</div>`:""}
    ${i.terms?`<div class="card iv-sec pop"><details><summary>${ic("next")}Terms and conditions</summary><div class="iv-long">${esc(i.terms)}</div></details></div>`:""}
   </div><div class="iv-side">
    <div class="card iv-sec pop"><h4>${ic("dollar")}Total</h4><div class="iv-tot"><div class="r"><span>Subtotal</span><b>${esc(invMoney(i.subtotal,cur))}</b></div>
      ${+i.discount_total?`<div class="r neg"><span>Discount${i.discount_kind==="percent"?" ("+esc(invRate(i.discount_value))+"%)":""}</span><b>−${esc(invMoney(i.discount_total,cur))}</b></div>`:""}
      ${+i.tax_rate?`<div class="r"><span>${esc(i.tax_label)} (${esc(invRate(i.tax_rate))}%)</span><b>${esc(invMoney(i.tax_total,cur))}</b></div>`:""}
      <div class="r t"><span>Total</span><b>${esc(invMoney(i.total,cur))}</b></div></div>${pay?`<div style="margin-top:14px">${pay}</div>`:""}</div>
    <div class="card iv-sec pop"><h4>${ic("briefcase")}Details</h4><dl class="iv-dl"><dt>Invoice date</dt><dd>${esc(invLong(i.issue_date))}</dd><dt>Due</dt><dd>${esc(invLong(i.due_date))}</dd>
      ${i.client_address?`<dt>Address</dt><dd>${esc(i.client_address)}</dd>`:""}${i.template_name?`<dt>Template</dt><dd>${esc(i.template_name)}</dd>`:""}
      <dt>Made by</dt><dd><span class="plink" data-au="${esc(i.created_by)}" tabindex="0" role="button">${esc(i.created_name||"")}</span> · ${esc(invShort(i.created_at))}</dd>${i.sent_at?`<dt>Issued</dt><dd>${esc(invShort(i.sent_at))}</dd>`:""}</dl></div>
   </div></div></div>`;
  hydrateIcons(pg);pg.scrollTop=0;
  $("[data-back]",pg).onclick=invBackToList;
  $$("[data-a]",pg).forEach(x=>x.onclick=()=>invAct(x.dataset.a,x));
}
/* email links: in the PC app they go to the computer's email app (through Electron); on the website the browser does it */
function invMailto(url){if(window.leafline)window.open(url,"_blank");else location.href=url}
document.addEventListener("click",e=>{const a=e.target.closest&&e.target.closest('a[href^="mailto:"]');if(!a||!window.leafline)return;e.preventDefault();window.open(a.getAttribute("href"),"_blank")});
function invPayText(i){const st=INV.settings||{};return `Pay by Interac e-Transfer\nSend to: ${st.etransfer_email}${st.etransfer_name?" ("+st.etransfer_name+")":""}\nAmount: ${invMoney(i.total,i.currency)}\nMessage: Invoice ${i.number}\nDue: ${invLong(i.due_date)}${st.payment_note?"\n"+st.payment_note:""}`}
async function invAct(a,btn){
  const i=INV.cur,st=INV.settings||{};
  const after=async(r,msg)=>{if(!r.ok)return toast(invErr(r),{bad:1}),false;INV.at=0;invLoad(true);if(msg)toast(msg);
    const g=r.data&&r.data.items?r:await invRpc("inv_get",{p_id:(r.data&&r.data.id)||i.id});if(g.ok){INV.cur=g.data;invView()}return true};
  if(a==="pdf")return invDownload(i,btn);
  if(a==="edit")return invEditFrom(i);
  if(a==="copyem")return invCopy(st.etransfer_email,"e-Transfer email copied");
  if(a==="copypay")return invCopy(invPayText(i),"Payment details copied");
  if(a==="email"){const nm=i.client_contact||i.client_name,me=(S.me&&S.me.display_name)||"",co=st.company_name||"Leafline";
    const body=`Hi ${nm},\n\nHere is invoice ${i.number} from ${co} for ${invMoney(i.total,i.currency)}, due ${invLong(i.due_date)}. The PDF is attached.\n\n`+(st.etransfer_email?invPayText(i)+"\n\n":"")+`Thank you,\n${me}\n${co}`;
    invMailto(`mailto:${encodeURIComponent(i.client_email)}?subject=${encodeURIComponent(`Invoice ${i.number} from ${co}`)}&body=${encodeURIComponent(body)}`);
    return toast("Your email app is opening. Attach the PDF (Download PDF) before you send it.",{ms:6000})}
  if(a==="issue"){invBusy(btn,true,"Issuing...");const r=await invRpc("inv_set_status",{p_id:i.id,p_status:"sent"});invBusy(btn,false);return after(r,`Invoice ${i.number} issued`)}
  if(a==="draft"){const r=await invRpc("inv_set_status",{p_id:i.id,p_status:"draft"});return after(r,"Moved back to draft")}
  if(a==="restore"){const r=await invRpc("inv_set_status",{p_id:i.id,p_status:"draft"});return after(r,"Restored as a draft")}
  if(a==="void")return invVoidModal(i,after);
  if(a==="unpay"){if(!confirm(`Undo the payment on ${i.number}? It goes back to unpaid.`))return;const r=await invRpc("inv_unpay",{p_id:i.id});return after(r,"Payment removed")}
  if(a==="del"){if(!confirm(`Delete draft ${i.number}? This can't be undone.`))return;const r=await invRpc("inv_delete",{p_id:i.id});if(!r.ok)return toast(invErr(r),{bad:1});
    toast(`Draft ${i.number} deleted`);INV.at=0;return invBackToList()}
  if(a==="dup"){invBusy(btn,true,"Copying...");const r=await invRpc("inv_duplicate",{p_id:i.id});invBusy(btn,false);if(!r.ok)return toast(invErr(r),{bad:1});
    INV.at=0;invLoad(true);toast(`Copied into draft ${r.data.number}`);return invEditFrom(r.data)}
  if(a==="pay")return invPayModal(i,after);
  if(a==="totpl")return invTplEdit({name:i.template_name?i.template_name+" (copy)":i.client_name+" template",category:"",summary:"",items:i.items,payment_terms:i.payment_terms,notes:i.notes,terms:i.terms,due_days:Math.max(0,Math.round((new Date(i.due_date)-new Date(i.issue_date))/864e5)),tax_rate:null,source:"Invoice "+i.number});
}
function invVoidModal(i,after){
  openModal(`<h2>Void ${esc(i.number)}?</h2><div class="muted" style="margin:6px 0 14px;font-size:13.5px;line-height:1.5">It stays in the list, marked void, and can't be paid. Nothing is deleted. An admin can restore it later.</div>
   <label class="l" for="ivVr">Reason (optional)</label><input class="inp" id="ivVr" maxlength="200" placeholder="e.g. Client cancelled" style="width:100%">
   <div class="iv-err" id="ivVe" role="alert"></div>
   <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:6px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok style="background:linear-gradient(160deg,#E46F6F,#B94A4A);color:#fff">${ic("x")}Void invoice</button></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $("[data-ok]",ov).onclick=async()=>{const b=$("[data-ok]",ov);invBusy(b,true,"Voiding...");
      const r=await invRpc("inv_set_status",{p_id:i.id,p_status:"void",p_reason:$("#ivVr",ov).value.trim()});invBusy(b,false);
      if(!r.ok)return $("#ivVe",ov).textContent=invErr(r);close();after(r,`${i.number} voided`)}});
}
function invPayModal(i,after){
  openModal(`<h2>Mark ${esc(i.number)} paid</h2><div class="muted" style="margin:4px 0 14px;font-size:13.5px">Only once the money is really in. This is recorded with your name.</div>
   <div class="fg"><div><label class="l" for="ipA">Amount received ($)</label><input class="inp" id="ipA" inputmode="decimal" value="${esc((+i.total).toFixed(2))}"></div>
    <div><label class="l" for="ipD">Date received</label><input class="inp" id="ipD" type="date" max="${esc(invToday())}" value="${esc(invToday())}"></div>
    <div><label class="l" for="ipM">How</label><select id="ipM">${INV_METHODS.map(m=>`<option>${m}</option>`).join("")}</select></div>
    <div><label class="l" for="ipR">Reference (optional)</label><input class="inp" id="ipR" maxlength="80" placeholder="e.g. e-Transfer reference number"></div>
    <div style="grid-column:1/3"><label class="l" for="ipN">Note (optional)</label><input class="inp" id="ipN" maxlength="400"></div></div>
   <div class="iv-err" id="ipE" role="alert"></div>
   <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:6px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>${ic("check")}Mark paid</button></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $("[data-ok]",ov).onclick=async()=>{const e=$("#ipE",ov),amt=invFix($("#ipA",ov).value,2)/100,d=$("#ipD",ov).value;e.textContent="";
      if(!(amt>0))return e.textContent="Enter the amount that was paid.";if(!d)return e.textContent="Pick the day it was paid.";
      if(Math.abs(amt-(+i.total))>=0.01&&!confirm(`That's ${invMoney(amt,i.currency)}, not the full ${invMoney(i.total,i.currency)}. Mark it paid anyway?`))return;
      const b=$("[data-ok]",ov);invBusy(b,true,"Saving...");
      const r=await invRpc("inv_pay",{p_id:i.id,p_amount:amt,p_on:d,p_method:$("#ipM",ov).value,p_ref:$("#ipR",ov).value.trim(),p_note:$("#ipN",ov).value.trim()});
      invBusy(b,false);if(!r.ok)return e.textContent=invErr(r);close();logNote(`Invoice ${i.number} marked paid`);after(r,`${i.number} marked paid`)}});
}

/* ---------- settings (admins) ---------- */
function invSettingsModal(){
  if(!INV.admin)return;const s=INV.settings||{};
  const f=(k,lb,o={})=>`<div${o.wide?' style="grid-column:1/3"':""}><label class="l" for="is_${k}">${lb}</label>${o.area?`<textarea class="inp" id="is_${k}" rows="2" maxlength="${o.max||300}" style="width:100%">${esc(s[k]??"")}</textarea>`:`<input class="inp" id="is_${k}" ${o.type?`type="${o.type}"`:""}${o.im?` inputmode="${o.im}"`:""} maxlength="${o.max||160}"${o.ph?` placeholder="${esc(o.ph)}"`:""} value="${esc(s[k]??"")}" style="width:100%">`}</div>`;
  openModal(`<div class="iv-set"><h2>Invoice settings</h2><div class="muted" style="margin:4px 0 0;font-size:13.5px">Shown on every invoice and PDF. Only admins can change these.</div>
   <h5>Interac e-Transfer</h5><div class="fg">${f("etransfer_email","Send e-Transfers to (email)",{type:"email",ph:"payments@yourdomain.com",wide:1})}${f("etransfer_name","Recipient name (optional)",{max:80,ph:"Leafline Web Services"})}<div></div>
    ${f("payment_note","Extra payment instructions (optional)",{area:1,max:1000,wide:1})}</div>
   <h5>Company</h5><div class="fg">${f("company_name","Company name",{max:80})}${f("company_phone","Phone",{max:40})}${f("company_email","Email",{type:"email"})}${f("company_website","Website",{ph:"leaflineweb.com"})}${f("company_address","Address",{area:1,wide:1})}</div>
   <h5>Tax</h5><div class="fg">${f("tax_label","Tax name",{max:20,ph:"HST"})}${f("tax_rate","Default tax rate (%)",{im:"decimal",ph:"0"})}${f("tax_number","Tax / business number (optional)",{max:40,ph:"e.g. 123456789 RT0001",wide:1})}</div>
   <div class="note">Only charge tax if the business is registered for it. New invoices start with this rate; each invoice can change it.</div>
   <h5>Numbers and defaults</h5><div class="fg">${f("number_prefix","Invoice number prefix",{max:8,ph:"LF"})}${f("default_due_days","Days to pay",{im:"numeric"})}
    <div><label class="l" for="is_currency">Currency</label><select id="is_currency"><option${s.currency!=="USD"?" selected":""}>CAD</option><option${s.currency==="USD"?" selected":""}>USD</option></select></div>${f("footer","Footer line",{max:300})}</div>
   <div class="iv-err" id="isE" role="alert"></div>
   <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:6px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>${ic("check")}Save settings</button></div></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    $("[data-ok]",ov).onclick=async()=>{const e=$("#isE",ov),v=k=>$("#is_"+k,ov).value.trim(),p={};e.textContent="";
      ["etransfer_email","etransfer_name","payment_note","company_name","company_phone","company_email","company_website","company_address","tax_label","tax_number","footer"].forEach(k=>p[k]=v(k));
      p.tax_rate=invFix(v("tax_rate")||"0",3)/1000;p.default_due_days=parseInt(v("default_due_days")||"14",10);p.number_prefix=v("number_prefix").toUpperCase()||"LF";p.currency=$("#is_currency",ov).value;
      if(!Number.isFinite(p.default_due_days))return e.textContent="Days to pay must be a number.";
      const b=$("[data-ok]",ov);invBusy(b,true,"Saving...");const r=await invRpc("inv_settings_set",{p});invBusy(b,false);
      if(!r.ok)return e.textContent=invErr(r);INV.settings=r.data;close();toast("Invoice settings saved");const pg=$("#pg-invoices");pg.dataset.sig="";if(INV.view==="list")renderInvoices(true);else if(INV.view==="view")invView()}});
}

/* ---------- templates (admins) ---------- */
function invTplModal(){
  if(!INV.admin)return;
  const draw=ov=>{const ts=INV.tpls||[];$(".iv-tl",ov).innerHTML=ts.length?ts.map(t=>`<div class="t${t.archived?" arch":""}"><b>${esc(t.name)}${t.archived?" (archived)":""}</b><small>${esc([t.category,`${(t.items||[]).length} item${(t.items||[]).length===1?"":"s"}`,t.source?"from "+t.source:""].filter(Boolean).join(" · "))}</small>
      <div class="a"><button class="btn sm" data-ed="${esc(t.id)}">${ic("edit")}Edit</button><button class="btn sm" data-ar="${esc(t.id)}">${t.archived?"Restore":"Archive"}</button></div></div>`).join("")
      :`<div class="empty" style="padding:20px 10px"><div class="bub">${ic("note")}</div><b>No templates yet</b>A template is a starting point: items, prices, payment terms, notes and terms. Make one here, or open any invoice and press Save as template.</div>`;
    hydrateIcons(ov);
    $$("[data-ed]",ov).forEach(b=>b.onclick=()=>{const t=ts.find(x=>x.id===b.dataset.ed);ov.remove();invTplEdit(t)});
    $$("[data-ar]",ov).forEach(b=>b.onclick=async()=>{const t=ts.find(x=>x.id===b.dataset.ar);const r=await invRpc("inv_tpl_archive",{p_id:t.id,p_archived:!t.archived});
      if(!r.ok)return toast(invErr(r),{bad:1});await invLoad(true);draw(ov);toast(t.archived?`Restored "${t.name}"`:`Archived "${t.name}". Old invoices keep it.`)})};
  openModal(`<h2>Invoice templates</h2><div class="muted" style="margin:4px 0 0;font-size:13.5px">Everyone can start an invoice from these. Only admins change them. Templates are archived, never deleted, so old invoices keep pointing at them.</div>
    <div class="iv-tl"></div><div style="display:flex;gap:10px;justify-content:flex-end"><button class="btn" data-x>Close</button><button class="btn pri" data-new>${ic("plus")}New template</button></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;$("[data-new]",ov).onclick=()=>{close();invTplEdit(null)};draw(ov)});
}
function invTplEdit(t){
  const T=t?JSON.parse(JSON.stringify(t)):{name:"",category:"",summary:"",items:[invBlankItem()],payment_terms:"",notes:"",terms:"",due_days:14,tax_rate:null,source:""};
  if(!T.items||!T.items.length)T.items=[invBlankItem()];
  const f=(k,lb,o={})=>`<div${o.wide?' style="grid-column:1/3"':""}><label class="l" for="it_${k}">${lb}</label>${o.area?`<textarea class="inp" id="it_${k}" rows="${o.rows||3}" maxlength="${o.max}" style="width:100%">${esc(T[k]??"")}</textarea>`:`<input class="inp" id="it_${k}" maxlength="${o.max||80}"${o.im?` inputmode="${o.im}"`:""}${o.ph?` placeholder="${esc(o.ph)}"`:""} value="${esc(T[k]??"")}" style="width:100%">`}</div>`;
  openModal(`<h2>${t&&t.id?"Edit template":"New template"}</h2><div class="muted" style="margin:4px 0 0;font-size:13.5px">Use the exact wording of your agreements for the payment terms and the terms and conditions.</div>
   <div class="fg">${f("name","Template name",{ph:"e.g. Website development"})}${f("category","Service type",{max:60,ph:"e.g. Websites"})}${f("summary","What it's for (optional)",{max:300,wide:1})}
    ${f("due_days","Days to pay",{im:"numeric"})}<div><label class="l" for="it_tax_rate">Tax rate (%)</label><input class="inp" id="it_tax_rate" inputmode="decimal" placeholder="Use the default" value="${esc(T.tax_rate??"")}" style="width:100%"></div>
    ${f("source","Based on (optional)",{max:200,ph:"e.g. the document this came from",wide:1})}</div>
   <label class="l">Items</label><div class="iv-items" id="itItems">${T.items.map((x,k)=>invItemHTML(x,k,"CAD")).join("")}</div><button type="button" class="btn iv-add" data-additem>${ic("plus")}Add item</button>
   <div class="fg">${f("payment_terms","Payment terms",{area:1,max:2000,wide:1,rows:2})}${f("notes","Notes",{area:1,max:4000,wide:1,rows:2})}${f("terms","Terms and conditions",{area:1,max:20000,wide:1,rows:6})}</div>
   <div class="iv-err" id="itE" role="alert"></div>
   <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:6px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>${ic("check")}Save template</button></div>`,(ov,close)=>{
    const box=$("#itItems",ov);
    const read=()=>{$$(".iv-it",box).forEach(el=>{const it=T.items[+el.dataset.k];$$("[data-f]",el).forEach(i=>{it[i.dataset.f]=i.type==="checkbox"?i.checked:i.value})})};
    const amts=()=>{read();invCalc(T.items,"none",0,0).lines.forEach((l,k)=>{const b=$(`[data-amt="${k}"]`,box);if(b)b.textContent=invMoney(l)})};
    const redraw=n=>{read();box.innerHTML=T.items.map((x,k)=>invItemHTML(x,k,"CAD",k===n)).join("");hydrateIcons(box);amts()};
    box.addEventListener("input",amts);
    box.addEventListener("click",e=>{const b=e.target.closest("[data-rm]");if(!b)return;read();T.items.splice(+b.dataset.rm,1);if(!T.items.length)T.items.push(invBlankItem());redraw()});
    $("[data-additem]",ov).onclick=()=>{read();T.items.push(invBlankItem());redraw(T.items.length-1)};
    $("[data-x]",ov).onclick=close;amts();
    $("[data-ok]",ov).onclick=async()=>{read();const e=$("#itE",ov),v=k=>$("#it_"+k,ov).value;e.textContent="";
      const p={...T,name:v("name").trim(),category:v("category").trim(),summary:v("summary").trim(),source:v("source").trim(),payment_terms:v("payment_terms"),notes:v("notes"),terms:v("terms"),
        due_days:v("due_days").trim()||"14",tax_rate:v("tax_rate").trim(),items:T.items.map(x=>({description:String(x.description||"").trim(),details:String(x.details||"").trim(),qty:String(x.qty===""?1:x.qty).replace(/[,\s]/g,""),unit_price:String(x.unit_price===""?0:x.unit_price).replace(/[$,\s]/g,""),taxable:x.taxable!==false}))};
      ["archived","updated_at","version"].forEach(k=>delete p[k]);
      if(!p.name)return e.textContent="Give the template a name.";
      const b=$("[data-ok]",ov);invBusy(b,true,"Saving...");const r=await invRpc("inv_tpl_save",{p});invBusy(b,false);
      if(!r.ok)return e.textContent=invErr(r);close();await invLoad(true);toast(`Template "${p.name}" saved`);if(INV.view==="list")renderInvoices(true)}});
}

/* ---------- PDF ----------
   A small PDF writer: Helvetica (built into every PDF reader), lines, boxes, the vector Leafline leaf, page numbers and
   clickable links. Text is real text. Characters outside the Windows-1252 set fall back to their plain letter. */
const PDF_W={R:[278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584],
  B:[278,333,474,556,556,889,722,238,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,333,333,584,584,584,611,975,722,722,722,722,667,611,778,722,278,556,722,611,833,722,778,667,778,722,667,611,722,667,944,667,667,611,333,278,333,584,556,333,556,611,556,611,556,333,611,611,278,278,556,278,889,611,611,611,611,389,556,333,611,556,778,556,556,500,389,280,389,584]};
const PDF_X={"€":[128,556],"…":[133,1000],"‘":[145,222,278],"’":[146,222,278],"“":[147,333,500],"”":[148,333,500],"•":[149,350],"–":[150,556],"—":[151,1000],"™":[153,1000],"−":[45,584]};
function pdfGlyph(ch,bold){
  const c=ch.codePointAt(0);if(c>=32&&c<=126)return [c,(bold?PDF_W.B:PDF_W.R)[c-32]];
  const x=PDF_X[ch];if(x)return [x[0],bold&&x[2]?x[2]:x[1]];
  if(c===160)return [32,278];if(c===9)return [32,278];
  if(c>160&&c<=255){const base=ch.normalize("NFD")[0],bc=base.codePointAt(0);const w=bc>=32&&bc<=126?(bold?PDF_W.B:PDF_W.R)[bc-32]:({169:737,174:737,176:400,215:584,247:584,171:556,187:556,183:278}[c]||556);return [c,w]}
  const base=ch.normalize("NFD")[0],bc=base.codePointAt(0);if(bc>=32&&bc<=126)return [bc,(bold?PDF_W.B:PDF_W.R)[bc-32]];return [63,bold?611:556];
}
function pdfStr(s,bold){let out="",w=0;for(const ch of String(s==null?"":s).replace(/\r/g,"")){if(ch==="\n")continue;const [c,cw]=pdfGlyph(ch,bold);w+=cw;
  out+=c===40||c===41||c===92?"\\"+String.fromCharCode(c):c<32||c>126?"\\"+c.toString(8).padStart(3,"0"):String.fromCharCode(c)}return {s:out,w}}
const pdfWidth=(s,bold,size)=>pdfStr(s,bold).w*size/1000;
function pdfWrap(text,bold,size,maxW){
  if(!String(text==null?"":text).trim())return [];
  const out=[];for(const para of String(text==null?"":text).replace(/\r/g,"").split("\n")){
    if(!para.trim()){out.push("");continue}
    let line="";for(const word of para.split(/(\s+)/)){if(!word)continue;
      const tryL=line+word;if(pdfWidth(tryL.trimEnd(),bold,size)<=maxW){line=tryL;continue}
      if(line.trim())out.push(line.trimEnd());line=word.trimStart();
      while(pdfWidth(line,bold,size)>maxW){let k=line.length;while(k>1&&pdfWidth(line.slice(0,k),bold,size)>maxW)k--;out.push(line.slice(0,k));line=line.slice(k)}}
    out.push(line.trimEnd())}
  return out;
}
const pdfRGB=h=>{const n=parseInt(h.slice(1),16);return [((n>>16)&255)/255,((n>>8)&255)/255,(n&255)/255].map(v=>+v.toFixed(3)).join(" ")};
const pdfN=v=>+(+v).toFixed(2);
function pdfDoc(){
  const W=612,H=792,pages=[];let cur=null;
  const D={W,H,
    page(){cur={ops:[],links:[]};pages.push(cur);return D},
    text(x,y,s,o={}){const size=o.size||10,bold=!!o.bold,{s:enc,w}=pdfStr(s,bold),tw=w*size/1000;let X=x;if(o.align==="right")X=x-tw;else if(o.align==="center")X=x-tw/2;
      cur.ops.push(`BT /${bold?"F2":"F1"} ${size} Tf ${pdfRGB(o.color||"#16231B")} rg ${pdfN(X)} ${pdfN(H-y)} Td (${enc}) Tj ET`);return tw},
    rect(x,y,w,h,o={}){const r=o.r||0,X=x,Y=H-y-h;let p;
      if(r){const k=.5523*r;p=`${pdfN(X+r)} ${pdfN(Y)} m ${pdfN(X+w-r)} ${pdfN(Y)} l ${pdfN(X+w-r+k)} ${pdfN(Y)} ${pdfN(X+w)} ${pdfN(Y+r-k)} ${pdfN(X+w)} ${pdfN(Y+r)} c ${pdfN(X+w)} ${pdfN(Y+h-r)} l ${pdfN(X+w)} ${pdfN(Y+h-r+k)} ${pdfN(X+w-r+k)} ${pdfN(Y+h)} ${pdfN(X+w-r)} ${pdfN(Y+h)} c ${pdfN(X+r)} ${pdfN(Y+h)} l ${pdfN(X+r-k)} ${pdfN(Y+h)} ${pdfN(X)} ${pdfN(Y+h-r+k)} ${pdfN(X)} ${pdfN(Y+h-r)} c ${pdfN(X)} ${pdfN(Y+r)} l ${pdfN(X)} ${pdfN(Y+r-k)} ${pdfN(X+r-k)} ${pdfN(Y)} ${pdfN(X+r)} ${pdfN(Y)} c h`}
      else p=`${pdfN(X)} ${pdfN(Y)} ${pdfN(w)} ${pdfN(h)} re`;
      cur.ops.push(`q ${o.fill?pdfRGB(o.fill)+" rg ":""}${o.stroke?pdfRGB(o.stroke)+" RG "+(o.lw||.8)+" w ":""}${p} ${o.fill&&o.stroke?"B":o.fill?"f":"S"} Q`)},
    line(x1,y1,x2,y2,o={}){cur.ops.push(`q ${pdfRGB(o.color||"#DCE6E0")} RG ${o.lw||.7} w ${pdfN(x1)} ${pdfN(H-y1)} m ${pdfN(x2)} ${pdfN(H-y2)} l S Q`)},
    link(x,y,w,h,uri){cur.links.push([pdfN(x),pdfN(H-y-h),pdfN(x+w),pdfN(H-y),uri])},
    leaf(x,y,size){const s=size/64;const P=pdfPath("M51 9C30 9 13 20 13 39c0 6 2 11 5 15 2-12 9-22 21-29-9 8-15 18-17 30 4 2 8 3 12 3 19 0 26-19 26-37 0-5-1-9-9-12z"),V=pdfPath("M22 55c3-13 10-23 21-30");
      cur.ops.push(`q ${pdfN(s)} 0 0 ${pdfN(-s)} ${pdfN(x)} ${pdfN(H-y)} cm ${P} W n /Sh1 sh Q`);
      cur.ops.push(`q ${pdfN(s)} 0 0 ${pdfN(-s)} ${pdfN(x)} ${pdfN(H-y)} cm 0.016 0.129 0.059 RG 2.2 w 1 J ${V} S Q`)},
    count:()=>pages.length,
    onPage(k){cur=pages[k];return D},
    bytes(title){
      const objs=[];const add=s=>{objs.push(s);return objs.length};
      const cat=add(""),pagesId=add(""),f1=add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"),f2=add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");
      const sh=add("<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [8 8 56 58] /Function << /FunctionType 2 /Domain [0 1] /C0 [0.722 0.969 0.831] /C1 [0.122 0.62 0.357] /N 1 >> /Extend [true true] >>");
      const kids=[];
      for(const p of pages){const body=p.ops.join("\n"),c=add(`<< /Length ${body.length} >>\nstream\n${body}\nendstream`);
        const an=p.links.map(([a,b,c2,d,u])=>add(`<< /Type /Annot /Subtype /Link /Rect [${a} ${b} ${c2} ${d}] /Border [0 0 0] /A << /S /URI /URI (${pdfStr(u).s}) >> >>`));
        kids.push(add(`<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 ${W} ${H}] /Resources << /Font << /F1 ${f1} 0 R /F2 ${f2} 0 R >> /Shading << /Sh1 ${sh} 0 R >> >> /Contents ${c} 0 R${an.length?` /Annots [${an.map(n=>n+" 0 R").join(" ")}]`:""} >>`))}
      objs[cat-1]=`<< /Type /Catalog /Pages ${pagesId} 0 R >>`;objs[pagesId-1]=`<< /Type /Pages /Kids [${kids.map(k=>k+" 0 R").join(" ")}] /Count ${kids.length} >>`;
      const info=add(`<< /Title (${pdfStr(title||"Invoice").s}) /Producer (Leafline) /Creator (Leafline) /CreationDate (D:${new Date().toISOString().replace(/[-:T]/g,"").slice(0,14)}) >>`);
      let out="%PDF-1.4\n%âãÏÓ\n";const offs=[];
      objs.forEach((o,k)=>{offs.push(out.length);out+=`${k+1} 0 obj\n${o}\nendobj\n`});
      const xref=out.length;out+=`xref\n0 ${objs.length+1}\n0000000000 65535 f \n`+offs.map(o=>String(o).padStart(10,"0")+" 00000 n \n").join("");
      out+=`trailer\n<< /Size ${objs.length+1} /Root ${cat} 0 R /Info ${info} 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
      const b=new Uint8Array(out.length);for(let k=0;k<out.length;k++)b[k]=out.charCodeAt(k)&255;return b}};
  return D.page();
}
/* SVG path (M, L, C, Z, absolute or relative) to PDF path operators */
function pdfPath(d){const t=d.match(/[MmLlCcZz]|-?\d*\.?\d+(?:e-?\d+)?/g)||[];let i=0,cmd="",x=0,y=0,sx=0,sy=0;const out=[],n=()=>+t[i++];
  while(i<t.length){if(/[a-z]/i.test(t[i]))cmd=t[i++];
    if(cmd==="M"||cmd==="m"){let a=n(),b=n();if(cmd==="m"){a+=x;b+=y}x=a;y=b;sx=x;sy=y;out.push(`${x} ${y} m`);cmd=cmd==="m"?"l":"L"}
    else if(cmd==="L"||cmd==="l"){let a=n(),b=n();if(cmd==="l"){a+=x;b+=y}x=a;y=b;out.push(`${x} ${y} l`)}
    else if(cmd==="C"||cmd==="c"){const p=[n(),n(),n(),n(),n(),n()];if(cmd==="c")for(let k=0;k<6;k++)p[k]+=k%2?y:x;out.push(`${p.join(" ")} c`);x=p[4];y=p[5]}
    else if(cmd==="Z"||cmd==="z"){out.push("h");x=sx;y=sy}else break}
  return out.join(" ")}
/* The invoice itself. Letter size, 48pt margins. */
function invPdf(inv,st){
  st=st||{};const D=pdfDoc(),L=48,R=564,CW=R-L,BOT=730,cur=inv.currency||"CAD",G="#1F7A4A",DK="#10261A",MU="#5F7268",LN="#DCE6E0",SOFT="#EEF7F1";
  const m=v=>invMoney(v,"CAD");let y=0;   /* plain $ amounts; the currency is written out next to the totals */
  const status=inv.status==="paid"?["PAID","#1F9E5B"]:inv.status==="void"?["VOID","#C0392B"]:inv.status==="draft"?["DRAFT","#7A8A80"]:inv.overdue?["OVERDUE","#C0392B"]:null;
  /* header */
  D.leaf(L,40,40);
  D.text(L+50,60,st.company_name||"Leafline Web Services",{size:16,bold:1,color:DK});
  let hy=74;const co=[...pdfWrap(st.company_address,0,8.5,230),[st.company_phone,st.company_email].filter(Boolean).join("  •  "),st.company_website].filter(Boolean);
  co.forEach(l=>{D.text(L+50,hy,l,{size:8.5,color:MU});hy+=11});
  D.text(R,62,"INVOICE",{size:26,bold:1,color:G,align:"right"});
  const meta=[["Invoice number",inv.number],["Invoice date",invLong(inv.issue_date)],["Due date",invLong(inv.due_date)]];if(st.tax_number)meta.push([(inv.tax_label||"Tax")+" number",st.tax_number]);
  let my=80;meta.forEach(([k,v])=>{D.text(R-150,my,k,{size:8.5,color:MU});D.text(R,my,v,{size:9,bold:1,color:DK,align:"right"});my+=13});
  if(status){const w=pdfWidth(status[0],1,9)+20;D.rect(R-w,my-2,w,18,{r:9,fill:status[1]});D.text(R-w/2,my+10.5,status[0],{size:9,bold:1,color:"#FFFFFF",align:"center"});my+=22}
  y=Math.max(hy,my)+14;D.line(L,y,R,y,{color:LN,lw:1});y+=22;
  /* bill to + amount due */
  const by0=y;D.text(L,y,"BILL TO",{size:7.5,bold:1,color:MU});y+=14;
  D.text(L,y,inv.client_name,{size:11.5,bold:1,color:DK});y+=14;
  const cl=[inv.client_contact,...pdfWrap(inv.client_address,0,9,260),inv.client_email,inv.client_phone].filter(Boolean);cl.forEach(l=>{D.text(L,y,l,{size:9,color:"#33453A"});y+=12});
  const bw=200,bx=R-bw,bh=74;D.rect(bx,by0-12,bw,bh,{r:12,fill:SOFT});
  const paid=inv.status==="paid",due=paid?0:inv.status==="void"?0:+inv.total;
  D.text(bx+16,by0+6,paid?"Paid in full":inv.status==="void"?"Voided":"Amount due",{size:8.5,bold:1,color:MU});
  D.text(bx+16,by0+32,m(paid?inv.paid_amount:inv.total)+" "+cur,{size:20,bold:1,color:DK});
  D.text(bx+16,by0+50,paid?`Received ${invLong(inv.paid_on)}`:inv.status==="void"?"This invoice was cancelled":`Due ${invLong(inv.due_date)}`,{size:8.5,color:MU});
  y=Math.max(y,by0+bh)+20;
  /* items */
  const cQ=380,cP=470,cA=R-10,dW=cQ-L-60;
  const head=()=>{D.rect(L,y,CW,22,{r:6,fill:DK});const ty=y+14.5;D.text(L+10,ty,"DESCRIPTION",{size:7.5,bold:1,color:"#FFFFFF"});D.text(cQ,ty,"QTY",{size:7.5,bold:1,color:"#FFFFFF",align:"right"});
    D.text(cP,ty,"PRICE",{size:7.5,bold:1,color:"#FFFFFF",align:"right"});D.text(cA,ty,"AMOUNT",{size:7.5,bold:1,color:"#FFFFFF",align:"right"});y+=30};
  const newPage=()=>{D.page();y=56};
  head();
  (inv.items||[]).forEach((it,k)=>{
    const dl=pdfWrap(it.description,1,9.5,dW),xl=[...pdfWrap(it.details,0,8.5,dW),...(+inv.tax_rate&&it.taxable===false?[`No ${inv.tax_label||"tax"} on this item`]:[])];
    const h=dl.length*12+xl.length*11+10;
    if(y+h>BOT){newPage();head()}
    const amt=Math.round(invFix(it.qty,2)*invFix(it.unit_price,2)/100)/100,ry=y+2;
    dl.forEach((l,j)=>D.text(L+10,ry+j*12,l,{size:9.5,bold:1,color:DK}));
    xl.forEach((l,j)=>D.text(L+10,ry+dl.length*12+j*11,l,{size:8.5,color:MU}));
    D.text(cQ,ry,invRate(it.qty),{size:9.5,color:DK,align:"right"});D.text(cP,ry,m(it.unit_price),{size:9.5,color:DK,align:"right"});D.text(cA,ry,m(amt),{size:9.5,bold:1,color:DK,align:"right"});
    y+=h;if(k<(inv.items||[]).length-1)D.line(L+10,y-6,R-10,y-6,{color:LN})});
  /* totals */
  const rows=[["Subtotal",m(inv.subtotal)]];
  if(+inv.discount_total)rows.push([`Discount${inv.discount_kind==="percent"?" ("+invRate(inv.discount_value)+"%)":""}`,"−"+m(inv.discount_total)]);
  if(+inv.tax_rate)rows.push([`${inv.tax_label} (${invRate(inv.tax_rate)}%)`,m(inv.tax_total)]);
  const th=rows.length*16+44+(paid?32:0);if(y+th>BOT)newPage();
  y+=6;D.line(330,y,R,y,{color:LN,lw:1});y+=16;
  rows.forEach(([k,v])=>{D.text(340,y,k,{size:9.5,color:MU});D.text(cA,y,v,{size:9.5,color:DK,align:"right"});y+=16});
  D.rect(330,y-6,R-330,28,{r:8,fill:SOFT});D.text(340,y+12,"Total",{size:11,bold:1,color:DK});D.text(cA,y+12,m(inv.total)+" "+cur,{size:12,bold:1,color:G,align:"right"});y+=34;
  if(paid){D.text(340,y,`Paid ${invLong(inv.paid_on)}`,{size:9.5,color:MU});D.text(cA,y,"−"+m(inv.paid_amount),{size:9.5,color:DK,align:"right"});y+=16;
    D.text(340,y,"Balance due",{size:9.5,bold:1,color:DK});D.text(cA,y,m(Math.max(0,Math.round((+inv.total-(+inv.paid_amount))*100)/100)),{size:9.5,bold:1,color:DK,align:"right"});y+=16}
  y+=14;
  /* how to pay */
  if(st.etransfer_email&&inv.status!=="void"&&!paid){
    const ref=`Invoice ${inv.number}`,note=pdfWrap(st.payment_note,0,8.5,CW-40),rowsN=3+(st.etransfer_name?1:0),bh2=22+18+rowsN*14+note.length*11+(note.length?6:0)+24+20;if(y+bh2>BOT)newPage();
    D.rect(L,y,CW,bh2,{r:12,fill:"#F6FBF8",stroke:"#CFE6D8",lw:.8});
    let py=y+22;D.text(L+20,py,"How to pay: Interac e-Transfer",{size:11,bold:1,color:DK});py+=18;
    const kv=(k,v,b,link)=>{D.text(L+20,py,k,{size:8.5,color:MU});const w=D.text(L+110,py,v,{size:9.5,bold:b,color:link?G:DK});if(link)D.link(L+108,py-10,w+4,14,link);py+=14};
    kv("Send to",st.etransfer_email,1,"mailto:"+st.etransfer_email);if(st.etransfer_name)kv("Payable to",st.etransfer_name,0);kv("Amount",m(inv.total)+" "+cur,1);kv("Message",ref,1);
    note.forEach(l=>{D.text(L+20,py,l,{size:8.5,color:"#33453A"});py+=11});
    const btn="Email us when you've paid",bw2=pdfWidth(btn,1,9)+28,byy=py-6+(note.length?6:0);
    D.rect(L+20,byy,bw2,24,{r:12,fill:G});D.text(L+20+bw2/2,byy+15.5,btn,{size:9,bold:1,color:"#FFFFFF",align:"center"});
    const sub=`${ref}: e-Transfer sent`,body=`Hi,\n\nI sent an Interac e-Transfer of ${m(inv.total)} to ${st.etransfer_email} for ${ref}.\n\nThanks,\n${inv.client_contact||inv.client_name}`;
    D.link(L+20,byy,bw2,24,`mailto:${st.etransfer_email}?subject=${encodeURIComponent(sub)}&body=${encodeURIComponent(body)}`);
    D.text(L+30+bw2,byy+15.5,"Send the e-Transfer from your bank's app, then let us know.",{size:8,color:MU});
    y+=bh2+20}
  /* payment terms, notes, terms */
  const section=(title,text,size)=>{if(!String(text||"").trim())return;const lines=pdfWrap(text,0,size,CW);if(y+30>BOT)newPage();
    D.text(L,y,title.toUpperCase(),{size:8,bold:1,color:G});y+=14;
    lines.forEach(l=>{if(y>BOT){newPage()}if(l)D.text(L,y,l,{size,color:"#33453A"});y+=size+3.5});y+=12};
  section("Payment terms",inv.payment_terms,9);section("Notes",inv.notes,9);section("Terms and conditions",inv.terms,8);
  /* footer on every page */
  const n=D.count();for(let k=0;k<n;k++){D.onPage(k);D.line(L,756,R,756,{color:LN});
    const ft=[st.footer,st.company_website].filter(Boolean).join("  •  ");if(ft)D.text(L,770,ft,{size:7.5,color:MU});
    D.text(R,770,`${inv.number}  •  Page ${k+1} of ${n}`,{size:7.5,color:MU,align:"right"})}
  return D.bytes(`Invoice ${inv.number} - ${inv.client_name}`);
}
async function invDownload(inv,btn){
  invBusy(btn,true,"Making PDF...");
  try{
    if(!inv.items){const g=await invRpc("inv_get",{p_id:inv.id});if(!g.ok)throw new Error(invErr(g));inv=g.data}
    await new Promise(r=>setTimeout(r,30));
    const bytes=invPdf(inv,INV.settings),name=`${inv.number} ${inv.client_name}`.replace(/[^\w.\- ]+/g,"").replace(/\s+/g," ").trim().slice(0,80)+".pdf";
    if(window.leafline&&window.leafline.savePdf){const r=await window.leafline.savePdf(name,bytes);
      if(r&&r.ok){toast("PDF saved");logNote(`Saved the PDF of ${inv.number}`)}else if(r&&!r.canceled)toast("Couldn't save the PDF: "+(r.error||""),{bad:1});return}
    const file=new File([bytes],name,{type:"application/pdf"});
    if(isPhone()&&navigator.canShare&&navigator.canShare({files:[file]})){try{await navigator.share({files:[file],title:name});toast("PDF ready");return}catch(e){if(e&&e.name==="AbortError")return}}
    const a=document.createElement("a");a.href=URL.createObjectURL(file);a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},4000);
    toast("PDF downloaded");logNote(`Downloaded the PDF of ${inv.number}`);
  }catch(e){toast("Couldn't make the PDF: "+e.message,{bad:1})}
  finally{invBusy(btn,false)}
}
/* from a deal (Profits): a new invoice with the client and the deal's payments filled in */
function invFromDeal(d){
  const items=[];if(+d.upfront>0)items.push({description:"Upfront payment",details:d.notes||"",qty:1,unit_price:(+d.upfront).toFixed(2),taxable:true});
  if(+d.monthly>0)items.push({description:"Monthly payment",details:d.months?`${d.months} months`:"Billed every month",qty:1,unit_price:(+d.monthly).toFixed(2),taxable:true});
  invLoad(false).then(()=>invStart({client_name:d.client||"",items:items.length?items:[invBlankItem()],lead_id:d.lead_id||null,deal_id:/^[0-9a-f-]{36}$/.test(String(d.remote_id||d.uuid||""))?(d.remote_id||d.uuid):null}));
}
'''


def inject(ui):
    """Adds Invoices to the shared page."""
    css_at, js_at = "</style>\n</head>", "</script>\n</body>"
    assert ui.count(css_at) == 1 and ui.count(js_at) == 1
    return ui.replace(css_at, INV_CSS + css_at, 1).replace(js_at, INV_JS + js_at, 1)
