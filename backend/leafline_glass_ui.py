"""Liquid glass (11.17): an optional look, switched on and off in Settings > Appearance.

Real optical glass, not a blurred card. Four layers on every glass surface:
  1. Refraction: a per-shape SVG filter (feImage normal map + feDisplacementMap) bends what is behind the
     surface, only inside its outer 12-24px rim. Chromium only (the desktop app, Chrome, Edge), applied as
     backdrop-filter: url(#...). The preset's interior blur happens inside the same filter, masked to the
     middle (the map's blue channel marks the rim): a CSS blur() after url(#...) would smear the bent rim
     back into flat colour, so the bend would not show.
  2. Chromatic dispersion: three displacement passes (R/G/B) with slightly different scales, recombined with
     screen blending, give a thin prism fringe at the rim.
  3. Specular rim + bezel light: crisp inset highlights and a highlight that follows the pointer.
  4. Fallback: backdrop-filter: blur(16px) saturate(180%) everywhere, so Safari and Firefox get clean frosted
     glass with the same layout.

Normal maps are drawn on an offscreen canvas at each surface's exact size and corner radius, only when a
ResizeObserver reports a size (never while scrolling or moving the mouse). Surfaces bigger than 900 x 900
(or with more area than that) never get the displacement filter, only the blur.
"""

GLASS_HEAD = r'''<script>try{if(localStorage.getItem("lf_glass")==="1")document.documentElement.classList.add("lf-glass")}catch(e){}</script>
'''

