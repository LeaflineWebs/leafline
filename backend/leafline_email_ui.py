"""Email writer (11.20): write a ready-to-send email for one business from a quick prompt.

Where: Find Leads (the "Email" button in a business's details), Called Leads (the "Write email" button in the pop-up), and
right after a call: marking a result (No answer / Interested / Meeting) or logging a call shows a small "Email <business>?"
card. From a call it starts writing straight away, using the call result and the call notes.

How: the page sends the business's details, the prompt and the tone to the Supabase Edge Function "email-draft" with the
person's OWN sign-in. The function holds the AI key (a Supabase secret, never in the app), checks the person is an active
teammate under today's limit (18th database update), and asks Claude for a subject and a body. The signature is added
here, from Settings you can edit in the pop-up. If the email writer isn't set up yet (or you're offline), a plain template
is filled in instead and the pop-up says so. Sending: "Open in email app" (mailto), "Gmail", or Copy.
"""

EMAIL_CSS = r'''
/* ---------- email writer (11.20) ---------- */
.em-dlg h2{display:flex;align-items:center;gap:10px}.em-dlg h2 .ic{width:20px;height:20px;color:var(--accent)}
.em-dlg .em-sub{margin:2px 0 14px;font-size:13px;color:var(--muted)}
.em-dlg .em-f{margin-top:12px}.em-dlg .em-f .inp{width:100%}
.em-dlg textarea.inp{resize:vertical;line-height:1.5;font:inherit;font-size:14px}
.em-picks{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.em-picks .chip{height:30px;padding:0 12px;font-size:12.5px;cursor:pointer}
.em-picks .chip:hover{color:var(--text);border-color:var(--accent-line)}
.em-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:14px}.em-row .em-sp{flex:1}
.dlg.em-wide{width:min(680px,94vw)}
.em-out{margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}
.em-out[hidden]{display:none}
.em-msg{font-size:12.5px;line-height:1.5;padding:9px 12px;border-radius:14px;background:rgba(var(--accent-rgb),.10);border:1px solid var(--accent-line);color:var(--text2);margin-bottom:10px}
.em-msg.warn{background:rgba(255,214,10,.08);border-color:rgba(255,214,10,.35)}
.em-msg.bad{background:rgba(255,69,58,.10);border-color:rgba(255,69,58,.4)}
.em-msg small{display:block;opacity:.75;margin-top:2px}
.em-sig{margin-top:10px}.em-sig summary{cursor:pointer;font-size:12.5px;font-weight:600;color:var(--muted);padding:4px}
.em-sig[open] summary{margin-bottom:6px}
.em-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;align-items:center}.em-acts .em-sp{flex:1}
.em-busy{position:relative;color:transparent !important}
.em-busy::after{content:"Writing...";position:absolute;inset:0;display:grid;place-items:center;color:var(--accent-text)}
.em-wait{display:none;align-items:center;gap:10px;font-size:13px;color:var(--muted);margin-top:14px}
.em-wait.on{display:flex}.em-wait i{width:16px;height:16px;border-radius:50%;border:2px solid var(--accent-line);border-top-color:var(--accent);animation:emspin .8s linear infinite}
@keyframes emspin{to{transform:rotate(360deg)}}
.em-nudge{position:fixed;right:30px;bottom:100px;z-index:79;display:flex;align-items:center;gap:10px;max-width:min(420px,calc(100vw - 32px));padding:10px 10px 10px 16px;border-radius:22px;
  background:var(--card2);border:1px solid var(--accent-line);box-shadow:0 18px 40px rgba(0,0,0,.45);font-size:13.5px;font-weight:600;
  transform:translateY(20px) scale(.94);opacity:0;pointer-events:none;transition:transform .5s var(--spring),opacity .25s}
.em-nudge.on{transform:none;opacity:1;pointer-events:auto}
.em-nudge .ic{width:18px;height:18px;color:var(--accent);flex:none}
.em-nudge span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.em-nudge .em-x{width:30px;height:30px;border-radius:15px;display:grid;place-items:center;color:var(--muted);font-size:18px;line-height:1;flex:none}
.em-nudge .em-x:hover{color:var(--text);background:rgba(255,255,255,.06)}
@media (max-width:860px){
  .em-nudge{right:16px;left:16px;max-width:none;bottom:calc(150px + env(safe-area-inset-bottom))}
  .em-acts .btn{flex:1 1 auto}.em-acts .em-sp{display:none}
}
@media (prefers-reduced-motion:reduce){.em-nudge{transition:opacity .2s}.em-wait i{animation:none}}
'''

