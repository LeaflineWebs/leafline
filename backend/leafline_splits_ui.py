"""Profit splits (11.18): when a payment is confirmed, its money can be split between teammates by percent
(e.g. Omar 60%, Jay 40%). The split is saved for that payment and as the deal's default, so later payments follow it
until it is changed. The leaderboard, Revenue Champion and Deal Closer count each person's share.

Rules live in the database (16th update, supabase/migrations/20261113000016_deal_splits.sql): only an admin or the
person the deal is credited to can set a split, the percents must add up to exactly 100, active teammates only.
"""

SPLIT_CSS = r'''
/* ---------- profit splits (11.18) ---------- */
.spl-chip{display:inline-flex;align-items:center;gap:6px;height:30px;max-width:230px;padding:0 11px;border-radius:15px;font-size:12px;font-weight:700;
  color:var(--text2);background:rgba(255,255,255,.05);border:1px solid var(--line2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:none;
  transition:border-color var(--d-hover) var(--e-out),color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.spl-chip .ic{width:14px;height:14px;flex:none}.spl-chip span{overflow:hidden;text-overflow:ellipsis}
.spl-chip:hover{border-color:var(--accent-line);color:var(--text);transform:translateY(-1px)}
.spl-chip.multi{color:var(--accent-hi);border-color:var(--accent-line);background:var(--accent-soft)}
/* payment rows with a split: the name keeps its room; the chip drops to its own line when space runs out */
.prow:has(.spl-chip){flex-wrap:wrap;row-gap:8px}.prow:has(.spl-chip)>div:first-child{min-width:150px !important}
.prow .spl-chip{order:9;margin-left:auto}
.spl-head{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;margin-top:6px;color:var(--muted);font-size:13.5px}
.spl-head b{color:var(--text);font-size:15px}
.spl-sec{margin-top:16px;padding:14px;border-radius:18px;background:rgba(0,0,0,.16);border:1px solid var(--line)}
.spl-sec h3{font-size:14.5px}.spl-sec .note{margin-top:3px}
.spl-rows{display:grid;gap:8px;margin-top:12px}
.spl-row{display:grid;grid-template-columns:minmax(0,1fr) 92px 92px 34px;gap:8px;align-items:center}
.spl-row select,.spl-row input{height:40px;min-width:0}
.spl-row .spl-pct{position:relative}.spl-row .spl-pct input{width:100%;padding-right:26px;text-align:right}
.spl-row .spl-pct:after{content:"%";position:absolute;right:11px;top:50%;transform:translateY(-50%);color:var(--muted);font-weight:700;pointer-events:none}
.spl-amt{text-align:right;font-weight:700;font-variant-numeric:tabular-nums;color:var(--text2);font-size:13px}
.spl-rm{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;color:var(--muted);font-size:18px;line-height:1;background:rgba(255,255,255,.04)}
.spl-rm:hover{color:var(--bad);background:rgba(240,138,138,.12)}.spl-rm[disabled]{opacity:.3;pointer-events:none}
.spl-tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}
.spl-sum{margin-left:auto;font-weight:800;font-size:13px;padding:5px 11px;border-radius:12px;background:rgba(255,255,255,.05)}
.spl-sum.ok{color:var(--ok);background:rgba(91,227,154,.12)}.spl-sum.bad{color:var(--warn);background:rgba(235,193,92,.12)}
.spl-bar{display:flex;height:8px;border-radius:4px;overflow:hidden;margin-top:12px;background:rgba(255,255,255,.06)}
.spl-bar i{display:block;height:100%;transition:width var(--d-card) var(--e-out)}
.spl-ro{display:grid;gap:6px;margin-top:10px}.spl-ro div{display:flex;justify-content:space-between;gap:10px;font-size:13.5px}
.spl-ro b{font-variant-numeric:tabular-nums}
.spl-err{color:var(--bad);font-size:13px;min-height:18px;margin-top:8px}
.spl-deal{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
@media (max-width:560px){.spl-row{grid-template-columns:minmax(0,1fr) 84px 34px}.spl-row .spl-amt{display:none}}
'''