GLASS_CSS = r'''
/* ================= Liquid glass (11.17) — only when <html class="lf-glass"> ================= */
@property --lx{syntax:"<length-percentage>";inherits:false;initial-value:30%}
@property --ly{syntax:"<length-percentage>";inherits:false;initial-value:0%}
/* the room the glass sits in: soft light in the theme's colours and a faint dot grid, so the glass has
   something to bend (a flat colour behind glass looks the same bent or not) */
html.lf-glass body{background-color:var(--bg);
  background-image:radial-gradient(900px 640px at 6% -4%,rgba(var(--accent-rgb),.26),transparent 62%),
    radial-gradient(820px 600px at 100% 106%,color-mix(in srgb,var(--accent2) 34%,transparent),transparent 64%),
    radial-gradient(560px 460px at 58% 34%,color-mix(in srgb,var(--hi2) 11%,transparent),transparent 70%),
    radial-gradient(circle at 1px 1px,rgba(255,255,255,.06) 1px,transparent 1.6px);
  background-size:auto,auto,auto,24px 24px}
html.lf-glass .main{background:radial-gradient(circle at 1px 1px,rgba(var(--accent-rgb),.10) 1px,transparent 1.6px) 0 0/24px 24px,
    linear-gradient(180deg,color-mix(in srgb,var(--main1) 70%,transparent),color-mix(in srgb,var(--main2) 80%,transparent)) !important;
  box-shadow:var(--sh),inset 0 1px 1px rgba(255,255,255,.14),inset 0 -1px 2px rgba(255,255,255,.05) !important}
/* containers that would cut glass off from what is behind it (a backdrop-filter on a parent hides the page from its children) */
html.lf-glass .ov{-webkit-backdrop-filter:none !important;backdrop-filter:none !important;background:color-mix(in srgb,var(--bg) 58%,transparent) !important}
html.lf-glass .fnav{-webkit-backdrop-filter:none !important;backdrop-filter:none !important;background:none !important;box-shadow:none !important}

/* ---- every glass surface ---- */
html.lf-glass [data-lgp]:not([data-lgp=liquid-mercury]){
  --lg-t:64%;--lg-c1:var(--card);--lg-c2:var(--card-end);--lg-ss:260px;--lg-sp:.15;--lg-s1:.10;--lg-s2:.02;--lg-s3:.07;
  --lg-edge:color-mix(in srgb,rgba(255,255,255,.28) 78%,rgba(var(--accent-rgb),.55));
  --lg-depth:0 20px 40px rgba(0,0,0,.25);
  background:radial-gradient(var(--lg-ss) circle at var(--lx) var(--ly),rgba(255,255,255,var(--lg-sp)),transparent 62%),
    linear-gradient(135deg,rgba(255,255,255,var(--lg-s1)) 0%,rgba(255,255,255,var(--lg-s2)) 50%,rgba(255,255,255,var(--lg-s3)) 100%),
    linear-gradient(180deg,color-mix(in srgb,var(--lg-c1) var(--lg-t),transparent),color-mix(in srgb,var(--lg-c2) var(--lg-t),transparent)) !important;
  -webkit-backdrop-filter:blur(16px) saturate(180%) !important;backdrop-filter:blur(16px) saturate(180%) !important;
  border:1px solid var(--lg-edge) !important;
  box-shadow:var(--lg-depth),inset 0 1px 1px rgba(255,255,255,.6),inset 0 -1px 2px rgba(255,255,255,.15),var(--lg-ring,0 0 #0000) !important}
/* presets: corner radius + how clear the glass is */
html.lf-glass [data-lgp=frosted-pill]{border-radius:9999px !important;--lg-t:40%;--lg-ss:120px;--lg-sp:.22;--lg-depth:0 10px 24px rgba(0,0,0,.28)}
html.lf-glass [data-lgp=thick-lens]{border-radius:28px !important;--lg-t:74%;--lg-c1:var(--card2);--lg-c2:var(--card);--lg-ss:380px;--lg-sp:.18;--lg-s1:.13;--lg-s3:.09;--lg-depth:0 30px 70px rgba(0,0,0,.45)}
html.lf-glass [data-lgp=subtle-pane]{border-radius:16px !important;--lg-t:62%;--lg-s1:.07;--lg-s2:.015;--lg-s3:.05;--lg-sp:.10;--lg-depth:0 14px 32px rgba(0,0,0,.28)}
html.lf-glass .banner[data-lgp]{--lg-c1:color-mix(in srgb,var(--accent) 16%,var(--card));--lg-c2:color-mix(in srgb,var(--accent2) 8%,var(--card-end));--lg-t:66%}
html.lf-glass .side[data-lgp]{--lg-c1:var(--side1);--lg-c2:var(--side2);--lg-t:56%}
html.lf-glass .fplus[data-lgp]{--lg-c1:var(--accent);--lg-c2:var(--accent2);--lg-t:72%;--lg-ring:0 0 24px var(--glow-soft)}
html.lf-glass .toast[data-lgp]{--lg-ring:0 0 0 1px var(--accent-line),0 0 30px var(--glow-soft)}
html.lf-glass .top .srch input[data-lgp]:focus{border-color:var(--accent) !important;--lg-ring:0 0 0 4px rgba(var(--accent-rgb),.18)}
html.lf-glass [data-lgp=frosted-pill]:hover{--lg-ring:0 0 0 1px var(--accent-line),0 0 26px var(--glow-soft)}
@media (hover:hover){html.lf-glass .card[data-lgp]:hover{--lg-ring:0 0 0 1px var(--accent-line),0 0 34px var(--glow-soft)}}
/* the theme picker's pop-up sits above everything; keep it readable */
html.lf-glass .thpop[data-lgp]{--lg-t:84%}

/* ---- liquid-mercury: the switch thumb is a drop of glass that bends the track under it ---- */
html.lf-glass .tgl[data-lgp]{background:repeating-linear-gradient(90deg,rgba(255,255,255,.07) 0 1px,transparent 1px 5px),linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.11));
  box-shadow:inset 0 0 0 1px var(--line2),inset 0 2px 5px rgba(0,0,0,.3)}
html.lf-glass .tgl.on[data-lgp]{background:repeating-linear-gradient(90deg,rgba(255,255,255,.16) 0 1px,transparent 1px 5px),linear-gradient(90deg,var(--accent2),var(--accent));
  box-shadow:inset 0 0 0 1px var(--accent-line),inset 0 2px 5px rgba(0,0,0,.22),0 0 18px var(--glow-soft)}
html.lf-glass .tgl[data-lgp]:after{border-radius:50% !important;
  background:radial-gradient(10px circle at 34% 26%,rgba(255,255,255,.85),rgba(255,255,255,0) 70%),
    linear-gradient(135deg,rgba(255,255,255,.34) 0%,rgba(255,255,255,.06) 50%,rgba(255,255,255,.20) 100%) !important;
  -webkit-backdrop-filter:blur(16px) saturate(180%);backdrop-filter:var(--lgf,blur(16px) saturate(180%));
  box-shadow:0 3px 8px rgba(0,0,0,.35),inset 0 1px 1px rgba(255,255,255,.6),inset 0 -1px 2px rgba(255,255,255,.15),inset 0 0 0 1px rgba(255,255,255,.28) !important;
  transform:translateX(var(--tx,0px)) scale(var(--sx,1),var(--sy,1)) !important}
html.lf-glass .tgl.on[data-lgp]:after{transform:translateX(var(--tx,20px)) scale(var(--sx,1),var(--sy,1)) !important}
html.lf-glass .tgl[data-lgsp]:after{transition:none !important}

/* less see-through when the system asks for it */
@media (prefers-reduced-transparency:reduce){html.lf-glass [data-lgp]:not([data-lgp=liquid-mercury]){--lg-t:92% !important}}

/* ---- the switch in Settings > Appearance ---- */
.lfg-row{display:flex;align-items:center;gap:16px;margin-top:16px;padding:14px 16px;border-radius:18px;background:rgba(0,0,0,.16);border:1px solid var(--line)}
.lfg-row>div{flex:1;min-width:0}.lfg-row b{font-size:14px}.lfg-row .note{margin-top:3px}
'''