EMAIL_JS = r'''
/* ---------- email writer (11.20): the AI writes, you check and send ---------- */
const EM={nudgeT:0};
const EM_NEED18="AI emails need the 18th database update. Ask an admin to run RUN_IN_SUPABASE.sql in Supabase.";
const EM_SETUP="The AI email writer isn't set up yet, so this is a plain template and your request wasn't used. (Admins: SETUP_SUPABASE.md > Email writer.)";
/* what happened on the call -> what the email starts from */
const EM_FROM_STATUS={orange:"no_answer",yellow:"interested",green:"meeting"};
const EM_KIND={
  no_answer:["Couldn't reach them","I just tried calling and couldn't reach them. Short intro and ask for a good time to talk."],
  voicemail:["Left a voicemail","I just left them a voicemail. Follow up by email with why I called."],
  interested:["Interested","Thank them for the call and recap what we talked about. Suggest the next step."],
  meeting:["Meeting booked","Thank them for the call and confirm our meeting."],
  follow_up:["Follow up","Follow up on our call and suggest a time to talk again."],
  sale:["New customer","Thank them for choosing us and explain what happens next."]};
const EM_PICKS=[["Introduce us","Introduce us and explain how a better website could bring them more customers."],
  ["Free mock-up","Offer to make them a free mock-up of a new homepage, no strings attached."],
  ["Follow up on our call","Follow up on our call and suggest a time to talk again."],
  ["Sorry I missed you","I tried calling and couldn't reach them. Short intro and ask for a good time to talk."],
  ["Book a meeting","Ask for a 15-minute meeting this week to show them some ideas."],
  ["Send pricing","Say I'll send pricing options and ask what matters most to them."]];
const EM_TONES=[["friendly","Friendly"],["professional","Professional"],["short","Short"]];
const emHas=v=>!!v&&v!==NA&&String(v).trim()!=="";
function emCompany(){const st=(typeof INV!=="undefined"&&INV.settings)||{};
  return {name:st.company_name||"Leafline Web Services",website:st.company_website||"",phone:st.company_phone||"",email:st.company_email||""}}
function emSigDefault(){const me=S.me||{},ex=me.ext||{},co=emCompany();
  return [me.display_name||"",ex.title||"",co.name,co.phone,co.website].map(x=>String(x||"").trim()).filter(Boolean).join("\n")}
function emSig(){const s=getP("emailSig",null);return typeof s==="string"?s:emSigDefault()}
const emFirst=o=>{if(!emHas(o))return "";const w=String(o).trim().split(/\s+/)[0].replace(/[^A-Za-zÀ-ɏ'-]/g,"");return w.length>1?w[0].toUpperCase()+w.slice(1):""};
const emWith=(body,sig)=>sig&&sig.trim()?body.replace(/\s+$/,"")+"\n"+sig.trim():body;
function emMeetTxt(l){const k=String(l.meeting_at||"").replace("T"," ");if(!k)return "";const d=new Date(k.replace(" ","T"));
  return isNaN(d)?k:d.toLocaleString("en-US",{weekday:"long",month:"long",day:"numeric",hour:"numeric",minute:"2-digit"})}
/* the plain template used when the AI isn't available: still a proper, personal email */
function emTemplate(l,kind,tone){
  const me=(S.me&&S.me.display_name)||"",co=emCompany().name,first=emFirst(l.owner),nm=l.name||"your business";
  const kindTxt=String(l.btype||"").toLowerCase(),short=tone==="short",site=emHas(l.website),when=emMeetTxt(l);
  const hi=first?`Hi ${first},`:`Hi ${nm} team,`;
  const open={no_answer:"I tried giving you a call today but couldn't catch you, so I thought I'd send a quick note instead.",
    voicemail:"I just left you a voicemail and wanted to follow up by email so you have my details.",
    interested:"Thanks for taking the time to chat with me today.",
    meeting:`Thanks again for your time today. I'm looking forward to our meeting${when?" on "+when:""}.`,
    follow_up:"I'm following up on our recent call.",
    sale:`Thank you for choosing ${co}. We're excited to get started.`}[kind]||`My name is ${me||"..."} and I'm with ${co}.`;
  const pitch=kind==="sale"||kind==="meeting"?"":site
    ?`We help ${kindTxt||"local"} businesses get more out of their website, with a cleaner design, faster pages and better visibility on Google.`
    :`I noticed ${nm} doesn't have a website yet. We build professional websites for ${kindTxt||"local"} businesses that help new customers find you on Google and get in touch.`;
  const ask=kind==="meeting"?"If anything comes up before then, just reply to this email.":kind==="sale"?"I'll be in touch shortly with the next steps."
    :"Would you be open to a quick 10-minute call this week? Just reply with a time that works for you.";
  const subj=({no_answer:`Sorry I missed you, ${nm}`,voicemail:`Following up on my call, ${nm}`,interested:`Great speaking with you, ${nm}`,
    meeting:`Our meeting${when?" on "+when.split(",")[0]:""}`,follow_up:`Following up, ${nm}`,sale:`Welcome to ${co}, ${nm}`}[kind])||(site?`More customers for ${nm}`:`A website for ${nm}`);
  const paras=[hi,open];if(pitch)paras.push(short?pitch.split(". ")[0].replace(/\.?$/,"."):pitch);paras.push(ask,"Best,");
  return {subject:subj.slice(0,80),body:paras.join("\n\n")};
}
/* the AI: Supabase Edge Function "email-draft", called with this person's own sign-in */
async function emDraft(payload){
  let s;try{s=await api("sb_session")}catch(e){s=null}
  if(!s||!s.ok||!s.url||!s.token)return {ok:false,code:"offline",error:"You're offline or signed out."};
  let r;try{r=await fetch(s.url.replace(/\/+$/,"")+"/functions/v1/email-draft",{method:"POST",
    headers:{"Content-Type":"application/json",apikey:s.key||"",Authorization:"Bearer "+s.token},body:JSON.stringify(payload)})}
  catch(e){return {ok:false,code:"offline",error:"Couldn't reach the email writer."}}
  if(r.status===404)return {ok:false,code:"no_fn",error:"The email writer isn't set up yet."};
  let j=null;try{j=await r.json()}catch(e){}
  if(!j||typeof j!=="object")return {ok:false,code:r.status>=500?"busy":"bad",error:"The email writer didn't answer properly. Try again."};
  if(!j.ok&&!j.code&&r.status===401)j.code="auth";
  return j;
}
function emailModal(l,o={}){
  if(!l)return;
  const kind=EM_KIND[o.kind]?o.kind:"",tone0=getP("emailTone","friendly");
  if(typeof invLoad==="function"&&typeof INV!=="undefined"&&!INV.settings)invLoad().catch(()=>{});   // company name for the signature
  const pre=o.prompt!==undefined?o.prompt:kind?EM_KIND[kind][1]:"";
  const sub=[l.btype,emHas(l.address)?l.address:""].filter(Boolean).join(" · ");
  openModal(`<div class="em-dlg"><h2>${ic("mail")}Email ${esc(l.name)}</h2><div class="em-sub">${esc(sub)}${kind?` · <b>${esc(EM_KIND[kind][0])}</b>`:""}</div>
   ${typeof guardBanner==="function"?guardBanner(l):""}
   <div class="em-f"><label class="l" for="emAsk">What should the email say?</label>
    <textarea class="inp" id="emAsk" rows="3" maxlength="600" placeholder="e.g. thank them for the call, offer a free homepage mock-up, ask for 15 minutes on Thursday">${esc(pre)}</textarea>
    <div class="em-picks" role="group" aria-label="Quick picks">${EM_PICKS.map(([t,p],i)=>`<button type="button" class="chip" data-pick="${i}" title="${esc(p)}">${esc(t)}</button>`).join("")}</div></div>
   <div class="em-row"><div class="seg" role="radiogroup" aria-label="Tone">${EM_TONES.map(([k,t])=>`<button type="button" role="radio" data-tone="${k}" class="${k===tone0?"on":""}" aria-checked="${k===tone0}">${t}</button>`).join("")}</div>
    <span class="em-sp"></span><button class="btn pri" id="emGo">${ic("send")}Write email</button></div>
   <div class="em-wait" id="emWait" role="status" aria-live="polite"><i></i>Writing an email for ${esc(l.name)}...</div>
   <div class="em-out" id="emOut" hidden>
    <div id="emMsg" role="status" aria-live="polite"></div>
    <div class="em-f"><label class="l" for="emTo">To</label><input class="inp" id="emTo" type="email" maxlength="160" placeholder="their email address (you can also add it in your email app)" value="${esc(o.to||"")}"></div>
    <div class="em-f"><label class="l" for="emSub">Subject</label><input class="inp" id="emSub" maxlength="150"></div>
    <div class="em-f"><label class="l" for="emBody">Email</label><textarea class="inp" id="emBody" rows="12" maxlength="8000"></textarea></div>
    <details class="em-sig"><summary>Your signature</summary><textarea class="inp" id="emSig" rows="4" maxlength="400" style="width:100%">${esc(emSig())}</textarea>
     <div class="note" style="margin-top:4px">Added under every email you write. Saved for next time.</div></details></div>
   <div class="em-acts"><button class="btn" data-x>Close</button><span class="em-sp"></span>
    <button class="btn" id="emCopy" disabled>${ic("copy")}Copy</button><button class="btn" id="emGmail" disabled>Gmail</button>
    <button class="btn pri" id="emSend" disabled>${ic("mail")}Open in email app</button></div></div>`,
  (ov,close)=>{
    ov.querySelector(".dlg").classList.add("em-wide");
    const g=id=>$("#"+id,ov),ask=g("emAsk"),go=g("emGo"),out=g("emOut"),msg=g("emMsg"),subj=g("emSub"),body=g("emBody"),sig=g("emSig"),to=g("emTo");
    let tone=EM_TONES.some(t=>t[0]===tone0)?tone0:"friendly",busy=false,lastSig=emSig();
    $("[data-x]",ov).onclick=close;
    $$("[data-pick]",ov).forEach(b=>b.onclick=()=>{ask.value=EM_PICKS[+b.dataset.pick][1];ask.focus()});
    $$("[data-tone]",ov).forEach(b=>b.onclick=()=>{tone=b.dataset.tone;setP("emailTone",tone);$$("[data-tone]",ov).forEach(x=>{const on=x===b;x.classList.toggle("on",on);x.setAttribute("aria-checked",on)})});
    const ready=on=>["emCopy","emGmail","emSend"].forEach(i=>g(i).disabled=!on);
    const say=(cls,html)=>{msg.className=cls?"em-msg "+cls:"em-msg";msg.innerHTML=html};
    const show=(s,b)=>{subj.value=s;body.value=emWith(b,sig.value);lastSig=sig.value;out.hidden=false;ready(true)};
    sig.addEventListener("input",()=>{const v=sig.value,old=lastSig.trim();
      if(old&&body.value.endsWith(old))body.value=body.value.slice(0,body.value.length-old.length).replace(/\s+$/,"")+(v.trim()?"\n"+v.trim():"");
      else if(!old&&v.trim()&&body.value)body.value=emWith(body.value,v);lastSig=v});
    sig.addEventListener("change",()=>setP("emailSig",sig.value));
    const write=async()=>{
      if(busy)return;busy=true;go.disabled=true;go.classList.add("em-busy");go.setAttribute("aria-busy","true");g("emWait").classList.add("on");
      const me=S.me||{},co=emCompany();
      const lead={id:l.id||"",name:l.name||"",btype:l.btype||"",address:l.address||"",website:l.website||"",rating:l.rating||"",reviews:l.reviews||"",owner:l.owner||"",notes:l.notes||"",meeting_at:l.meeting_at||""};
      const r=await emDraft({lead,kind,tone,prompt:ask.value.trim(),sender:{name:me.display_name||"",title:(me.ext&&me.ext.title)||"",company:co.name,website:co.website}});
      busy=false;go.disabled=false;go.classList.remove("em-busy");go.removeAttribute("aria-busy");g("emWait").classList.remove("on");
      if(r.ok){show(r.subject,r.body);say("",`Written for ${esc(l.name)}. Read it over before you send it.${r.limit?`<small>${esc(r.used)} of ${esc(r.limit)} emails today</small>`:""}`);
        go.innerHTML=`${ic("send")}Write again`;hydrateIcons(go);logNote("Email written for "+l.name);return}
      if(r.code==="limit"||r.code==="auth"||r.code==="refused"){say("bad",esc(r.error||"Couldn't write that email."));out.hidden=false;return}
      const t=emTemplate(l,kind,tone);show(t.subject,t.body);
      say("warn",esc(r.code==="no_db"?EM_NEED18+" Here's a plain template for now.":r.code==="offline"?"You're offline, so this is a plain template. Your request wasn't used."
        :r.code==="busy"?(r.error||"The AI is busy.")+" Here's a plain template for now.":r.code==="no_fn"||r.code==="no_key"||r.code==="bad_key"?EM_SETUP:(r.error||"Couldn't reach the AI.")+" Here's a plain template for now."));
    };
    go.onclick=write;
    ask.addEventListener("keydown",e=>{if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)){e.preventDefault();write()}});
    const full=()=>({to:to.value.trim(),s:subj.value.trim(),b:body.value});
    g("emCopy").onclick=()=>{const f=full();copyText((f.s?"Subject: "+f.s+"\n\n":"")+f.b)};
    g("emSend").onclick=()=>{const f=full();const url=`mailto:${encodeURIComponent(f.to)}?subject=${encodeURIComponent(f.s)}&body=${encodeURIComponent(f.b)}`;
      if(typeof invMailto==="function")invMailto(url);else location.href=url;setP("emailSig",sig.value)};
    g("emGmail").onclick=()=>{const f=full();window.open(`https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(f.to)}&su=${encodeURIComponent(f.s)}&body=${encodeURIComponent(f.b)}`,"_blank","noopener");setP("emailSig",sig.value)};
    if(o.auto)setTimeout(write,60);else setTimeout(()=>{ask.focus();ask.setSelectionRange(ask.value.length,ask.value.length)},140);
  });
}
/* right after a call: a small card offering to write the email (it doesn't get in the way of the result's own toast) */
function emailNudge(l,kind){
  if(!l||!l.name||!EM_KIND[kind]||!S.me)return;
  /* the result may open its own pop-up first (Interested = reminder, Meeting = meeting time): wait until it's dealt with */
  clearTimeout(EM.waitT);const t0=Date.now();
  const wait=()=>{if(document.querySelector(".ov")){if(Date.now()-t0<180000)EM.waitT=setTimeout(wait,400);return}emNudgeShow(l,kind)};
  EM.waitT=setTimeout(wait,700);
}
function emNudgeShow(l,kind){
  let n=$("#emNudge");if(!n){n=document.createElement("div");n.id="emNudge";n.className="em-nudge";n.setAttribute("role","status");document.body.appendChild(n)}
  n.innerHTML=`${ic("mail")}<span>Email ${esc(l.name)}?</span><button class="btn sm pri" data-emgo>Write email</button><button class="em-x" data-emx aria-label="No thanks">×</button>`;hydrateIcons(n);
  const hide=()=>{n.classList.remove("on");clearTimeout(EM.nudgeT)};
  $("[data-emx]",n).onclick=hide;$("[data-emgo]",n).onclick=()=>{hide();emailModal(l,{kind,auto:true})};
  requestAnimationFrame(()=>n.classList.add("on"));clearTimeout(EM.nudgeT);EM.nudgeT=setTimeout(hide,25000);
}
/* Find Leads: marking one business as No answer / Interested / Meeting = a call just ended */
{const _mk=markLeads;markLeads=async function(status,fromBoard){
  const ids=fromBoard||(S.sel.size?[...S.sel]:S.active?[S.active]:[]);
  const one=!fromBoard&&ids.length===1?S.find.find(x=>x.id===ids[0]):null,o=$("#dOwner"),nt=$("#dNotes");
  const snap=one?{...one,owner:(o&&o.value.trim())||one.owner,notes:nt?nt.value:one.notes}:null;
  const r=await _mk.apply(this,arguments);
  if(snap&&EM_FROM_STATUS[status]&&!S.find.some(x=>x.id===snap.id))emailNudge(snap,EM_FROM_STATUS[status]);
  return r}}
$("#detail").addEventListener("click",e=>{if(!e.target.closest("#dMail"))return;const l=S.find.find(x=>x.id===S.active);if(!l)return;
  const o=$("#dOwner"),nt=$("#dNotes");saveDetail(true);emailModal({...l,owner:(o&&o.value.trim())||l.owner,notes:nt?nt.value:l.notes})});
'''


def inject(ui):
    """Adds the email writer to the shared page."""
    css_at, js_at = "</style>\n</head>", "</script>\n</body>"
    assert ui.count(css_at) == 1 and ui.count(js_at) == 1
    return ui.replace(css_at, EMAIL_CSS + css_at, 1).replace(js_at, EMAIL_JS + js_at, 1)
