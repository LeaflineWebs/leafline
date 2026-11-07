# One-off patch applied to backend/leafline_backend.py (kept for the record; do not run twice).
import re, sys
p = "/home/claude/leafline-app/backend/leafline_backend.py"
s = open(p, encoding="utf-8").read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

# 1. viewport + transport
rep('<meta name="viewport" content="width=device-width, initial-scale=1">', '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
rep('const api=async(n,...a)=>{const r=await fetch("/api/"+n', 'const api=window.LF_API||(async(n,...a)=>{const r=await fetch("/api/"+n')
rep('if(!r.ok)throw new Error((d&&d.error)||"The app engine returned an error ("+r.status+").");return d};', 'if(!r.ok)throw new Error((d&&d.error)||"The app engine returned an error ("+r.status+").");return d});\nif(window.LF_API)document.documentElement.classList.add("web");')
rep('try{const es=new EventSource("/events?t="+encodeURIComponent(TOKEN));es.onmessage=e=>{try{window.onPy(JSON.parse(e.data))}catch(x){}}}catch(e){}',
    'if(!window.LF_API){try{const es=new EventSource("/events?t="+encodeURIComponent(TOKEN));es.onmessage=e=>{try{window.onPy(JSON.parse(e.data))}catch(x){}}}catch(e){}}')
rep('account:"Account"};', 'account:"Account & Settings"};')

# 2. CSS
css = r'''
/* ---- profile extras, updates ---- */
.accr{display:grid;gap:18px;min-width:0}
.pban{height:96px;border-radius:18px;background:linear-gradient(120deg,#1D4130,#173A28);background-size:cover;background-position:center;position:relative}
.pbanw{margin-bottom:6px}.pbanw .avbtns{justify-content:flex-start}
.moods{display:flex;gap:6px;flex-wrap:wrap}.moods button{width:38px;height:38px;border-radius:12px;background:var(--panel);border:1px solid var(--line);font-size:19px}.moods button.on{border-color:var(--accent);background:rgba(61,220,132,.16)}
textarea.inp{height:auto;padding:10px 14px;line-height:1.45;resize:vertical;font:inherit}
.upd{display:flex;gap:16px;align-items:center;justify-content:space-between;margin-top:10px;flex-wrap:wrap}.upd .note{margin-top:3px}
.upd .bar{height:6px;border-radius:3px;background:rgba(255,255,255,.08);overflow:hidden;margin-top:8px;display:none}.upd .bar i{display:block;height:100%;background:var(--accent);width:0}
.tm-th{padding:16px 20px}.tm-th h3{margin:0 0 10px;font-size:16px}
.th-i{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-top:1px solid rgba(255,255,255,.06)}.th-i:first-of-type{border-top:0}
.th-i q{font-size:14.5px;line-height:1.4;quotes:"\201C" "\201D"}.th-i small{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.tm-p{cursor:pointer;border-top:3px solid var(--acc,transparent)}
.tm-p .psub{color:var(--muted);font-size:12.5px;margin:6px 0 0}.tm-p .pbio{font-size:13px;line-height:1.4;margin-top:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:#cfe3d6}
.tm-p .pth{margin-top:8px;padding:8px 10px;border-radius:12px;background:rgba(255,255,255,.06);font-size:13px;line-height:1.35}
.pcard{--acc:#3DDC84;text-align:center}.pcard .pban{margin:-24px -26px 0;border-radius:30px 30px 0 0;height:130px}
.pcard .pav{margin-top:-42px;display:flex;justify-content:center}.pcard .pav .tav{width:84px;height:84px;font-size:28px;box-shadow:0 0 0 4px #182A1F,0 0 0 6px var(--acc)}
.pcard h2{margin-top:10px;font-size:22px}.pcard .pm{font-size:22px}.pcard .sub{color:var(--muted);font-size:13.5px;margin-top:2px}.pcard .sub .on{color:var(--accent)}
.pcard .pbio2{margin:14px 4px 0;line-height:1.5;white-space:pre-wrap;font-size:14px}
.pcard .pth{margin:14px 0 0;padding:12px 14px;border-radius:16px;background:rgba(255,255,255,.07);font-size:15px;line-height:1.4}.pcard .pth small{display:block;color:var(--muted);font-size:11.5px;margin-top:4px}
.idc .pban{margin:-26px -22px 14px;border-radius:30px 30px 0 0;height:92px}.idc .pban+.ring{margin-top:-52px}
/* ---- phones and tablets (also used by the iPhone home-screen app) ---- */
@media (max-width:860px){
  html,body{height:100%}
  .app{display:block;padding:0;height:100dvh}
  .side{display:none}
  .main{border-radius:0;height:100dvh;padding-top:env(safe-area-inset-top)}
  .top{padding:10px 12px 4px;gap:8px}
  .top h1{font-size:19px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;flex:1}
  .srch,#userBtn,#scriptBtn{display:none}
  .sync{height:34px;padding:0 10px;font-size:12px}.sync span{max-width:92px;overflow:hidden;text-overflow:ellipsis}
  .page{padding:8px 12px calc(92px + env(safe-area-inset-bottom))}
  .fnav{left:0;right:0;bottom:0;transform:none;padding:8px 8px calc(8px + env(safe-area-inset-bottom));background:rgba(12,22,17,.94);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);box-shadow:0 -8px 24px rgba(0,0,0,.35)}
  .fpill{overflow-x:auto;max-width:100%;scrollbar-width:none;border-radius:26px;width:100%}.fpill::-webkit-scrollbar{display:none}
  .fpill button{height:38px;padding:0 14px;font-size:13px;flex:none}
  .fplus{display:none}
  .banner{grid-template-columns:1fr;padding:18px}.banner>div:first-child,.ill{display:none}
  .stats,.cstats{grid-template-columns:1fr 1fr;gap:10px}
  .frow{grid-template-columns:1fr 1fr}.frow>div:nth-child(4){grid-column:1/3}
  .split{grid-template-columns:1fr;min-height:0}.split .dpane{display:none}
  .board{grid-template-columns:repeat(4,minmax(240px,82vw));overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:8px}.board>*{scroll-snap-align:start}
  .acc{grid-template-columns:1fr}
  .fg{grid-template-columns:1fr}.fg>*{grid-column:auto!important}
  .tm-2,.cal-wrap,.nt{grid-template-columns:1fr}
  .nt{height:auto;padding-bottom:96px}.nt-list{max-height:260px}
  .ad-t{grid-template-columns:1fr 1fr}
  .tm-tiles{grid-template-columns:1fr 1fr}.tm-people{grid-template-columns:1fr}
  .tm-p .nums{grid-template-columns:repeat(3,1fr)}
  .dlg{width:94vw;padding:20px 18px;border-radius:24px;max-height:86dvh}
  .tbl{display:block;overflow-x:auto;white-space:nowrap}
  .cl-f{padding:12px}.cl-f>div{flex:1 1 140px}
  .wk-grid{grid-template-columns:repeat(7,minmax(130px,1fr))}
  .dock{display:none!important}
  .toast{bottom:calc(84px + env(safe-area-inset-bottom))}
  input,select,textarea{font-size:16px}
}
.web .frow,.web #fplus{display:none}
.web #goBtn{display:none}
'''
rep('</style>\n</head>', css + '</style>\n</head>')

# 3. profile extras + update JS (placed before the "search" section)
js = r'''
/* ---------------- app updates (desktop installer or website; same card) ---------------- */
const UP=(window.leafline&&window.leafline.checkUpdate)?window.leafline:(window.LF_WEB||null);
const UPS={state:"idle",version:"",latest:"",percent:0,error:"",platform:""};
function paintUpd(){
  const n=$("#updNote"),b=$("#updBtn"),v=$("#updVer"),bar=$("#updBar");if(!n)return;
  const web=UPS.platform==="web",s=UPS.state;
  v.textContent="Version "+(UPS.version||"?")+(web?" (website)":" (desktop)");
  let t="New versions are installed automatically each time you open the app.",lab="Check for updates";
  if(s==="checking")t="Checking for updates...";
  else if(s==="none")t="You're on the latest version.";
  else if(s==="available"||s==="downloading")t=`Downloading version ${UPS.latest||""}${UPS.percent?" ("+Math.round(UPS.percent)+"%)":"..."}`;
  else if(s==="ready"){t=web?`Version ${UPS.latest} is ready.`:`Version ${UPS.latest} is downloaded. It installs when you restart.`;lab=web?"Reload now":"Restart & update"}
  else if(s==="error"){t=UPS.error||"Couldn't check for updates.";lab="Try again"}
  n.textContent=t;b.textContent=lab;b.disabled=(s==="checking"||s==="available"||s==="downloading");
  bar.style.display=(s==="downloading"||s==="available")?"block":"none";$("i",bar).style.width=(UPS.percent||0)+"%";
}
async function initUpdates(){
  if(!UP)return;
  try{const i=await UP.appInfo();UPS.version=i.version;UPS.platform=i.platform||"desktop"}catch(e){}
  UP.onUpdate(st=>{Object.assign(UPS,st);paintUpd();
    if(st.state==="ready"&&S.updToast!==st.latest){S.updToast=st.latest;toast(`Update ${st.latest||""} is ready`,{ms:20000,action:{label:UPS.platform==="web"?"Reload":"Restart",fn:()=>UP.installUpdate()}});logNote("An app update is ready ("+(st.latest||"")+")")}});
  try{const c=await (UP.status?UP.status():null);c&&Object.assign(UPS,c)}catch(e){}
}
async function checkUpdatesNow(){
  if(!UP)return;
  if(UPS.state==="ready")return UP.installUpdate();
  UPS.state="checking";paintUpd();
  try{const r=await UP.checkUpdate();if(r)Object.assign(UPS,r)}catch(e){UPS.state="error";UPS.error="Couldn't check: "+e.message}
  paintUpd();
}
/* ---------------- profile extras: title, bio, mood, thought of the day, banner ---------------- */
const ACCENTS=["#3DDC84","#4DD0E1","#5C9DFF","#B388FF","#FF7EB6","#FF5C5C","#FF9F43","#FFD60A"];
const MOODS=["😀","😎","🔥","💪","🚀","☕","🎯","🤝","🎧","😴"];
const okAccent=a=>/^#[0-9A-Fa-f]{6}$/.test(a||"")?a:"";
const safeBanner=u=>(typeof u==="string"&&u.length<160000&&IMG_OK.test(u))?u:"";
const freshThought=x=>!!(x&&x.thought&&x.thought_at&&Date.now()-new Date(x.thought_at).getTime()<36*3600e3);
function bannerFromFile(file){
  return new Promise((res,rej)=>{
    if(!file||!/^image\//.test(file.type))return rej(new Error("Pick an image file (JPG, PNG or WebP)."));
    if(file.size>20e6)return rej(new Error("That image is too big. Pick one under 20 MB."));
    const url=URL.createObjectURL(file),im=new Image();
    im.onload=()=>{try{const W=720,H=180,c=document.createElement("canvas");c.width=W;c.height=H;const x=c.getContext("2d");x.fillStyle="#173A28";x.fillRect(0,0,W,H);
      const k=Math.max(W/im.naturalWidth,H/im.naturalHeight),w=im.naturalWidth*k,h=im.naturalHeight*k;x.drawImage(im,(W-w)/2,(H-h)/2,w,h);
      let q=.85,d=c.toDataURL("image/jpeg",q);while(d.length>110000&&q>.3){q-=.1;d=c.toDataURL("image/jpeg",q)}URL.revokeObjectURL(url);d.length>140000?rej(new Error("That picture is too detailed. Try another.")):res(d)}catch(e){rej(e)}};
    im.onerror=()=>{URL.revokeObjectURL(url);rej(new Error("Couldn't read that picture. Try a JPG or PNG."))};im.src=url});
}
function personModal(p){
  if(!p)return;const ext=p.ext||{},mine=!!(S.me&&S.me.id===p.id),acc=okAccent(ext.accent)||"#3DDC84";
  openModal(`<div class="pcard" style="--acc:${acc}"><div class="pban" id="pBan"></div><div class="pav">${avHTML(p.name,p.avatar)}</div>
   <h2>${esc(p.name)}${ext.mood?` <span class="pm">${esc(ext.mood)}</span>`:""}</h2>
   <div class="sub">${esc([ext.title,p.role==="admin"?"Admin":"Rep"].filter(Boolean).join(" · "))} · <span class="${p.online?"on":""}">${p.online?"Online":"Offline"}</span></div>
   ${ext.bio?`<p class="pbio2">${esc(ext.bio)}</p>`:""}
   ${freshThought(ext)?`<div class="pth">“${esc(ext.thought)}”<small>Thought of the day</small></div>`:""}
   ${p.today?`<div class="mini"><div><b>${p.today.calls}</b><span>Calls today</span></div><div><b>${p.today.meetings}</b><span>Meetings</span></div><div><b>${p.today.sales}</b><span>Sales</span></div></div>`:""}
   <div style="text-align:right;margin-top:18px"><button class="btn pri" data-x>Close</button></div></div>`,(ov,close)=>{
    $("[data-x]",ov).onclick=close;
    const set=u=>{u=safeBanner(u);if(u)$("#pBan",ov).style.backgroundImage=`url("${u}")`};
    if(mine)set(S.me.ext&&S.me.ext.banner);else api("get_person",p.id).then(r=>{if(r&&r.ok&&r.person)set(r.person.banner)}).catch(()=>{})});
}
'''
rep('/* ---------------- search ---------------- */', js + '/* ---------------- search ---------------- */')

# 4. Account page: right column becomes two cards + extras + updates
rep('''  <div class="card form pop"><h3>Account details</h3>''', '''  <div class="accr"><div class="card form pop"><h3>Account details</h3>''')
rep('''<span class="note" id="dbNote"></span></div></div></div>`;''', '''<span class="note" id="dbNote"></span></div></div>
  ${(()=>{const ex=(S.me&&S.me.ext)||{};return `<div class="card form pop" id="extCard"><h3>Your public profile</h3><div class="note">Everyone on the team can see this on the Team page.</div>
   <div class="pbanw" style="margin-top:14px"><div class="pban" id="bnPrev"></div><div class="avbtns"><button class="btn sm" id="bnUp">Upload banner</button><button class="btn sm" id="bnDel">Remove banner</button><input type="file" id="bnFile" accept="image/png,image/jpeg,image/webp" hidden></div></div>
   <div class="fg">
    <div><label class="l" for="xTitle">Job title</label><input class="inp" id="xTitle" maxlength="40" value="${esc(ex.title||"")}" placeholder="e.g. Sales rep"></div>
    <div><label class="l">Mood</label><div class="moods" id="xMoods">${MOODS.map(m=>`<button type="button" data-m="${m}" class="${ex.mood===m?"on":""}" aria-label="Mood ${m}">${m}</button>`).join("")}</div></div>
    <div style="grid-column:1/3"><label class="l" for="xBio">Bio</label><textarea class="inp" id="xBio" maxlength="280" rows="3" placeholder="A line or two about you">${esc(ex.bio||"")}</textarea><div class="note"><span id="xBioN">0</span>/280</div></div>
    <div style="grid-column:1/3"><label class="l" for="xTh">Thought of the day</label><input class="inp" id="xTh" maxlength="140" value="${esc(freshThought(ex)?ex.thought:"")}" placeholder="Something to share with the team today"></div>
    <div style="grid-column:1/3"><label class="l">Profile colour</label><div class="sw" id="xAcc" style="justify-content:flex-start;margin:6px 0 0">${ACCENTS.map(c=>`<button type="button" style="background:${c}" data-a="${c}" class="${(okAccent(ex.accent)||ACCENTS[0])===c?"on":""}" aria-label="Colour ${c}"></button>`).join("")}</div></div></div>
   <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap"><button class="btn pri" id="xSave">Save profile</button><span class="note" id="xNote"></span></div></div>
  <div class="card form pop" id="updCard"><h3>App &amp; updates</h3>
   <div class="upd"><div><b id="updVer">Version</b><div class="note" id="updNote"></div><div class="bar" id="updBar"><i></i></div></div><button class="btn" id="updBtn">Check for updates</button></div></div></div></div>`})()}`;''')

# account handlers: appended right before the data-folder note line
rep('''  $("#dbNote").textContent=S.dbPath?"Data folder: "+S.dbPath:"";
}''', '''  $("#dbNote").textContent=S.dbPath&&!window.LF_API?"Data folder: "+S.dbPath:"";
  /* public profile */
  {const ex0=(S.me&&S.me.ext)||{};let bn,mood=ex0.mood||"",acc=okAccent(ex0.accent)||ACCENTS[0];
   const showBn=u=>{u=safeBanner(u);$("#bnPrev").style.backgroundImage=u?`url("${u}")`:"";$("#bnDel").style.display=u?"":"none"};showBn(ex0.banner);
   $("#bnUp").onclick=()=>$("#bnFile").click();
   $("#bnFile").onchange=async e=>{const f=e.target.files[0];e.target.value="";if(!f)return;try{bn=await bannerFromFile(f);showBn(bn)}catch(x){toast(x.message,{bad:1})}};
   $("#bnDel").onclick=()=>{bn="";showBn("")};
   $$("#xMoods button").forEach(b=>b.onclick=()=>{mood=(mood===b.dataset.m)?"":b.dataset.m;$$("#xMoods button").forEach(x=>x.classList.toggle("on",x.dataset.m===mood))});
   $$("#xAcc button").forEach(b=>b.onclick=()=>{acc=b.dataset.a;$$("#xAcc button").forEach(x=>x.classList.toggle("on",x===b));bump(b)});
   const cnt=()=>{$("#xBioN").textContent=$("#xBio").value.length};cnt();$("#xBio").oninput=cnt;
   $("#xSave").onclick=async()=>{
     const d={title:$("#xTitle").value,mood,bio:$("#xBio").value,thought:$("#xTh").value,accent:acc};if(bn!==undefined)d.banner=bn;
     const r=await api("set_profile_ext",d);if(!r.ok)return toast(r.error||"Couldn't save.",{bad:1});
     S.me.ext=r.ext;bn=undefined;bump($("#xSave"));toast("Profile saved");
     $("#xNote").textContent=r.shared?"The team can see your changes.":"Saved on this device. It will be shared once the database update (step 4 in the setup guide) is applied."};}
  initUpdates().then(()=>{paintUpd();$("#updBtn").onclick=checkUpdatesNow;if(!UP){$("#updCard").style.display="none"}});
}''')
# banner on the identity card
rep('''  pg.innerHTML=`<div class="acc"><div class="card idc pop"><div class="ring">''', '''  pg.innerHTML=`<div class="acc"><div class="card idc pop">${S.me&&S.me.ext&&safeBanner(S.me.ext.banner)?`<div class="pban" style="background-image:url('${safeBanner(S.me.ext.banner)}')"></div>`:""}<div class="ring">''')

# 5. Team page: thoughts strip + richer cards
rep('''   <div class="tm-people">${d.people.map(p=>`<div class="card tm-p ${S.me&&S.me.id===p.id?"me":""}">
     <h3>${avHTML(p.name,p.avatar)}${esc(p.name)}<span class="role">${p.role==="admin"?"Admin":"Rep"}</span><span class="st ${p.online?"on":""}"><i></i>${p.online?"Online":"Offline"}</span></h3>''',
'''   ${d.people.some(p=>freshThought(p.ext))?`<div class="card tm-th"><h3>Thoughts of the day</h3>${d.people.filter(p=>freshThought(p.ext)).map(p=>`<div class="th-i">${avHTML(p.name,p.avatar)}<div><q>${esc(p.ext.thought)}</q><small>${esc(p.name)}${p.ext.mood?" "+esc(p.ext.mood):""}</small></div></div>`).join("")}</div>`:""}
   <div class="tm-people">${d.people.map(p=>`<div class="card tm-p ${S.me&&S.me.id===p.id?"me":""}" data-pid="${esc(p.id)}" style="--acc:${okAccent((p.ext||{}).accent)||"transparent"}">
     <h3>${avHTML(p.name,p.avatar)}${esc(p.name)}${(p.ext||{}).mood?` <span>${esc(p.ext.mood)}</span>`:""}<span class="role">${p.role==="admin"?"Admin":"Rep"}</span><span class="st ${p.online?"on":""}"><i></i>${p.online?"Online":"Offline"}</span></h3>
     ${(p.ext||{}).title?`<div class="psub">${esc(p.ext.title)}</div>`:""}${(p.ext||{}).bio?`<div class="pbio">${esc(p.ext.bio)}</div>`:""}${freshThought(p.ext)?`<div class="pth">“${esc(p.ext.thought)}”</div>`:""}''')
rep('''  hydrateIcons(pg);
}
setInterval(()=>{if(S.ready&&S.page==="team"&&!document.hidden)renderTeam()},8000);''', '''  hydrateIcons(pg);
  $$("[data-pid]",pg).forEach(c=>c.onclick=()=>personModal(d.people.find(x=>x.id===c.dataset.pid)));
}
setInterval(()=>{if(S.ready&&S.page==="team"&&!document.hidden)renderTeam()},8000);''')

# 6. boot: updates + web notes
rep('''  S.ready=true;
  const start=''', '''  S.ready=true;initUpdates().then(()=>{if(UP&&UP.platform!=="web"&&UPS.state==="ready")paintUpd()});
  if(window.LF_API){const sl=$("#sText");if(sl)sl.textContent="New businesses are found in the Leafline desktop app and show up here automatically."}
  const start=''')
open(p, "w", encoding="utf-8").write(s)
print("ok")