GLASS_JS = r'''
/* ================= Liquid glass (11.17) =================
   Glass surfaces are picked by selector, each with one of four presets. Per surface: an SVG filter whose
   normal map (an offscreen canvas at the surface's exact size and corner radius) bends the backdrop only in
   the outer rim, in three colour channels at slightly different strengths. Maps are made only when a
   ResizeObserver reports a size; scrolling and the mouse never make new ones. */
const LG=(()=>{
  const PRESET={
    "frosted-pill":  {s:-90, f:4,blur:8},    // buttons, floating nav: strong edge, clear middle
    "thick-lens":    {s:-145,f:7,blur:12},   // pop-ups and dialogs: deep bezel, clear prism fringe
    "liquid-mercury":{s:-180,f:9,blur:4},    // switch thumbs: the most bend, on a spring
    "subtle-pane":   {s:-55, f:2,blur:20}};  // sidebar and cards: gentle rim, more frosting for text
  const SEL=[[".ov .dlg","thick-lens"],[".hcard","thick-lens"],[".bell","thick-lens"],[".remp","thick-lens"],[".thpop","thick-lens"],[".toast","thick-lens"],[".remn","thick-lens"],[".sheet .sp","thick-lens"],
    [".fpill","frosted-pill"],[".fplus","frosted-pill"],[".top .rb","frosted-pill"],[".top .sync","frosted-pill"],[".top .srch input","frosted-pill"],[".lgt:not(.big)","frosted-pill"],
    [".tgl","liquid-mercury"],
    [".side","subtle-pane"],[".page .card","subtle-pane"],[".page .tm-tile","subtle-pane"],[".page .banner","subtle-pane"],[".page .stat","subtle-pane"],[".page .cstat","subtle-pane"],[".bdgtip","subtle-pane"]];
  const ALL=SEL.map(x=>x[0]).join(",");
  const UA=navigator.userAgent,brands=(navigator.userAgentData&&navigator.userAgentData.brands)||[];
  const chromium=brands.some(b=>/Chromium/i.test(b.brand))||(/\bChrome\/\d+/.test(UA)&&!/\b(CriOS|FxiOS|EdgiOS)\b|Firefox\//.test(UA));
  const L={on:false,opt:chromium&&!!(window.CSS&&CSS.supports&&CSS.supports("backdrop-filter","url(#lgx)")),recs:new Map(),filters:new Map(),n:0,defs:null,ro:null,io:null,mo:null,queued:false};
  const cap=()=>(matchMedia("(pointer:coarse)").matches||innerWidth<700)?6:14;   // cards bending at once (pills and pop-ups are few and small)
  const presetOf=el=>{for(const [s,p] of SEL)if(el.matches(s))return p;return null};
  const tooBig=(w,h)=>(w>900&&h>900)||w*h>810000;
  function defs(){
    if(L.defs&&L.defs.isConnected)return L.defs;
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.setAttribute("aria-hidden","true");svg.id="lgDefs";
    svg.setAttribute("style","position:absolute;width:0;height:0;pointer-events:none;overflow:hidden");
    svg.appendChild(document.createElementNS("http://www.w3.org/2000/svg","defs"));document.body.appendChild(svg);return L.defs=svg.firstChild;
  }
  /* the normal map: R/G = which way the rim leans (128 = flat); B = how much of the rim shows sharp (0 = frosted).
     The middle is exactly rgb(128,128,0): no bend, so text and icons on the glass never move. */
  function normalMap(w,h,r,b,mmax){
    const cv=document.createElement("canvas");cv.width=w;cv.height=h;const cx=cv.getContext("2d"),im=cx.createImageData(w,h),d=im.data;
    const hw=w/2,hh=h/2;r=Math.min(r,hw,hh);
    for(let y=0;y<h;y++){const py=y+.5-hh,ay=Math.abs(py),sy=py<0?-1:1,qy=ay-(hh-r);
      for(let x=0;x<w;x++){const px=x+.5-hw,ax=Math.abs(px),qx=ax-(hw-r),i=(y*w+x)*4;let dist,nx=0,ny=0;
        if(qx>0&&qy>0){const l=Math.hypot(qx,qy);dist=r-l;if(l>0){nx=qx/l;ny=qy/l}}
        else if(hw-ax<hh-ay){dist=hw-ax;nx=1}else{dist=hh-ay;ny=1}
        let m=0,k=0;if(dist>0&&dist<b){const t=1-dist/b;m=Math.pow(t,1.8)*mmax;k=Math.min(1,t*1.6)}
        d[i]=Math.round(128+(px<0?-nx:nx)*m*127);d[i+1]=Math.round(128+sy*ny*m*127);d[i+2]=Math.round(k*255);d[i+3]=255}}
    cx.putImageData(im,0,0);return cv.toDataURL("image/png");
  }
  const NS="http://www.w3.org/2000/svg",mk=(tag,at)=>{const e=document.createElementNS(NS,tag);for(const k in at)e.setAttribute(k,at[k]);return e};
  /* one filter per shape (same-size cards share one) */
  function filterFor(key,p,w,h,r){
    let f=L.filters.get(key);if(f){f.refs++;f.used=Date.now();return f}
    const P=PRESET[p],b=Math.max(4,Math.min(Math.max(12,Math.min(24,Math.round(Math.min(w,h)*.22))),Math.floor(Math.min(w,h)/2)));
    /* small surfaces: the rim may only borrow from inside the surface, so the strongest bend fits in it */
    const mmax=Math.min(1,Math.max(.05,(Math.min(w,h)-4)/((Math.abs(P.s)+P.f)/2)));
    const id="lgf"+(++L.n),fl=mk("filter",{id,x:"-10%",y:"-10%",width:"120%",height:"120%","color-interpolation-filters":"sRGB"});
    fl.appendChild(mk("feImage",{href:normalMap(w,h,r,b,mmax),x:0,y:0,width:w,height:h,preserveAspectRatio:"none",result:"map"}));
    fl.appendChild(mk("feGaussianBlur",{in:"SourceGraphic",stdDeviation:P.blur,result:"frost"}));   // the preset's interior blur
    [["R",P.s-P.f,"1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"],["G",P.s,"0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"],["B",P.s+P.f,"0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"]].forEach(([c,s,v])=>{
      fl.appendChild(mk("feDisplacementMap",{in:"SourceGraphic",in2:"map",scale:s,xChannelSelector:"R",yChannelSelector:"G",result:"disp"+c}));
      fl.appendChild(mk("feColorMatrix",{in:"disp"+c,type:"matrix",values:v,result:"ch"+c}))});
    fl.appendChild(mk("feBlend",{in:"chR",in2:"chG",mode:"screen",result:"rg"}));
    fl.appendChild(mk("feBlend",{in:"rg",in2:"chB",mode:"screen",result:"refracted"}));
    /* sharp, bent rim over the frosted middle */
    fl.appendChild(mk("feColorMatrix",{in:"map",type:"matrix",values:"0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 1 0 0",result:"rim"}));
    fl.appendChild(mk("feComposite",{in:"refracted",in2:"rim",operator:"in",result:"edge"}));
    fl.appendChild(mk("feComposite",{in:"edge",in2:"frost",operator:"over",result:"glass"}));
    defs().appendChild(fl);f={id,node:fl,refs:1,used:Date.now()};L.filters.set(key,f);return f;
  }
  function release(key){const f=key&&L.filters.get(key);if(!f)return;f.refs=Math.max(0,f.refs-1);
    if(L.filters.size>48){const idle=[...L.filters].filter(([,x])=>!x.refs).sort((a,b)=>a[1].used-b[1].used);
      for(const [k,x] of idle.slice(0,L.filters.size-40)){x.node.remove();L.filters.delete(k)}}}
  const px=v=>{const n=parseFloat(v);return isFinite(n)?n:0};
  /* size, corner radius and shape key of a surface (for a switch: of its thumb) */
  function measure(rec){
    const el=rec.el;
    if(rec.p==="liquid-mercury"){const a=getComputedStyle(el,"::after"),w=Math.round(px(a.width)),h=Math.round(px(a.height));
      rec.travel=Math.max(0,el.clientWidth-w-2*px(a.left));return {w,h,r:Math.min(w,h)/2}}
    const w=el.offsetWidth,h=el.offsetHeight,cs=getComputedStyle(el).borderTopLeftRadius,r=/%$/.test(cs)?px(cs)/100*Math.min(w,h):px(cs);
    return {w,h,r:Math.min(r,w/2,h/2)};
  }
  const inView=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>-80&&r.top<innerHeight+80&&r.right>-80&&r.left<innerWidth+80};
  function onResize(entries){
    for(const e of entries){const rec=L.recs.get(e.target);if(!rec)continue;
      const {w,h,r}=measure(rec),ok=w>=8&&h>=8&&!tooBig(w,h),key=ok?rec.p+"|"+w+"|"+h+"|"+Math.round(r):null;
      if(key!==rec.key){detach(rec);release(rec.key);rec.key=key;if(key&&L.opt)filterFor(key,rec.p,w,h,Math.round(r))}
      rec.vis=inView(rec.el)}
    assign();
  }
  function attach(rec){
    const f=L.filters.get(rec.key);if(!f||rec.att===rec.key)return;rec.att=rec.key;
    if(rec.p==="liquid-mercury")rec.el.style.setProperty("--lgf",`url(#${f.id}) saturate(160%)`);
    else rec.el.style.setProperty("backdrop-filter",`url(#${f.id}) saturate(160%)`,"important");
  }
  function detach(rec){if(!rec.att)return;rec.att=null;rec.el.style.removeProperty(rec.p==="liquid-mercury"?"--lgf":"backdrop-filter")}
  function assign(){
    let n=0;const c=cap();
    for(const rec of L.recs.values()){let want=L.on&&L.opt&&!!rec.key&&rec.vis;
      if(want&&rec.p==="subtle-pane"){if(n>=c)want=false;else n++}
      want?attach(rec):detach(rec)}
  }
  function track(el){
    if(L.recs.has(el))return;const p=presetOf(el);if(!p)return;
    if(p!=="liquid-mercury"){const up=el.parentElement&&el.parentElement.closest("[data-lgp]");if(up&&up.dataset.lgp!=="liquid-mercury")return}   // glass inside glass can't see the page
    const rec={el,p,key:null,att:null,vis:false};L.recs.set(el,rec);el.dataset.lgp=p;
    if(p==="liquid-mercury")mercInit(rec);
    L.ro.observe(el);L.io.observe(el);
  }
  function untrack(el){const rec=L.recs.get(el);if(!rec)return;detach(rec);release(rec.key);L.ro.unobserve(el);L.io.unobserve(el);if(rec.mo)rec.mo.disconnect();if(rec.raf)cancelAnimationFrame(rec.raf);
    ["--tx","--sx","--sy","--lx","--ly"].forEach(k=>el.style.removeProperty(k));el.removeAttribute("data-lgsp");el.removeAttribute("data-lgp");L.recs.delete(el)}
  function scan(root){if(!(root instanceof Element))return;if(root.matches(ALL))track(root);root.querySelectorAll(ALL).forEach(track)}
  function sweep(){for(const el of [...L.recs.keys()])if(!el.isConnected)untrack(el)}
  /* ---- switch thumbs: spring physics (stiffness 280, damping 22), stretch with speed, lean toward the pointer ---- */
  function mercInit(rec){rec.on=rec.el.classList.contains("on");rec.x=null;rec.v=0;rec.lean=0;rec.press=0;
    rec.mo=new MutationObserver(()=>{const on=rec.el.classList.contains("on");if(on!==rec.on){rec.on=on;spring(rec)}});rec.mo.observe(rec.el,{attributes:true,attributeFilter:["class"]})}
  function spring(rec){
    if(REDUCE||!L.on)return;
    if(rec.x==null)rec.x=rec.on?0:(rec.travel||20);   // just flipped: start from where the thumb was
    rec.el.setAttribute("data-lgsp","");rec.el.style.setProperty("--tx",rec.x.toFixed(2)+"px");if(!rec.raf){rec.t=performance.now();rec.raf=requestAnimationFrame(t=>step(rec,t))}
  }
  function step(rec,now){
    const el=rec.el,dt=Math.min(.05,Math.max(.001,(now-rec.t)/1000)),tgt=(rec.on?(rec.travel||20):0)+rec.lean,K=280,C=22,n=Math.ceil(dt/.004),h=dt/n;rec.t=now;
    for(let i=0;i<n;i++){const a=-K*(rec.x-tgt)-C*rec.v;rec.v+=a*h;rec.x+=rec.v*h}
    const st=Math.min(.3,Math.abs(rec.v)/560),pr=rec.press?.1:0;
    el.style.setProperty("--tx",rec.x.toFixed(2)+"px");el.style.setProperty("--sx",(1+st+pr).toFixed(3));el.style.setProperty("--sy",(1-st*.55+pr).toFixed(3));
    if(Math.abs(rec.x-tgt)<.04&&Math.abs(rec.v)<.4){rec.raf=0;
      if(!rec.lean&&!rec.press){rec.x=null;rec.v=0;["--tx","--sx","--sy"].forEach(k=>el.style.removeProperty(k));el.removeAttribute("data-lgsp")}
      return}
    rec.raf=requestAnimationFrame(t=>step(rec,t));
  }
  /* ---- pointer light: the highlight follows the pointer (only CSS variables change; no new maps) ---- */
  let pe=null,praf=0,lastT=null,pressT=null;
  function pstep(){praf=0;const e=pe;if(!e||!L.on)return;const tg=e.target instanceof Element?e.target:null;
    const g=tg&&tg.closest('[data-lgp]:not([data-lgp="liquid-mercury"])');
    if(g){const r=g.getBoundingClientRect();g.style.setProperty("--lx",Math.round(e.clientX-r.left)+"px");g.style.setProperty("--ly",Math.round(e.clientY-r.top)+"px")}
    const t=tg&&tg.closest('.tgl[data-lgp="liquid-mercury"]'),tr=t&&L.recs.get(t);
    if(lastT&&lastT!==tr&&lastT.lean){lastT.lean=0;if(lastT.x==null)lastT.x=lastT.on?(lastT.travel||20):0;spring(lastT)}
    lastT=tr||null;
    if(tr&&!REDUCE){const r=t.getBoundingClientRect(),c=r.left+r.width/2,lean=Math.max(-1,Math.min(1,(e.clientX-c)/(r.width/2)))*3;
      if(Math.abs(lean-tr.lean)>.15){tr.lean=lean;if(tr.x==null)tr.x=tr.on?(tr.travel||20):0;spring(tr)}}
  }
  document.addEventListener("pointermove",e=>{if(!L.on)return;pe=e;if(!praf)praf=requestAnimationFrame(pstep)},{passive:true});
  document.addEventListener("pointerdown",e=>{if(!L.on||REDUCE)return;const t=e.target instanceof Element&&e.target.closest('.tgl[data-lgp="liquid-mercury"]'),tr=t&&L.recs.get(t);
    if(tr){pressT=tr;tr.press=1;if(tr.x==null)tr.x=tr.on?(tr.travel||20):0;spring(tr)}},{passive:true});
  const unpress=()=>{if(pressT){const tr=pressT;pressT=null;tr.press=0;if(tr.x==null)tr.x=tr.on?(tr.travel||20):0;spring(tr)}};
  document.addEventListener("pointerup",unpress,{passive:true});document.addEventListener("pointercancel",unpress,{passive:true});
  function enable(){
    if(L.on)return;L.on=true;
    L.ro=new ResizeObserver(onResize);
    L.io=new IntersectionObserver(es=>{let ch=false;for(const e of es){const rec=L.recs.get(e.target);if(rec&&rec.vis!==e.isIntersecting){rec.vis=e.isIntersecting;ch=true}}if(ch)assign()},{rootMargin:"80px"});
    L.mo=new MutationObserver(ms=>{let rm=false;for(const m of ms){m.addedNodes.forEach(n=>scan(n));if(m.removedNodes.length)rm=true}if(rm)sweep()});
    L.mo.observe(document.body,{childList:true,subtree:true});
    scan(document.body);
  }
  function disable(){
    if(!L.on)return;L.on=false;L.mo.disconnect();
    for(const el of [...L.recs.keys()])untrack(el);
    L.ro.disconnect();L.io.disconnect();
    for(const f of L.filters.values())f.node.remove();L.filters.clear();
  }
  return {enable,disable,get optical(){return L.opt},get active(){return L.on},_L:L};
})();
function glassOn(){return document.documentElement.classList.contains("lf-glass")}
function setGlass(on,save){
  on=!!on;document.documentElement.classList.toggle("lf-glass",on);
  try{localStorage.setItem("lf_glass",on?"1":"0")}catch(e){}
  if(save&&S.ready)setP("glass",on);
  on?LG.enable():LG.disable();paintGlassSwitch();
}
function paintGlassSwitch(){const b=$("#lgTgl");if(!b)return;const on=glassOn();b.classList.toggle("on",on);b.setAttribute("aria-checked",on)}
function glassRowHTML(){
  return `<div class="lfg-row"><div><b>Liquid glass</b><div class="note">${LG.optical?"Panels, buttons and pop-ups turn into real glass that bends the light behind it. Works with every theme.":"Panels, buttons and pop-ups turn into frosted glass. The light-bending edges need the Leafline app, Chrome or Edge."}</div></div><button type="button" class="tgl" id="lgTgl" role="switch" aria-checked="false" aria-label="Liquid glass"></button></div>`;
}
function wireGlassSwitch(root){const b=$("#lgTgl",root);if(!b)return;paintGlassSwitch();b.onclick=()=>setGlass(!glassOn(),true)}
if(glassOn())LG.enable();
'''


def inject(ui):
    """Adds the optional liquid glass look to the shared page."""
    head_at, css_at, js_at = "<style>\n@font-face", "</style>\n</head>", "</script>\n</body>"
    assert ui.count(head_at) == 1 and ui.count(css_at) == 1 and ui.count(js_at) == 1
    return (ui.replace(head_at, GLASS_HEAD + head_at, 1)
              .replace(css_at, GLASS_CSS + css_at, 1)
              .replace(js_at, GLASS_JS + js_at, 1))