SPLIT_JS = r'''
/* ================= Profit splits (11.18) =================
   A payment's money can be shared between teammates by percent. Saved for that payment and as the deal's
   default (later payments follow it). With no split: 100% to whoever the deal is credited to. */
const SPL_COL=["#4ADE8B","#8FC7F0","#EBC15C","#F0A3C8","#B7A4FF","#EE9A5A","#7FE0D2","#D6E26B"];
function splitIndex(bd){
  bd=bd||B.data;if(!bd)return {};if(bd._spx)return bd._spx;
  const ix={};for(const r of bd.splits||[])(ix[r.deal_id]=ix[r.deal_id]||{})[r.pay_key||""]=r.shares;
  Object.defineProperty(bd,"_spx",{value:ix,enumerable:false,configurable:true});return ix;
}
/* who gets this payment's money: the payment's own split, else the deal's default, else 100% to the deal's owner */
function payShares(bd,dl,key){
  const s=dl&&dl.id?splitIndex(bd)[dl.id]:null,sh=s&&((key&&s[key])||s[""]);
  if(sh&&sh.length)return sh.map(x=>({id:x.id,pct:+x.pct}));
  return dl&&dl.owner_id?[{id:dl.owner_id,pct:100}]:[];
}
const boardDeal=rid=>rid&&B.data?(B.data.deals||[]).find(x=>x.id===rid)||null:null;
const splitName=id=>{const t=teamList().find(x=>x[0]===id);return t?t[1]:"Former teammate"};
const pctTxt=v=>(Math.round(v*100)/100).toString();
function splitText(sh){if(!sh.length)return "Not credited";if(sh.length===1)return splitName(sh[0].id);return sh.map(s=>splitName(s.id).split(" ")[0]+" "+pctTxt(s.pct)+"%").join(" · ")}
/* the chip on a confirmed payment (or a deal) showing who it counts for */
function splitChip(localId,day,kind){
  const d=(S.deals||[]).find(x=>String(x.id)===String(localId)),bd=boardDeal(d&&d.rid);if(!bd)return "";
  const sh=payShares(B.data,bd,day?day+":"+kind:"");
  return `<button class="spl-chip${sh.length>1?" multi":""}" data-split="${esc(localId)}|${esc(day||"")}|${esc(kind||"")}" title="Who gets credit: ${esc(splitText(sh))}. Click to change." aria-label="Credit split: ${esc(splitText(sh))}">${ic("users")}<span>${esc(splitText(sh))}</span></button>`;
}
function splitSig(){return B.data?JSON.stringify([B.data.splits||[],(B.data.deals||[]).map(x=>[x.id,x.owner_id])]):""}
function wireSplitChips(root){$$("[data-split]",root).forEach(b=>b.onclick=e=>{e.stopPropagation();const [id,day,kind]=b.dataset.split.split("|");splitModal(id,day||"",kind||"","edit")})}
/* the pop-up. mode "confirm": confirm the payment (and set the split); "edit": change the split only */
async function splitModal(localId,day,kind,mode){
  await ensureBoard().catch(()=>null);
  const d=(S.deals||[]).find(x=>String(x.id)===String(localId));if(!d)return toast("That deal was not found.",{bad:1});
  const key=day?day+":"+kind:"",amount=!day?0:kind==="upfront"?+d.upfront||0:+d.monthly||0,bd=boardDeal(d.rid);
  const ready=!!(B.data&&B.data.splits_ready!==false),owner=bd&&bd.owner_id,canEdit=!!(bd&&ready&&(isAdmin()||(S.me&&owner===S.me.id)));
  const cur=bd?payShares(B.data,bd,key):[];let rows=cur.length?cur.map(x=>({...x})):[{id:(S.me&&S.me.id)||"",pct:100}];
  const why=!B.data?"The split will show once the team's numbers load. You can confirm the payment now.":
    !ready?"Splitting a payment between teammates needs the 16th database update. Ask an admin to run it (see SETUP_SUPABASE.md).":
    !d.rid||!bd?"This deal is still uploading to the shared database. Once it says Synced, you can split it.":
    !canEdit?`Only an admin or ${esc(owner?splitName(owner):"the person this deal is credited to")} can change who gets credit.`:"";
  const KIND={upfront:"Upfront",monthly:"Monthly"};
  const title=mode==="confirm"?"Confirm payment":day?"Who gets credit for this payment":"Who gets credit for this deal";
  openModal(`<h2>${title}</h2>
   <div class="spl-head"><b>${esc(d.client)}</b>${day?`<span>${esc(dayFmt(day))} · ${KIND[kind]||kind}</span><span>${usd(amount)}</span>`:`<span>Every payment of this deal follows this split unless one is changed on its own.</span>`}</div>
   ${mode==="confirm"?`<p class="muted" style="margin:10px 0 0;font-size:13px;line-height:1.5">Confirm once the money is really in. It then counts as made, on Profits and the Dashboard.</p>`:""}
   <div class="spl-sec">${mode==="confirm"?"<h3>Who gets credit</h3>":""}
    <div class="note">${canEdit?"Split it between teammates by percent. It counts for each of them on the leaderboard."+(day?" Later payments of this deal use the same split until it's changed.":""):why}</div>
    <div id="splBody"></div><div class="spl-err" id="splErr" role="alert"></div></div>
   <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap"><span style="flex:1"></span><button class="btn" data-x>Cancel</button><button class="btn pri" data-splok>${mode==="confirm"?ic("check")+"Confirm payment":"Save split"}</button></div>`,
  (ov,close)=>{
    const body=$("#splBody",ov),err=$("#splErr",ov),go=$("[data-splok]",ov),team=teamList();
    const sum=()=>Math.round(rows.reduce((a,r)=>a+(+r.pct||0),0)*100)/100;
    const problem=()=>{if(!rows.length)return "Add at least one teammate.";if(rows.some(r=>!r.id))return "Pick a teammate on every line.";
      if(new Set(rows.map(r=>r.id)).size!==rows.length)return "Each teammate can only be in the split once.";
      if(rows.some(r=>!(+r.pct>0)||+r.pct>100||Math.abs(Math.round(+r.pct*100)-(+r.pct*100))>1e-6))return "Each percent must be more than 0 and at most 100 (up to 2 decimals).";
      const s=sum();return s!==100?`The percents add up to ${pctTxt(s)}%. They need to add up to 100%.`:""};
    const paint=()=>{
      if(!canEdit){body.innerHTML=cur.length?`<div class="spl-ro">${cur.map(s=>`<div><span>${esc(splitName(s.id))}</span><b>${pctTxt(s.pct)}%${amount?" · "+usd(amount*s.pct/100):""}</b></div>`).join("")}</div>`:"";return}
      const s=sum(),ok=s===100;
      body.innerHTML=`<div class="spl-rows">${rows.map((r,i)=>`<div class="spl-row" data-i="${i}">
          <select class="inp" data-who aria-label="Teammate ${i+1}"><option value="">Pick a teammate</option>${team.map(([id,n])=>`<option value="${esc(id)}"${id===r.id?" selected":""}>${esc(n)}</option>`).join("")}</select>
          <div class="spl-pct"><input class="inp" data-pct inputmode="decimal" value="${esc(r.pct===""?"":pctTxt(+r.pct||0))}" aria-label="Percent for teammate ${i+1}"></div>
          <div class="spl-amt">${amount?usd(Math.round(amount*(+r.pct||0))/100):""}</div>
          <button type="button" class="spl-rm" data-rm aria-label="Remove this teammate"${rows.length<2?" disabled":""}>×</button></div>`).join("")}</div>
        <div class="spl-bar" aria-hidden="true">${rows.map((r,i)=>`<i style="width:${Math.max(0,Math.min(100,+r.pct||0))}%;background:${SPL_COL[i%SPL_COL.length]}"></i>`).join("")}</div>
        <div class="spl-tools"><button type="button" class="btn sm" data-add${rows.length>=8?" disabled":""}>${ic("plus")}Add teammate</button><button type="button" class="btn sm" data-even${rows.length<2?" disabled":""}>Split evenly</button>
          <span class="spl-sum ${ok?"ok":"bad"}">${ok?"100% ✓":pctTxt(s)+"% of 100%"}</span></div>`;
      hydrateIcons(body);
      $$("[data-who]",body).forEach(sel=>sel.onchange=()=>{rows[+sel.closest(".spl-row").dataset.i].id=sel.value;err.textContent="";paint()});
      $$("[data-pct]",body).forEach(inp=>{inp.oninput=()=>{const i=+inp.closest(".spl-row").dataset.i;rows[i].pct=inp.value.trim()===""?"":parseFloat(inp.value.replace(",","."));err.textContent="";
          const row=inp.closest(".spl-row");row.querySelector(".spl-amt").textContent=amount?usd(Math.round(amount*(+rows[i].pct||0))/100):"";
          const t=sum(),b=$(".spl-sum",body);b.className="spl-sum "+(t===100?"ok":"bad");b.textContent=t===100?"100% ✓":pctTxt(t)+"% of 100%";
          $$(".spl-bar i",body).forEach((x,j)=>x.style.width=Math.max(0,Math.min(100,+rows[j].pct||0))+"%")}});
      $$("[data-rm]",body).forEach(b=>b.onclick=()=>{rows.splice(+b.closest(".spl-row").dataset.i,1);paint()});
      const add=$("[data-add]",body);if(add)add.onclick=()=>{const left=Math.max(0,Math.round((100-sum())*100)/100);const free=team.find(([id])=>!rows.some(r=>r.id===id));
        rows.push({id:free?free[0]:"",pct:left||""});paint();const ins=$$("[data-who]",body);ins[ins.length-1].focus()};
      const ev=$("[data-even]",body);if(ev)ev.onclick=()=>{const n=rows.length,each=Math.floor(10000/n)/100;rows.forEach((r,i)=>r.pct=i===n-1?Math.round((100-each*(n-1))*100)/100:each);paint()};
    };
    paint();
    $("[data-x]",ov).onclick=close;
    if(mode!=="confirm"&&!canEdit){go.style.display="none";$("[data-x]",ov).textContent="Close";return}   // read-only: nothing to save
    go.onclick=async()=>{
      const changed=canEdit&&JSON.stringify(rows.map(r=>[r.id,+r.pct]))!==JSON.stringify(cur.map(r=>[r.id,+r.pct]));
      if(canEdit){const p=problem();if(p){err.textContent=p;return}}
      go.disabled=true;
      try{
        if(changed){
          const r=await api("sb_rpc","deal_split_set",{p_deal:d.rid,p_key:key,p_shares:rows.map(r=>({id:r.id,pct:+r.pct})),p_default:true});
          if(!r||!r.ok){go.disabled=false;err.textContent=(r&&r.missing)?"Splitting needs the 16th database update. Ask an admin to run it.":((r&&r.error)||"Couldn't save the split.");return}
          logNote("Split "+d.client+(day?" ("+dayFmt(day)+")":"")+": "+splitText(rows));
        }
        if(mode==="confirm"){
          const r=await api("confirm_payment",+localId,day,kind,true);
          if(!r||!r.ok){go.disabled=false;err.textContent=(r&&r.error)||"Couldn't confirm the payment.";return}
          logNote("Confirmed a "+kind+" payment ("+dayFmt(day)+")");
        }
        close();
        toast(mode==="confirm"?(rows.length>1&&canEdit?"Payment confirmed and split: "+splitText(rows):"Payment confirmed. It now counts as made."):changed?"Split saved: "+splitText(rows):"Nothing changed");
        if(changed){B.at=0;await ensureBoard(true).catch(()=>null);computeAndPaintBadges()}
        reload();
      }catch(x){go.disabled=false;err.textContent="Couldn't save: "+x.message}
    };
  });
}
function computeAndPaintBadges(){if(B.data){B.badges=computeBadges(B.data);paintBadges()}if(S.page==="board"&&typeof drawRanks==="function")drawRanks(false)}
/* the deal pop-up: who the deal's payments count for */
function dealSplitHTML(d){return `<div style="grid-column:1/3"><div class="fact span"><div class="k">Profit split</div><div class="v spl-deal" id="dSplit">${splitChip(d.id,"","")||'<span class="muted">Loading...</span>'}</div>
  <div class="note" style="margin-top:6px">Who each payment of this deal counts for. You can also split a payment when you confirm it.</div></div></div>`}
function wireDealSplit(ov,d){const el=$("#dSplit",ov);if(!el)return;const fill=()=>{const h=splitChip(d.id,"","");el.innerHTML=h||'<span class="muted">Available once this deal is synced.</span>';hydrateIcons(el);wireSplitChips(el)};
  fill();if(!B.data)ensureBoard().then(fill).catch(()=>{})}
'''


def inject(ui):
    """Adds profit splits to the shared page."""
    css_at, js_at = "</style>\n</head>", "</script>\n</body>"
    assert ui.count(css_at) == 1 and ui.count(js_at) == 1
    return ui.replace(css_at, SPLIT_CSS + css_at, 1).replace(js_at, SPLIT_JS + js_at, 1)
