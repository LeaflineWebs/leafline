"""Leafline Messages (11.4): the styles and page code for team chat. They are added to the shared page (UI_HTML),
so the desktop app and the website get the same Messages. Every rule (who can read, post, edit, remove...) is
enforced by the database (supabase/migrations/20261108000008_messaging.sql); this is only the interface."""

MSG_CSS = r'''
/* ================= Messages ================= */
#pg-msgs{padding:0;overflow:hidden}
#pg-msgs.on{display:block}
.mx{position:absolute;inset:0;display:grid;grid-template-columns:320px minmax(0,1fr) 0px;gap:0;padding:6px 18px 104px 22px;transition:grid-template-columns var(--d-card) var(--e-out)}
.mx.info{grid-template-columns:320px minmax(0,1fr) 300px}
.mx>*{min-width:0;min-height:0}
.mx-list{display:flex;flex-direction:column;padding-right:14px;border-right:1px solid var(--line)}
.mx-lh{display:flex;align-items:center;gap:8px;padding:6px 2px 10px}
.mx-lh h3{font-size:18px;font-weight:800;letter-spacing:-.2px;margin-right:auto}
.mx-ib{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;color:var(--text2);position:relative;transition:background-color var(--d-hover) var(--e-out),color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.mx-ib:hover{background:rgba(255,255,255,.06);color:var(--text)}.mx-ib:active{transform:scale(.92)}
.mx-ib .ic{width:19px;height:19px}.mx-ib.on{color:var(--accent-hi);background:var(--accent-soft)}
.mx-ib .nb{position:absolute;top:2px;right:2px;min-width:16px;height:16px;padding:0 4px;border-radius:8px;background:var(--accent);color:var(--accent-text);font-size:10.5px;font-weight:800;display:grid;place-items:center}
.mx-srch{position:relative;margin-bottom:10px}
.mx-srch input{width:100%;height:38px;border-radius:12px;background:rgba(0,0,0,.22);border:1px solid var(--line);padding:0 12px 0 36px;font-size:14px;outline:none;transition:border-color var(--d-hover) var(--e-out),background-color var(--d-hover) var(--e-out)}
.mx-srch input:focus{border-color:var(--accent-line);background:rgba(0,0,0,.3)}
.mx-srch .ic{position:absolute;left:11px;top:10px;width:18px;height:18px;color:var(--muted)}
.mx-tabs{display:flex;gap:4px;margin-bottom:8px;padding:3px;border-radius:12px;background:rgba(0,0,0,.18)}
.mx-tabs button{flex:1;height:30px;border-radius:9px;font-size:12.5px;font-weight:700;color:var(--muted);display:inline-flex;align-items:center;justify-content:center;gap:6px;transition:background-color var(--d-hover) var(--e-out),color var(--d-hover) var(--e-out)}
.mx-tabs button.on{background:var(--card2);color:var(--text);box-shadow:0 2px 8px rgba(0,0,0,.25)}
.mx-tabs button b{min-width:17px;height:17px;padding:0 5px;border-radius:9px;background:var(--accent);color:var(--accent-text);font-size:10.5px;display:grid;place-items:center}
.mx-cl{flex:1;overflow-y:auto;overscroll-behavior:contain;margin:0 -6px;padding:0 6px 8px}
.mx-sec{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--faint);padding:12px 8px 6px}
.mx-c{width:100%;display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:4px 11px;align-items:center;padding:9px 9px;border-radius:14px;text-align:left;position:relative;transition:background-color var(--d-hover) var(--e-out)}
.mx-c:hover{background:rgba(255,255,255,.04)}.mx-c.on{background:var(--accent-soft)}
.mx-c .mav{grid-row:1/3}
.mx-c .nm{font-size:14px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:flex;align-items:center;gap:6px}
.mx-c .nm .ic{width:13px;height:13px;color:var(--faint);flex:none}
.mx-c .mxt{font-size:11.5px;color:var(--faint);font-weight:600;justify-self:end}
.mx-c .pv{font-size:13px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mx-c.un .nm{color:#fff}.mx-c.un .pv{color:var(--text2);font-weight:600}
.mx-c .bd{justify-self:end;display:flex;gap:4px;align-items:center}
.mx-c .bd b{min-width:19px;height:19px;padding:0 6px;border-radius:10px;background:var(--accent);color:var(--accent-text);font-size:11px;font-weight:800;display:grid;place-items:center}
.mx-c .bd b.at{background:#F2D88C;color:#2a1f05}
.mx-c.mute .bd b{background:var(--card3);color:var(--text2)}
.mx-c .pv .ty{color:var(--accent-hi);font-weight:600}
.mav{position:relative;display:block;width:44px;height:44px;flex:none}
.mav .tav{width:100%;height:100%;font-size:15px}
.mav.sm{width:30px;height:30px}.mav.sm .tav{font-size:11.5px}
.mav.xs{width:22px;height:22px}.mav.xs .tav{font-size:9px;box-shadow:none}
.mav.big{width:72px;height:72px}.mav.big .tav{font-size:24px}
.mav .od{position:absolute;right:-1px;bottom:-1px;width:13px;height:13px;border-radius:50%;background:#56685d;border:2.5px solid var(--bg)}
.mav .od.on{background:var(--g)}
.mav.sm .od{width:10px;height:10px;border-width:2px}
.gav{width:100%;height:100%;border-radius:15px;display:grid;place-items:center;font-weight:800;font-size:15px;color:var(--accent-hi);background:linear-gradient(150deg,var(--card3),var(--av-bg));overflow:hidden;box-shadow:0 0 0 2px rgba(255,255,255,.08)}
.gav img{width:100%;height:100%;object-fit:cover}
.mav.big .gav{border-radius:24px;font-size:24px}
.mx-empty{display:grid;place-items:center;text-align:center;gap:10px;padding:40px 20px;color:var(--muted);font-size:13.5px;line-height:1.5}
.mx-empty .bub{width:60px;height:60px;border-radius:20px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-hi)}
.mx-empty .bub .ic{width:28px;height:28px}
.mx-empty b{color:var(--text);font-size:15.5px}
/* chat */
.mx-chat{display:flex;flex-direction:column;position:relative;padding-left:4px}
.mx-ch{display:flex;align-items:center;gap:12px;padding:6px 6px 12px 18px;border-bottom:1px solid var(--line)}
.mx-ch .tt{min-width:0;flex:1;cursor:pointer}
.mx-ch h4{font-size:16px;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mx-ch .sub{font-size:12.5px;color:var(--muted);margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mx-ch .sub .onl{color:var(--accent-hi)}
.mx-back{display:none}
.mx-scroll{flex:1;overflow-y:auto;overscroll-behavior:contain;padding:14px 18px 8px;scroll-behavior:auto}
.mx-day{display:flex;align-items:center;gap:12px;margin:16px 0 10px;color:var(--faint);font-size:11.5px;font-weight:700;letter-spacing:.3px}
.mx-day:before,.mx-day:after{content:"";flex:1;height:1px;background:var(--line)}
.mx-sys{text-align:center;font-size:12.5px;color:var(--muted);margin:10px 0;padding:0 20px}
.mx-sys b{color:var(--text2)}
.mx-more{display:block;margin:4px auto 10px;font-size:12.5px;color:var(--muted);padding:6px 12px;border-radius:10px}
.mx-more:hover{background:rgba(255,255,255,.05);color:var(--text)}
.mm{display:grid;grid-template-columns:34px minmax(0,1fr);gap:0 10px;margin-top:12px;position:relative}
.mm.cont{margin-top:3px}.mm.cont .mm-av,.mm.cont .mm-h{display:none}
.mm.me{grid-template-columns:minmax(0,1fr)}.mm.me .mm-av{display:none}
.mm-av{grid-row:1/9;align-self:start;padding-top:20px}
.mm.cont .mm-av{padding-top:0}
.mm-h{font-size:12.5px;color:var(--muted);margin:0 0 3px 4px;display:flex;gap:8px;align-items:baseline}
.mm-h b{color:var(--text2);font-size:13px;cursor:pointer}
.mm.me .mm-h{justify-content:flex-end;margin:0 4px 3px 0}.mm.me .mm-h b{display:none}
.mm-col{grid-column:2;display:flex;flex-direction:column;align-items:flex-start;min-width:0}
.mm.me .mm-col{grid-column:1}
.mm.me .mm-col{align-items:flex-end}
.mb{max-width:min(620px,86%);padding:9px 13px;border-radius:18px 18px 18px 6px;background:var(--card2);font-size:14.5px;line-height:1.48;overflow-wrap:anywhere;position:relative;box-shadow:0 1px 0 rgba(255,255,255,.03) inset}
.mm.cont .mb{border-radius:6px 18px 18px 6px}
.mm.me .mb{background:linear-gradient(160deg,rgba(74,222,139,.24),rgba(47,191,113,.18));border-radius:18px 18px 6px 18px;color:#F2FFF7}
.mm.me.cont .mb{border-radius:18px 6px 6px 18px}
.mm.atme .mb{box-shadow:inset 3px 0 0 #F2D88C;background:rgba(242,216,140,.10)}
.mm.del .mb{background:none;border:1px dashed var(--line2);color:var(--faint);font-style:italic}
.mm.flash .mb{animation:mxFlash 1.6s var(--e-out)}
@keyframes mxFlash{0%,30%{box-shadow:0 0 0 2px var(--accent),0 0 30px var(--glow)}100%{box-shadow:none}}
.mm.pend .mb{opacity:.7}
.mb p{margin:0}.mb p+p{margin-top:6px}
.mb ul{margin:4px 0 0;padding-left:18px}.mb li{margin:1px 0}
.mb code{font-family:ui-monospace,Consolas,monospace;font-size:.88em;padding:1px 5px;border-radius:6px;background:rgba(0,0,0,.32)}
.mb pre{margin:6px 0 0;padding:9px 11px;border-radius:10px;background:rgba(0,0,0,.32);overflow-x:auto;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;white-space:pre}
.mb a{color:var(--accent-hi);text-decoration:underline;text-underline-offset:2px}
.mb .ment,.mb .ment.ev{cursor:pointer}
.mb .ment.ev{color:#F2D88C;background:rgba(233,193,90,.14);box-shadow:inset 0 0 0 1px rgba(233,193,90,.4)}
.mb .ed{font-size:11px;color:var(--faint);margin-left:6px;font-style:normal}
.mb.only-emoji{background:none!important;box-shadow:none!important;font-size:34px;line-height:1.15;padding:2px 2px}
.mm-rp{display:flex;align-items:center;gap:7px;max-width:min(520px,80%);font-size:12.5px;color:var(--muted);padding:4px 10px 6px;margin-bottom:-2px;cursor:pointer;border-left:2px solid var(--line2);border-radius:2px;margin-left:8px;overflow:hidden}
.mm-rp b{color:var(--text2);flex:none}.mm-rp span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mm-rp:hover{color:var(--text2);border-left-color:var(--accent)}
.mm.me .mm-rp{margin:0 8px -2px 0;border-left:0;border-right:2px solid var(--line2)}
.mm-files{display:flex;flex-wrap:wrap;gap:6px;margin-top:5px;max-width:min(620px,86%)}
.mm.me .mm-files{justify-content:flex-end}
.mm-img{display:block;border-radius:14px;overflow:hidden;background:rgba(0,0,0,.25);max-width:280px;max-height:260px;min-width:90px;min-height:70px;cursor:zoom-in;border:1px solid var(--line)}
.mm-img img{display:block;max-width:280px;max-height:260px;object-fit:cover}
.mm-file{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:14px;background:var(--card2);border:1px solid var(--line);min-width:200px;max-width:300px;transition:border-color var(--d-hover) var(--e-out),transform var(--d-card) var(--e-spring)}
.mm-file:hover{border-color:var(--accent-line);transform:translateY(-1px)}
.mm-file .fi{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-hi);font-size:10px;font-weight:800;flex:none}
.mm-file .fn{min-width:0;flex:1}.mm-file .fn b{display:block;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mm-file .fn span{font-size:11.5px;color:var(--muted)}
.mm-file .ic{width:18px;height:18px;color:var(--muted)}
.mm-rx{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.mm-rx button{height:26px;padding:0 8px;border-radius:13px;background:rgba(0,0,0,.2);border:1px solid var(--line);font-size:13px;display:inline-flex;align-items:center;gap:5px;transition:transform var(--d-card) var(--e-spring),border-color var(--d-hover) var(--e-out),background-color var(--d-hover) var(--e-out)}
.mm-rx button b{font-size:11.5px;color:var(--text2)}
.mm-rx button.on{background:var(--accent-soft);border-color:var(--accent-line)}.mm-rx button.on b{color:var(--accent-hi)}
.mm-rx button:hover{transform:translateY(-1px);border-color:var(--line2)}.mm-rx button.pulse{animation:rxp 420ms var(--e-bounce)}
.mm-st{font-size:11px;color:var(--faint);margin:3px 6px 0;display:flex;gap:6px;align-items:center}
.mm-st.bad{color:#FF9AA0}.mm-st button{color:var(--accent-hi);font-weight:700;text-decoration:underline}
.mm-st .rd{display:inline-flex;gap:-4px}.mm-st .rd .mav.xs{margin-left:-5px}
.mm-pin{font-size:11px;color:#F2D88C;margin:2px 6px 0;display:flex;align-items:center;gap:4px}.mm-pin .ic{width:12px;height:12px}
.mm-act{position:absolute;top:-14px;right:8px;display:flex;gap:2px;padding:3px;border-radius:12px;background:var(--card3);border:1px solid var(--line2);box-shadow:0 8px 22px rgba(0,0,0,.4);opacity:0;pointer-events:none;transform:translateY(4px);transition:opacity var(--d-micro) var(--e-out),transform var(--d-micro) var(--e-out);z-index:3}
.mm.me .mm-act{right:auto;left:8px}
.mm:hover .mm-act,.mm.act .mm-act{opacity:1;pointer-events:auto;transform:none}
.mm-act button{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;font-size:15px;color:var(--text2)}
.mm-act button:hover{background:rgba(255,255,255,.08);color:#fff}.mm-act .ic{width:16px;height:16px}
.mm-act .sep{width:1px;background:var(--line2);margin:5px 2px}
.mx-typ{height:20px;padding:0 22px;font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:8px}
.mx-typ .dots{display:inline-flex;gap:3px}.mx-typ .dots i{width:5px;height:5px;border-radius:50%;background:var(--accent-hi);animation:mxDot 1.2s infinite ease-in-out}
.mx-typ .dots i:nth-child(2){animation-delay:.15s}.mx-typ .dots i:nth-child(3){animation-delay:.3s}
@keyframes mxDot{0%,60%,100%{opacity:.25;transform:none}30%{opacity:1;transform:translateY(-3px)}}
.mx-new{position:absolute;left:50%;bottom:150px;transform:translateX(-50%);padding:7px 14px;border-radius:16px;background:var(--accent);color:var(--accent-text);font-size:12.5px;font-weight:800;box-shadow:0 8px 20px var(--glow-soft);z-index:4;animation:fadeup .3s var(--e-out)}
/* composer */
.mx-comp{margin:2px 10px 0 14px;border-radius:18px;background:var(--card);border:1px solid var(--line2);box-shadow:0 10px 30px rgba(0,0,0,.25);transition:border-color var(--d-hover) var(--e-out)}
.mx-comp:focus-within{border-color:var(--accent-line)}
.mx-comp.drag{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.mx-rpl{display:flex;align-items:center;gap:8px;padding:8px 12px 0;font-size:12.5px;color:var(--muted)}
.mx-rpl .ic{width:15px;height:15px;color:var(--accent-hi)}.mx-rpl span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mx-rpl b{color:var(--text2)}
.mx-rpl button{width:24px;height:24px;border-radius:8px;display:grid;place-items:center}.mx-rpl button:hover{background:rgba(255,255,255,.07)}
.mx-att{display:flex;flex-wrap:wrap;gap:6px;padding:8px 10px 0}
.mx-att .mxch{display:flex;align-items:center;gap:8px;padding:5px 6px 5px 9px;border-radius:11px;background:rgba(0,0,0,.25);border:1px solid var(--line);font-size:12.5px;max-width:240px;position:relative;overflow:hidden}
.mx-att .mxch span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mx-att .mxch small{color:var(--muted);flex:none}
.mx-att .mxch button{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;flex:none}.mx-att .mxch button:hover{background:rgba(255,255,255,.08)}
.mx-att .mxch i.pg{position:absolute;left:0;bottom:0;height:2px;background:var(--accent);transition:width .2s linear}
.mx-att .mxch.bad{border-color:rgba(255,107,112,.5);color:#FF9AA0}
.mx-att .mxch img{width:26px;height:26px;border-radius:6px;object-fit:cover}
.mx-ta{display:block;width:100%;resize:none;border:0;outline:none;background:none;padding:11px 14px 4px;font-size:14.5px;line-height:1.45;max-height:200px;min-height:42px;overflow-y:auto}
.mx-tb{display:flex;align-items:center;gap:2px;padding:4px 6px 6px}
.mx-tb .mx-ib{width:32px;height:32px;border-radius:10px}.mx-tb .mx-ib .ic{width:17px;height:17px}
.mx-tb .fmt{font-weight:800;font-size:13.5px;font-family:inherit}
.mx-tb .sp{flex:1}
.mx-tb .hint{font-size:11px;color:var(--faint);margin-right:8px}
.mx.info .mx-tb .hint{display:none}
.mx-tabs button{white-space:nowrap}
.mx-send{height:34px;padding:0 14px;border-radius:12px;background:var(--accent);color:var(--accent-text);font-weight:800;font-size:13.5px;display:inline-flex;align-items:center;gap:6px;transition:transform var(--d-card) var(--e-spring),opacity var(--d-hover) var(--e-out),box-shadow var(--d-hover) var(--e-out)}
.mx-send:not([disabled]):hover{box-shadow:0 6px 18px var(--glow-soft);transform:translateY(-1px)}.mx-send:active{transform:scale(.95)}
.mx-send[disabled]{opacity:.4;cursor:default}
.mx-send .ic{width:16px;height:16px}
.mx-ro{margin:6px 14px 0;padding:12px 16px;border-radius:14px;background:rgba(0,0,0,.2);color:var(--muted);font-size:13px;text-align:center}
/* details panel */
.mx-info{overflow:hidden;border-left:1px solid var(--line)}
.mx-info>div{width:300px;height:100%;overflow-y:auto;padding:4px 4px 20px 18px}
.mx-ih{display:flex;align-items:center;justify-content:space-between;padding:6px 0 10px}
.mx-ih h4{font-size:14px;font-weight:800}
.mx-pf{display:grid;justify-items:center;text-align:center;gap:6px;padding:8px 0 14px;border-bottom:1px solid var(--line)}
.mx-pf h3{font-size:17px;font-weight:800;margin-top:4px}
.mx-pf .sub{font-size:12.5px;color:var(--muted)}
.mx-pf .ds{font-size:13px;color:var(--text2);line-height:1.5;white-space:pre-wrap}
.mx-pf .acts{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;justify-content:center}
.mx-blk{padding:12px 0;border-bottom:1px solid var(--line)}
.mx-blk h5{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:var(--faint);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.mx-blk h5 button{font-size:11.5px;letter-spacing:0;text-transform:none;color:var(--accent-hi);font-weight:700}
.mx-mem{display:flex;align-items:center;gap:10px;padding:6px 4px;border-radius:12px}
.mx-mem:hover{background:rgba(255,255,255,.03)}
.mx-mem .nm{flex:1;min-width:0;font-size:13.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
.mx-mem small{font-size:11px;color:var(--muted);font-weight:600}
.mx-mem .rm{width:26px;height:26px;border-radius:8px;display:grid;place-items:center;color:var(--faint);opacity:0}
.mx-mem:hover .rm{opacity:1}.mx-mem .rm:hover{color:#FF9AA0;background:rgba(255,107,112,.12)}
.mx-pinr{display:block;width:100%;text-align:left;padding:8px 10px;border-radius:12px;background:rgba(0,0,0,.16);margin-bottom:6px;font-size:12.5px;transition:background-color var(--d-hover) var(--e-out)}
.mx-pinr:hover{background:rgba(0,0,0,.28)}.mx-pinr b{display:block;font-size:12px;color:var(--text2);margin-bottom:2px}
.mx-pinr span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:var(--muted)}
.mx-fl{display:flex;align-items:center;gap:9px;padding:6px 4px;border-radius:10px;font-size:12.5px;width:100%;text-align:left}
.mx-fl:hover{background:rgba(255,255,255,.04)}.mx-fl .fi{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-hi);font-size:9px;font-weight:800;flex:none}
.mx-fl span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mx-fl small{color:var(--faint)}
.mx-tog{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:7px 4px;font-size:13.5px;font-weight:600}
.mx-danger{color:#FF9AA0!important}
/* popovers: emoji picker, mention list, notifications */
.mx-pop{position:fixed;z-index:80;background:var(--card);border:1px solid var(--line2);border-radius:18px;box-shadow:0 24px 60px rgba(0,0,0,.55);animation:mpin .18s var(--e-out)}
.mx-emo{width:328px;padding:10px}
.mx-emo input{width:100%;height:34px;border-radius:10px;background:rgba(0,0,0,.25);border:1px solid var(--line);padding:0 10px;font-size:13.5px;outline:none;margin-bottom:8px}
.mx-emo .cats{display:flex;gap:2px;margin-bottom:6px}
.mx-emo .cats button{flex:1;height:30px;border-radius:9px;font-size:16px;opacity:.6;transition:opacity var(--d-hover),background-color var(--d-hover)}
.mx-emo .cats button.on,.mx-emo .cats button:hover{opacity:1;background:rgba(255,255,255,.06)}
.mx-emo .grid{display:grid;grid-template-columns:repeat(8,1fr);gap:2px;height:232px;overflow-y:auto;align-content:start}
.mx-emo .grid h6{grid-column:1/-1;font-size:10.5px;font-weight:800;color:var(--faint);text-transform:uppercase;letter-spacing:.5px;padding:6px 2px 2px}
.mx-emo .grid button{height:36px;border-radius:9px;font-size:21px;transition:background-color var(--d-micro),transform var(--d-card) var(--e-spring)}
.mx-emo .grid button:hover{background:rgba(255,255,255,.08);transform:scale(1.12)}
.mx-emo .quick{display:flex;justify-content:space-between;padding:0 2px 8px;margin-bottom:6px;border-bottom:1px solid var(--line)}
.mx-emo .quick button{width:34px;height:34px;border-radius:10px;font-size:20px}.mx-emo .quick button:hover{background:rgba(255,255,255,.08)}
.mx-emo .none{grid-column:1/-1;padding:20px;text-align:center;color:var(--muted);font-size:13px}
.mx-mp{width:260px;padding:6px;max-height:300px;overflow-y:auto}
.mx-mp button{display:flex;align-items:center;gap:10px;width:100%;padding:7px 8px;border-radius:11px;text-align:left;font-size:13.5px;font-weight:600}
.mx-mp button.on,.mx-mp button:hover{background:var(--accent-soft)}
.mx-mp small{margin-left:auto;font-size:11px;color:var(--muted);font-weight:600}
.mx-nt{width:360px;max-height:min(520px,70vh);display:flex;flex-direction:column}
.mx-nt .hd{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px;border-bottom:1px solid var(--line)}
.mx-nt .hd b{font-size:15px}.mx-nt .hd button{font-size:12.5px;color:var(--accent-hi);font-weight:700}
.mx-nt .mxls{overflow-y:auto;padding:6px}
.mx-nt .it{display:flex;gap:10px;width:100%;text-align:left;padding:9px 10px;border-radius:12px;position:relative}
.mx-nt .it:hover{background:rgba(255,255,255,.04)}
.mx-nt .it.un:after{content:"";position:absolute;right:10px;top:16px;width:8px;height:8px;border-radius:50%;background:var(--accent)}
.mx-nt .it .tx{min-width:0;flex:1;font-size:13px;line-height:1.4;padding-right:12px}
.mx-nt .it .tx b{color:var(--text)}.mx-nt .it .tx span{display:block;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mx-nt .it small{display:block;font-size:11px;color:var(--faint);margin-top:2px}
.mx-nt .ft{padding:10px 16px;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;font-size:12.5px;color:var(--muted)}
/* new chat dialog */
.mx-pick{display:grid;gap:4px;max-height:300px;overflow-y:auto;margin:10px -4px 0;padding:0 4px}
.mx-pick button{display:flex;align-items:center;gap:11px;padding:8px 10px;border-radius:13px;text-align:left;transition:background-color var(--d-hover) var(--e-out)}
.mx-pick button:hover{background:rgba(255,255,255,.04)}
.mx-pick button .nm{flex:1;font-size:14px;font-weight:600}.mx-pick button .nm small{display:block;font-size:12px;color:var(--muted);font-weight:500}
.mx-pick .ck{width:22px;height:22px;border-radius:50%;border:2px solid var(--faint);display:grid;place-items:center;color:transparent;transition:all .25s var(--e-spring)}
.mx-pick button.on .ck{background:var(--accent);border-color:var(--accent);color:var(--accent-text);transform:scale(1.06)}
.mx-pick .ck .ic{width:13px;height:13px}
.mx-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;min-height:0}
.mx-chips span{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 6px 0 4px;border-radius:14px;background:var(--accent-soft);font-size:12.5px;font-weight:700;color:var(--accent-hi);animation:clChip .3s var(--e-spring)}
.mx-chips span .mav.xs{width:20px;height:20px}
.mx-seg{display:flex;gap:4px;padding:3px;border-radius:12px;background:rgba(0,0,0,.2);margin:14px 0 4px}
.mx-seg button{flex:1;height:34px;border-radius:9px;font-size:13px;font-weight:700;color:var(--muted)}
.mx-seg button.on{background:var(--card2);color:var(--text)}
.mx-light{position:fixed;inset:0;z-index:90;background:rgba(0,0,0,.86);display:grid;place-items:center;animation:fadeup .2s var(--e-out);cursor:zoom-out}
.mx-light img{max-width:92vw;max-height:84vh;border-radius:12px;box-shadow:0 30px 80px rgba(0,0,0,.6)}
.mx-light .mxbar{position:absolute;top:16px;right:16px;display:flex;gap:8px}
.mx-res{display:block;width:100%;text-align:left;padding:9px 10px;border-radius:12px;font-size:13px}
.mx-res:hover{background:rgba(255,255,255,.04)}
.mx-res .h{display:flex;gap:8px;align-items:baseline;font-size:12px;color:var(--muted)}.mx-res .h b{color:var(--text2);font-size:12.5px}
.mx-res .t{color:var(--text2);overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-top:2px}
.mx-res mark{background:rgba(242,216,140,.3);color:#fff;border-radius:3px;padding:0 1px}
.mx-banner{margin:0 0 8px;padding:8px 12px;border-radius:12px;font-size:12.5px;display:flex;gap:8px;align-items:center;background:rgba(233,193,90,.12);color:#F2D88C}
.mx-banner.bad{background:rgba(255,107,112,.12);color:#FF9AA0}
.mx-sk{display:grid;gap:14px;padding:16px 18px}
.mx-sk i{display:block;height:42px;border-radius:16px;width:60%;background:linear-gradient(90deg,rgba(255,255,255,.04),rgba(255,255,255,.09),rgba(255,255,255,.04));background-size:200% 100%;animation:slide 1.3s linear infinite}
.mx-sk i:nth-child(2n){width:42%;justify-self:end}.mx-sk i:nth-child(3){width:70%}
.nv .badge.at{background:#F2D88C;color:#2a1f05}
@media (max-width:1180px){.mx.info{grid-template-columns:290px minmax(0,1fr) 0px}.mx{grid-template-columns:290px minmax(0,1fr) 0}.mx.info .mx-info{position:absolute;right:0;top:0;bottom:96px;width:310px;background:var(--panel);z-index:6;box-shadow:-20px 0 40px rgba(0,0,0,.35);border-radius:22px 0 0 22px}}
/* phones: one panel at a time, like Messages on a phone */
@media (max-width:860px){
  .mx,.mx.info{grid-template-columns:minmax(0,1fr);padding:4px 16px calc(96px + env(safe-area-inset-bottom))}
  .mx-list{padding-right:0;border-right:0}
  .mx .mx-chat,.mx .mx-info{display:none}
  .mx.chat .mx-list{display:none}.mx.chat .mx-chat{display:flex}
  .mx.chat{padding:0 0 calc(8px + env(safe-area-inset-bottom))}
  body.msg-chat .fnav{transform:translateY(140%);transition:transform var(--d-card) var(--e-out)}
  body.msg-chat .top{display:none}
  .mx-back{display:grid}
  .mx-ch{padding:calc(8px + env(safe-area-inset-top)) 10px 10px;gap:8px;background:var(--panel)}
  .mx-scroll{padding:10px 12px 6px}
  .mx-comp{margin:2px 8px 0}
  .mx-tb .hint,.mx-tb .fmt.hx{display:none}
  .mx-new{bottom:120px}
  .mx.info .mx-info{display:block;position:fixed;inset:0;z-index:70;background:var(--bg);border:0;width:auto;border-radius:0;animation:fadeup .25s var(--e-out)}
  .mx.info .mx-info>div{width:auto;padding:calc(10px + env(safe-area-inset-top)) 18px 40px}
  .mb{max-width:88%;font-size:15px}
  .mm-act{top:-40px}
  .mx-pop.mx-emo{left:8px!important;right:8px;width:auto;top:auto!important;bottom:calc(10px + env(safe-area-inset-bottom))}
  .mx-pop.mx-nt{left:8px!important;right:8px;width:auto}
  .mx-c{padding:10px 8px}
  .mx-mem .rm{opacity:1}
  .mx-ta{font-size:16px}
  .mx-srch input{font-size:16px;height:42px}
  .mx-tabs button{height:38px}
  .mx-tb .mx-ib{width:40px;height:40px}.mx-send{height:40px;padding:0 16px}
  .mm-act button{width:38px;height:38px;font-size:17px}
  .mx-blk h5 button{padding:8px 4px;margin:-8px -4px}
  .mx-ib{width:40px;height:40px}
  .mx-mem{padding:8px 4px}.mx-mem .rm{width:36px;height:36px}
  .mx-seg button{height:40px}
}
'''

MSG_EMOJI = (
    "Smileys|😀 grin happy|😃 smile|😄 laugh|😁 beam|😆 lol|😅 sweat|🤣 rofl|😂 joy tears laugh|🙂 slight|🙃 upside|😉 wink|😊 blush|😇 angel|🥰 love|😍 heart eyes|🤩 star struck|😘 kiss|😋 yum|😛 tongue|😜 crazy|🤪 zany|😝 squint|🤑 money|🤗 hug|🤭 oops|🤫 shh|🤔 think|🤐 zip|🤨 doubt|😐 neutral|😑 blank|😶 silent|😏 smirk|😒 unamused|🙄 eye roll|😬 grimace|😌 relieved|😔 pensive|😪 sleepy|🤤 drool|😴 sleep|😷 mask|🤒 sick|🥵 hot|🥶 cold|🥴 woozy|😵 dizzy|🤯 mind blown|🤠 cowboy|🥳 party|😎 cool sunglasses|🤓 nerd|🧐 monocle|😕 confused|😟 worried|🙁 frown|😮 wow|😯 hushed|😲 astonished|😳 flushed|🥺 pleading|😦 frowning|😧 anguished|😨 fearful|😰 anxious|😥 sad relieved|😢 cry|😭 sob|😱 scream|😖 confounded|😣 persevere|😞 disappointed|😓 downcast|😩 weary|😫 tired|🥱 yawn|😤 triumph|😡 angry|😠 mad|🤬 swear|💀 skull dead|👻 ghost|🤖 robot|😺 cat",
    "Gestures|👍 thumbs up yes|👎 thumbs down no|👌 ok|🤌 pinch|✌️ peace|🤞 fingers crossed luck|🤟 love you|🤘 rock|🤙 call me|👈 left|👉 right|👆 up|👇 down|☝️ point|✋ hand stop|🤚 raised|🖐️ five|🖖 vulcan|👋 wave hi bye|👏 clap|🙌 raise hands|👐 open hands|🤲 palms|🤝 handshake deal|🙏 pray thanks please|✍️ write|💪 strong muscle|🦾 arm|🧠 brain|👀 eyes look|👁️ eye|👂 ear|🫡 salute|🫶 heart hands",
    "Work|📞 phone call|☎️ telephone|📱 mobile|💻 laptop|🖥️ computer|⌨️ keyboard|📧 email|📨 incoming|📩 envelope|📅 calendar date|📆 schedule|🗓️ planner|📈 chart up growth|📉 chart down|📊 bar chart stats|📋 clipboard|📌 pin|📍 location|📎 paperclip|✂️ scissors|🗂️ folders|📁 folder|📄 document page|📝 memo note|✏️ pencil|🖊️ pen|💼 briefcase|🗃️ file box|🔍 search|💡 idea bulb|🔔 bell|📣 announce|📢 loudspeaker|⏰ alarm|⏳ hourglass|⌛ time|✅ check done|☑️ checkbox|✔️ tick|❌ cross no|⚠️ warning|❗ important|❓ question|🔥 fire hot|⭐ star|🌟 glow star|✨ sparkles|💯 hundred|🎯 target goal|🚀 rocket launch|⚡ lightning fast|🔑 key|🔒 lock|🛠️ tools|⚙️ gear settings|🏆 trophy win|🥇 gold first|🥈 silver|🥉 bronze|🏅 medal",
    "Money|💰 money bag|💵 dollar cash|💸 money flying|💳 card|🧾 receipt|🏦 bank|💎 diamond|🤑 rich|📦 package|🛒 cart|🏠 house home|🏢 office building|🏗️ construction|🔨 hammer|🪚 saw|🧰 toolbox|🚚 truck|🚗 car|✈️ plane|🗺️ map",
    "Celebrate|🎉 party tada|🎊 confetti|🥂 cheers|🍾 champagne|🎂 cake birthday|🎁 gift|🎈 balloon|🏁 finish|🙌 hooray|🤩 excited|🥳 celebrate|👑 crown king|💥 boom|🎶 music|🍕 pizza|🍔 burger|🌮 taco|🍩 donut|☕ coffee|🍺 beer|🧃 juice|🍿 popcorn|🍎 apple",
    "Hearts|❤️ red heart love|🧡 orange heart|💛 yellow heart|💚 green heart|💙 blue heart|💜 purple heart|🖤 black heart|🤍 white heart|🤎 brown heart|💔 broken heart|❣️ exclamation heart|💕 two hearts|💞 revolving|💓 beating|💗 growing|💖 sparkling|💘 arrow|💝 ribbon|💯 hundred|💢 anger|💬 speech|🗯️ anger bubble|💭 thought",
    "Nature|🌱 seedling leaf|🌿 herb|🍀 clover luck|🍃 leaves|🌳 tree|🌲 evergreen|🌴 palm|🌵 cactus|🌻 sunflower|🌸 blossom|🌹 rose|🌞 sun|🌙 moon|⭐ star|🌈 rainbow|☀️ sunny|⛅ cloud sun|🌧️ rain|❄️ snow|🌊 wave|🐶 dog|🐱 cat|🦁 lion|🐻 bear|🦊 fox|🐸 frog|🐝 bee|🦋 butterfly|🐢 turtle|🦄 unicorn|🐐 goat",
)
MSG_QUICK = "👍 ❤️ 😂 🔥 👀 🎉 😭 🚀"


MSG_JS = r'''
/* ======================= Messages (11.4) =======================
   Team chat. The database decides who may read or do anything (row level security + msg_* functions);
   this code only draws it, keeps a live connection (Supabase Realtime) and keeps unsent messages safe. */
const MX={started:false,convs:[],byId:{},cur:null,threads:{},tab:"all",q:"",results:null,searching:0,mentions:null,notes:[],presence:{},
  live:false,ws:null,rtTimer:0,hb:0,ref:0,joinRef:"",tokenAt:0,backoff:1000,info:false,reply:null,editing:null,atts:[],typingSent:0,typing:{},
  signed:{},missing:false,err:"",lastOv:0,lastNotes:0,lastPres:0,pins:{},files:{},noteIds:null,ovT:0,readT:0,seenMsg:{}};
const MX_TYPES=["image/png","image/jpeg","image/gif","image/webp","image/avif","image/heic","application/pdf","text/plain","text/csv","application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.ms-excel","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-powerpoint","application/vnd.openxmlformats-officedocument.presentationml.presentation","application/zip","application/x-zip-compressed",
  "application/rtf","application/vnd.oasis.opendocument.text","application/vnd.oasis.opendocument.spreadsheet","audio/mpeg","audio/mp4","video/mp4","video/quicktime"];
const MX_EXT={pdf:"application/pdf",txt:"text/plain",csv:"text/csv",doc:"application/msword",docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xls:"application/vnd.ms-excel",xlsx:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",ppt:"application/vnd.ms-powerpoint",
  pptx:"application/vnd.openxmlformats-officedocument.presentationml.presentation",zip:"application/zip",rtf:"application/rtf",odt:"application/vnd.oasis.opendocument.text",
  ods:"application/vnd.oasis.opendocument.spreadsheet",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg",gif:"image/gif",webp:"image/webp",heic:"image/heic",
  mp3:"audio/mpeg",m4a:"audio/mp4",mp4:"video/mp4",mov:"video/quicktime"};
const MX_MAX=25*1024*1024;
const mxId=()=>(crypto.randomUUID?crypto.randomUUID():"10000000-1000-4000-8000-100000000000".replace(/[018]/g,c=>(c^crypto.getRandomValues(new Uint8Array(1))[0]&15>>c/4).toString(16)));
const mxMe=()=>(S.me&&S.me.id)||"";
const mxName=id=>id&&id===mxMe()?"You":personById(id).name;
const mxFirst=id=>id&&id===mxMe()?"You":String(personById(id).name||"").split(" ")[0];
const mxOther=c=>{const m=(c.members||[]).find(x=>x.user_id!==mxMe());return m?m.user_id:mxMe()};
const mxTitle=c=>!c?"":c.type==="group"?(c.name||"Group chat"):personById(mxOther(c)).name;
const mxSize=n=>n<1024?n+" B":n<1048576?(n/1024).toFixed(n<10240?1:0)+" KB":(n/1048576).toFixed(1)+" MB";
const mxExt=n=>{const m=/\.([a-z0-9]{1,5})$/i.exec(n||"");return m?m[1].toUpperCase():"FILE"};
const mxIsImg=t=>/^image\/(png|jpeg|gif|webp|avif)$/.test(t||"");
const mxTime=iso=>{const d=new Date(iso);return isNaN(d)?"":d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"})};
function mxWhen(iso){const d=new Date(iso),n=new Date();if(isNaN(d))return "";if(d.toDateString()===n.toDateString())return mxTime(iso);
  const y=new Date(n);y.setDate(n.getDate()-1);if(d.toDateString()===y.toDateString())return "Yesterday";
  return (n-d)<6*864e5?d.toLocaleDateString([],{weekday:"short"}):d.toLocaleDateString([],{month:"short",day:"numeric"})}
function mxDay(iso){const d=new Date(iso),n=new Date(),y=new Date(n);y.setDate(n.getDate()-1);
  if(d.toDateString()===n.toDateString())return "Today";if(d.toDateString()===y.toDateString())return "Yesterday";
  return d.toLocaleDateString([],{weekday:"long",month:"long",day:"numeric",year:d.getFullYear()===n.getFullYear()?undefined:"numeric"})}
async function mxRpc(fn,args={}){let r;try{r=await api("sb_rpc",fn,args)}catch(e){r={ok:false,offline:true,error:"The app engine did not respond."}}
  r=r||{ok:false,error:"No answer."};if(r.missing)MX.missing=true;return r}
function mxCan(c){return c&&(c.role==="owner"||c.role==="admin"||(S.me&&S.me.role==="admin"))}

/* ---------- avatars ---------- */
function mxPAv(id,cls=""){const p=personById(id);return `<span class="mav ${cls}" data-au="${esc(id)}">${avHTML(p.name,p.avatar,p.media)}<i class="od${MX.presence[id]?" on":""}"></i></span>`}
function mxCAv(c,cls=""){if(c.type==="direct")return mxPAv(mxOther(c),cls);
  const img=c.avatar_url&&/^https:\/\//.test(c.avatar_url)?`<img src="${esc(c.avatar_url)}" alt="" loading="lazy">`:esc(initialsOf(c.name||"G"));
  return `<span class="mav ${cls}"><span class="gav">${img}</span></span>`}

/* ---------- message text: **bold**, *italic*, ~~strike~~, `code`, ```blocks```, - lists, links, @mentions ---------- */
function mxInline(t){
  const hold=[];const keep=h=>{hold.push(h);return "\u0001"+(hold.length-1)+"\u0001"};
  let s=String(t).replace(/`([^`\n]+)`/g,(m,c)=>keep(`<code>${esc(c)}</code>`))
    .replace(/\[([^\]\n]{1,200})\]\((https?:\/\/[^\s)]{1,800})\)/g,(m,x,u)=>keep(`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(x)}</a>`))
    .replace(/\bhttps?:\/\/[^\s<>"]{1,800}[^\s<>".,;:!?)\]'"]/g,u=>keep(`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>`))
    .replace(/<@(everyone|[0-9a-f-]{36})>/g,(m,id)=>keep(id==="everyone"?`<span class="ment ev">@everyone</span>`:`<span class="ment${id===mxMe()?" me":""}" data-au="${esc(id)}" role="button" tabindex="0">@${esc(personById(id).name)}</span>`));
  s=esc(s).replace(/\*\*(?=\S)([^*]*?\S)\*\*/g,"<b>$1</b>").replace(/~~(?=\S)([^~]*?\S)~~/g,"<s>$1</s>")
    .replace(/(^|[^\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])/g,"$1<i>$2</i>").replace(/(^|[^\w])_(?=\S)([^_\n]*?\S)_(?!\w)/g,"$1<i>$2</i>");
  return s.replace(/\u0001(\d+)\u0001/g,(m,i)=>hold[+i]);
}
function mxFmt(src){
  const blocks=[];let s=String(src||"").replace(/```\n?([\s\S]*?)```/g,(m,c)=>{blocks.push(c);return "\u0002"+(blocks.length-1)+"\u0002"});
  let out="",list=false,para=[];const flush=()=>{if(para.length){out+="<p>"+para.join("<br>")+"</p>";para=[]}};
  for(const ln of s.split("\n")){const m=/^\s*[-*•]\s+(.+)$/.exec(ln);
    if(m){flush();if(!list){out+="<ul>";list=true}out+="<li>"+mxInline(m[1])+"</li>";continue}
    if(list){out+="</ul>";list=false}
    if(/^\u0002\d+\u0002$/.test(ln.trim())){flush();out+=ln.trim();continue}
    if(!ln.trim())flush();else para.push(mxInline(ln))}
  flush();if(list)out+="</ul>";
  return out.replace(/\u0002(\d+)\u0002/g,(m,i)=>`<pre>${esc(blocks[+i])}</pre>`);
}
const mxPlain=t=>String(t||"").replace(/<@everyone>/g,"@everyone").replace(/<@([0-9a-f-]{36})>/g,(m,id)=>"@"+personById(id).name).replace(/[*_~`]/g,"");
const mxOnlyEmoji=t=>{const x=String(t||"").trim();return x.length>0&&x.length<=12&&/^(\p{Extended_Pictographic}|\p{Emoji_Component}|\u200d|\ufe0f|\s)+$/u.test(x)};
function mxSys(m){const a=(m.meta||{}).action,who=`<b>${esc(mxName(m.sender_id))}</b>`,us=((m.meta||{}).users||[]).map(u=>`<b>${esc(mxName(u))}</b>`);
  const list=us.length>2?us.slice(0,-1).join(", ")+" and "+us[us.length-1]:us.join(" and ");
  return a==="created"?`${who} created the group "${esc(m.meta.name||"")}"${us.length?" with "+list:""}`:a==="added"?`${who} added ${list}`:a==="removed"?`${who} removed ${list}`
    :a==="left"?`${list||who} left the group`:a==="renamed"?`${who} renamed the group to "${esc(m.meta.name||"")}"`:a==="picture"?`${who} changed the group picture`
    :a==="pinned"?`${who} pinned a message`:`${who} updated the chat`}
function mxPreview(c){const l=c.last;if(!l)return c.type==="group"?"Group created":"Say hello 👋";
  if(l.message_type==="system")return mxPlain(mxSys({...l,meta:l.meta||{}}).replace(/<[^>]+>/g,""));
  if(l.deleted)return "Message deleted";
  const who=l.sender_id===mxMe()?"You: ":c.type==="group"?mxFirst(l.sender_id)+": ":"";
  return who+(mxPlain(l.content).trim()||(l.files?`📎 ${l.files} file${l.files>1?"s":""}`:""))}

/* ---------- unsent messages are kept on this device until the database confirms them ---------- */
const mxOutKey=()=>"lf_msg_outbox_"+mxMe();
function mxOut(){try{return JSON.parse(localStorage.getItem(mxOutKey())||"[]")}catch(e){return []}}
function mxOutSet(a){try{localStorage.setItem(mxOutKey(),JSON.stringify(a.slice(-200)))}catch(e){}}
function mxOutPut(it){const a=mxOut().filter(x=>x.op!==it.op);a.push(it);mxOutSet(a)}
function mxOutDrop(op){mxOutSet(mxOut().filter(x=>x.op!==op))}

/* ---------- loading ---------- */
async function mxOverview(force){
  if(!force&&Date.now()-MX.lastOv<700)return;MX.lastOv=Date.now();
  const r=await mxRpc("msg_overview");
  if(!r.ok){MX.err=r.missing?"":r.error||"";if(S.page==="msgs")mxPaintList();mxBadges();return}
  MX.err="";MX.missing=false;MX.convs=r.data||[];MX.byId={};MX.convs.forEach(c=>{MX.byId[c.id]=c;
    (c.members||[]).forEach(m=>{if(m.typing&&m.user_id!==mxMe()){MX.typing[c.id]=MX.typing[c.id]||{};MX.typing[c.id][m.user_id]=Date.now()+6000}})});
  if(MX.cur&&!MX.byId[MX.cur]&&!String(MX.cur).startsWith("new:")){MX.cur=null;if(S.page==="msgs")mxRender()}
  mxBadges();if(S.page==="msgs"){mxPaintList();mxPaintHead();mxPaintTyping();if(MX.info)mxPaintInfo();mxPaintReceipts()}
}
const mxOvSoon=(ms=250)=>{clearTimeout(MX.ovT);MX.ovT=setTimeout(()=>mxOverview(true),ms)};
async function mxPresence(){const r=await mxRpc("msg_presence");if(r.ok){MX.presence={};(r.data||[]).forEach(p=>{MX.presence[p.id]=!!p.online})}MX.lastPres=Date.now();
  if(S.page==="msgs"){$$("#pg-msgs .mav[data-au] .od").forEach(o=>o.classList.toggle("on",!!MX.presence[o.parentElement.dataset.au]));mxPaintHead()}}
async function mxNotes(){
  const r=await mxRpc("msg_notifications",{p_limit:40});MX.lastNotes=Date.now();if(!r.ok)return;
  const fresh=(r.data||[]).filter(n=>!n.is_read&&MX.noteIds&&!MX.noteIds.has(n.id));
  MX.notes=r.data||[];MX.noteIds=new Set(MX.notes.map(n=>n.id));mxBadges();
  if($(".mx-nt"))mxPaintNotes();
  fresh.reverse().forEach(n=>{if(n.message_id&&MX.cur===n.conversation_id&&S.page==="msgs"&&!document.hidden)return;mxAlert(n)});
}
function mxNoteText(n){const who=`<b>${esc(personById(n.actor_id).name)}</b>`,where=n.conversation&&n.conversation.type==="group"?` in <b>${esc(n.conversation.name)}</b>`:"";
  return n.type==="mention"?`${who} mentioned you${where}`:n.type==="everyone"?`${who} notified everyone${where}`:n.type==="reply"?`${who} replied to you${where}`
    :n.type==="member"?`${who} added you to <b>${esc((n.conversation||{}).name||"a group")}</b>`:`${who} sent you a message`}
function mxAlert(n){
  const plain=mxNoteText(n).replace(/<[^>]+>/g,""),body=n.preview?mxPlain(n.preview):"";
  toast(plain+(body?": "+body.slice(0,60):""),{ms:7000,action:{label:"Open",fn:()=>mxOpenAt(n.conversation_id,n.message_id)}});
  if(n.type==="mention"||n.type==="everyone")logNote(plain);
  try{if(getP("msgAlerts",false)&&"Notification" in window&&Notification.permission==="granted"&&document.hidden){
    const x=new Notification(plain,{body:body.slice(0,140),tag:n.id,silent:false});x.onclick=()=>{window.focus();mxOpenAt(n.conversation_id,n.message_id);x.close()}}}catch(e){}
}
function mxBadges(){
  const vis=MX.convs.filter(c=>!c.muted),un=vis.reduce((a,c)=>a+(c.unread||0),0),at=MX.convs.reduce((a,c)=>a+(c.mentions||0),0);
  const b=$("#msgBadge");if(b){b.textContent=at||un;b.style.display=(un||at)?"":"none";b.classList.toggle("at",at>0)}
  const f=$("#fnMsgDot");if(f)f.classList.toggle("on",un+at>0);
  const nb=$("#mxNoteN");const nn=MX.notes.filter(n=>!n.is_read).length;if(nb){nb.textContent=nn;nb.style.display=nn?"":"none"}
  MX.unread=un;MX.atCount=at;
}

/* ---------- live connection: Supabase Realtime (postgres_changes), with polling as the fallback ---------- */
async function mxConnect(){
  if(!MX.started||MX.ws||MX.missing)return;
  const s=await api("sb_session").catch(()=>null);
  if(!s||!s.ok){mxLater();return}
  let ws;try{ws=new WebSocket(s.realtime+"?apikey="+encodeURIComponent(s.key)+"&vsn=1.0.0")}catch(e){mxLater();return}
  MX.ws=ws;MX.tokenAt=Date.now();const topic="realtime:leafline-messages-"+mxMe().slice(0,8);
  const send=(m)=>{try{if(ws.readyState===1)ws.send(JSON.stringify(m))}catch(e){}};
  ws.onopen=()=>{MX.joinRef=String(++MX.ref);
    send({topic,event:"phx_join",ref:MX.joinRef,join_ref:MX.joinRef,payload:{access_token:s.token,config:{broadcast:{self:false},presence:{key:""},
      postgres_changes:["conversations","conversation_members","messages","message_reactions","message_notifications","pinned_messages"].map(t=>({event:"*",schema:"public",table:t}))}}});
    clearInterval(MX.hb);MX.hb=setInterval(()=>{send({topic:"phoenix",event:"heartbeat",payload:{},ref:String(++MX.ref)});
      if(Date.now()-MX.tokenAt>15*60e3){MX.tokenAt=Date.now();api("sb_session").then(x=>{if(x&&x.ok)send({topic,event:"access_token",payload:{access_token:x.token},ref:String(++MX.ref)})}).catch(()=>{})}},25000)};
  ws.onmessage=e=>{let m;try{m=JSON.parse(e.data)}catch(x){return}
    if(m.event==="phx_reply"&&m.ref===MX.joinRef){if(m.payload&&m.payload.status==="ok"){MX.live=true;MX.backoff=1000;mxSyncAfterGap()}else{try{ws.close()}catch(x){}}return}
    if(m.event==="postgres_changes"&&m.payload&&m.payload.data)mxChange(m.payload.data);
    if(m.event==="phx_error"||m.event==="phx_close"){try{ws.close()}catch(x){}}};
  ws.onclose=()=>{if(MX.ws===ws){MX.ws=null;MX.live=false;clearInterval(MX.hb);mxLater()}};
  ws.onerror=()=>{};
}
function mxLater(){clearTimeout(MX.rtTimer);if(!MX.started)return;MX.rtTimer=setTimeout(mxConnect,MX.backoff);MX.backoff=Math.min(MX.backoff*2,30000)}
function mxSyncAfterGap(){mxOverview(true);mxNotes();if(MX.cur)mxNewer(MX.cur);mxFlushOut()}
function mxChange(d){
  const r=d.record&&Object.keys(d.record).length?d.record:(d.old_record||{}),t=d.table,cid=t==="conversations"?r.id:r.conversation_id;
  if(t==="messages"){
    if(cid&&cid===MX.cur&&r.id)mxFetch(cid,[r.id]);
    mxOvSoon(d.type==="INSERT"?150:400);
  }else if(t==="message_reactions"||t==="pinned_messages"){
    const mid=r.message_id;if(mid&&MX.threads[cid||MX.cur]&&MX.threads[cid||MX.cur].list.some(x=>x.id===mid))mxFetch(cid||MX.cur,[mid]);
    else if(mid&&MX.cur&&MX.threads[MX.cur]&&MX.threads[MX.cur].list.some(x=>x.id===mid))mxFetch(MX.cur,[mid]);
    if(t==="pinned_messages"){if(cid)delete MX.pins[cid];if(MX.info)mxLoadSide(MX.cur)}
    mxOvSoon(600);
  }else if(t==="conversation_members"){
    if(r.typing_at&&r.user_id&&r.user_id!==mxMe()&&Date.now()-Date.parse(r.typing_at)<60e3&&cid){MX.typing[cid]=MX.typing[cid]||{};MX.typing[cid][r.user_id]=Date.now()+6000;if(cid===MX.cur)mxPaintTyping()}
    mxOvSoon(500);
  }else if(t==="message_notifications"){clearTimeout(MX.ntT);MX.ntT=setTimeout(mxNotes,300)}
  else mxOvSoon(300);
}
function mxTick(){
  if(!MX.started){if(S.ready&&S.me){MX.started=true;MX.noteIds=null;MX.missing=false;
      mxOverview(true).then(()=>{if(MX.missing)return;mxPresence();mxNotes();mxConnect();mxFlushOut()})}return}
  if(!S.me){mxStop();return}
  const now=Date.now(),here=S.page==="msgs"&&!document.hidden;
  if(MX.missing){if(now-MX.lastOv>300000)mxOverview(true).then(()=>{if(!MX.missing){mxPresence();mxNotes();mxConnect()}});return}   /* 8th update not run: stay quiet, re-check now and then */
  if(!MX.live){if(here&&now-MX.lastOv>4000){mxOverview(true);if(MX.cur)mxNewer(MX.cur)}else if(!here&&now-MX.lastOv>(document.hidden?60000:20000))mxOverview(true);
    if(now-MX.lastNotes>(here?12000:30000))mxNotes()}
  else if(now-MX.lastOv>60000)mxOverview(true);
  if(now-MX.lastPres>(here?30000:90000))mxPresence();
  if(MX.cur&&MX.typing[MX.cur])mxPaintTyping();
}
function mxStop(){MX.started=false;MX.live=false;clearTimeout(MX.rtTimer);clearInterval(MX.hb);if(MX.ws){const w=MX.ws;MX.ws=null;try{w.close()}catch(e){}}
  Object.assign(MX,{convs:[],byId:{},cur:null,threads:{},notes:[],results:null,mentions:null,pins:{},files:{},signed:{},typing:{},noteIds:null});mxBadges()}
setInterval(mxTick,1000);
setInterval(()=>{if(MX.started&&!MX.missing)mxFlushOut()},8000);
addEventListener("online",()=>{if(MX.started){mxSyncAfterGap();if(!MX.ws){MX.backoff=1000;mxConnect()}}});
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&MX.started){mxOverview(true);if(MX.cur&&S.page==="msgs")mxRead(MX.cur)}});

/* ---------- threads ---------- */
const mxT=cid=>MX.threads[cid]||(MX.threads[cid]={list:[],more:true,loaded:false,loading:false,gap:false});
function mxMerge(cid,msgs){const t=mxT(cid),by=new Map(t.list.map(m=>[m.id,m]));msgs.forEach(m=>by.set(m.id,m));
  t.list=[...by.values()].sort((a,b)=>a.created_at<b.created_at?-1:a.created_at>b.created_at?1:a.id<b.id?-1:1);
  const ops=new Set(msgs.map(m=>m.client_op_id).filter(Boolean));if(ops.size)mxOutSet(mxOut().filter(x=>!ops.has(x.op)))}
async function mxFetch(cid,ids){const r=await mxRpc("msg_get",{p_ids:ids});if(!r.ok)return;
  const fresh=(r.data||[]).filter(m=>!mxT(cid).list.some(x=>x.id===m.id));mxMerge(cid,r.data||[]);
  if(cid===MX.cur&&S.page==="msgs"){mxPaintMsgs({fresh:fresh.map(m=>m.id)});if(fresh.some(m=>m.sender_id!==mxMe()))mxRead(cid)}}
async function mxLoad(cid){const t=mxT(cid);if(t.loading)return;t.loading=true;
  const r=await mxRpc("msg_history",{p_conv:cid,p_limit:40});t.loading=false;
  if(!r.ok){if(cid===MX.cur)mxPaintMsgs({error:r.error});return}
  t.list=[];mxMerge(cid,r.data||[]);t.loaded=true;t.more=(r.data||[]).length>=40;t.gap=false;if(cid===MX.cur){mxPaintMsgs({bottom:true});mxRead(cid)}}
async function mxOlder(cid){const t=mxT(cid);if(t.loading||!t.more||!t.list.length)return;t.loading=true;const o=t.list[0];
  const sc=$("#mxScroll"),h0=sc?sc.scrollHeight:0,top0=sc?sc.scrollTop:0;
  const r=await mxRpc("msg_history",{p_conv:cid,p_before:o.created_at,p_before_id:o.id,p_limit:40});t.loading=false;if(!r.ok)return;
  mxMerge(cid,r.data||[]);t.more=(r.data||[]).length>=40;
  if(cid===MX.cur){mxPaintMsgs({keep:true});const s2=$("#mxScroll");if(s2)s2.scrollTop=top0+(s2.scrollHeight-h0)}}
async function mxNewer(cid){const t=mxT(cid);if(!t.loaded||t.gap)return;const r=await mxRpc("msg_history",{p_conv:cid,p_limit:25});if(!r.ok)return;
  const fresh=(r.data||[]).filter(m=>!t.list.some(x=>x.id===m.id));const changed=fresh.length||(r.data||[]).some(m=>{const x=t.list.find(y=>y.id===m.id);return x&&JSON.stringify(x)!==JSON.stringify(m)});
  if(!changed)return;mxMerge(cid,r.data||[]);if(cid===MX.cur&&S.page==="msgs"){mxPaintMsgs({fresh:fresh.map(m=>m.id)});if(fresh.some(m=>m.sender_id!==mxMe()))mxRead(cid)}}
function mxRead(cid){const c=MX.byId[cid];if(!c||document.hidden||S.page!=="msgs"||MX.cur!==cid)return;
  if(c.unread||c.mentions){c.unread=0;c.mentions=0;mxBadges();mxPaintList()}
  clearTimeout(MX.readT);MX.readT=setTimeout(async()=>{await mxRpc("msg_mark_read",{p_conv:cid});MX.notes.forEach(n=>{if(n.conversation_id===cid)n.is_read=true});mxBadges()},400)}

/* ---------- page ---------- */
function renderMsgs(){
  const pg=$("#pg-msgs");if(!pg)return;
  if(!pg.dataset.built){pg.dataset.built=1;
    pg.innerHTML=`<div class="mx" id="mx"><aside class="mx-list" aria-label="Conversations">
      <div class="mx-lh"><h3>Chats</h3><button class="mx-ib" id="mxNoteBtn" title="Notifications" aria-label="Message notifications">${ic("bell")}<span class="nb" id="mxNoteN" style="display:none">0</span></button>
        <button class="mx-ib" id="mxNewBtn" title="New message" aria-label="New message">${ic("edit")}</button></div>
      <div class="mx-srch">${ic("search")}<input id="mxQ" placeholder="Search people, chats and messages" autocomplete="off" aria-label="Search messages"></div>
      <div class="mx-tabs" role="tablist"><button data-tab="all" class="on" role="tab">All</button><button data-tab="unread" role="tab">Unread</button><button data-tab="mentions" role="tab">Mentions</button></div>
      <div class="mx-cl" id="mxList"></div></aside>
      <section class="mx-chat" id="mxChat" aria-label="Conversation"></section>
      <aside class="mx-info" id="mxInfo" aria-label="Conversation details"><div id="mxInfoIn"></div></aside></div>`;
    hydrateIcons(pg);
    $("#mxNewBtn").onclick=()=>mxNewChat("direct");
    $("#mxNoteBtn").onclick=e=>{e.stopPropagation();mxNotesPop($("#mxNoteBtn"))};
    let qt=0;$("#mxQ").oninput=e=>{MX.q=e.target.value;mxPaintList();clearTimeout(qt);qt=setTimeout(mxSearch,320)};
    $("#mxQ").onkeydown=e=>{if(e.key==="Escape"){e.target.value="";MX.q="";MX.results=null;mxPaintList()}};
    $$("#pg-msgs [data-tab]").forEach(b=>b.onclick=()=>{MX.tab=b.dataset.tab;$$("#pg-msgs [data-tab]").forEach(x=>x.classList.toggle("on",x===b));if(MX.tab==="mentions")mxLoadMentions();mxPaintList()});
    wireHover(pg);
  }
  if(!MX.cur&&innerWidth>860){const first=MX.convs.find(c=>!c.archived);if(first&&getP("msgLast","")===first.id)MX.cur=first.id}
  mxRender();if(MX.started)mxOverview(true);mxPresence();
}
function mxRender(){mxPaintList();mxPaintChat();mxPaintInfo();
  const mx=$("#mx");if(!mx)return;mx.classList.toggle("chat",!!MX.cur);mx.classList.toggle("info",!!(MX.info&&MX.cur));
  document.body.classList.toggle("msg-chat",!!MX.cur&&S.page==="msgs")}
function mxLeave(){document.body.classList.remove("msg-chat");mxClosePops()}

/* ---------- conversation list ---------- */
function mxMatch(c,q){q=q.toLowerCase();return mxTitle(c).toLowerCase().includes(q)||(c.members||[]).some(m=>personById(m.user_id).name.toLowerCase().includes(q))}
function mxRow(c){const typ=MX.typing[c.id]&&Object.entries(MX.typing[c.id]).filter(([u,t])=>t>Date.now()).map(([u])=>u);
  const pv=typ&&typ.length?`<span class="ty">${esc(c.type==="group"?mxFirst(typ[0])+" is typing…":"typing…")}</span>`:esc(mxPreview(c));
  return `<button class="mx-c${c.id===MX.cur?" on":""}${c.unread?" un":""}${c.muted?" mute":""}" data-cid="${esc(c.id)}">${mxCAv(c)}
   <span class="nm">${esc(mxTitle(c))}${c.muted?ic("bell"):""}${c.pinned?ic("pin"):""}</span><span class="mxt">${esc(mxWhen((c.last||{}).created_at||c.last_message_at))}</span>
   <span class="pv">${pv}</span><span class="bd">${c.mentions?`<b class="at">@</b>`:""}${c.unread?`<b>${c.unread>99?"99+":c.unread}</b>`:""}</span></button>`}
function mxPaintList(){
  const el=$("#mxList");if(!el)return;
  $$("#pg-msgs [data-tab]").forEach(b=>{const n=b.dataset.tab==="unread"?MX.convs.filter(c=>c.unread&&!c.archived).length:b.dataset.tab==="mentions"?MX.atCount||0:0;
    b.innerHTML=({all:"All",unread:"Unread",mentions:"Mentions"})[b.dataset.tab]+(n?` <b>${n}</b>`:"")});
  if(MX.missing){el.innerHTML=`<div class="mx-empty"><div class="bub">${ic("chat")}</div><b>Messages aren't switched on yet</b>An admin needs to run the 8th database update once (supabase/migrations/20261108000008_messaging.sql, also in RUN_IN_SUPABASE.sql). Everything else keeps working.</div>`;hydrateIcons(el);return}
  let html=MX.err&&!MX.convs.length?`<div class="mx-banner bad">${esc(MX.err)}</div>`:(!MX.live&&MX.started&&MX.convs.length?"":"");
  if(MX.tab==="mentions"){html+=mxResultsHTML(MX.mentions,"Nobody has mentioned you yet.","Loading mentions…");el.innerHTML=html;mxWireResults(el);return}
  let list=MX.convs.slice();
  if(MX.q.trim())list=list.filter(c=>mxMatch(c,MX.q.trim()));
  if(MX.tab==="unread")list=list.filter(c=>c.unread||c.mentions);
  const pinned=list.filter(c=>c.pinned&&!c.archived),rest=list.filter(c=>!c.pinned&&!c.archived),arch=list.filter(c=>c.archived);
  if(!MX.convs.length&&!MX.err)html+=MX.started&&MX.lastOv?`<div class="mx-empty"><div class="bub">${ic("chat")}</div><b>No conversations yet</b>Message a teammate or start a group chat.<button class="btn pri" data-new style="margin-top:6px">${ic("plus")}New message</button></div>`:`<div class="mx-sk">${"<i></i>".repeat(5)}</div>`;
  else if(!list.length)html+=`<div class="mx-empty" style="padding:24px 10px">${MX.tab==="unread"?"You're all caught up.":"No chats match."}</div>`;
  if(pinned.length)html+=`<div class="mx-sec">Pinned</div>`+pinned.map(mxRow).join("");
  if(rest.length)html+=(pinned.length?`<div class="mx-sec">Recent</div>`:"")+rest.map(mxRow).join("");
  if(arch.length)html+=`<div class="mx-sec">Archived</div>`+arch.map(mxRow).join("");
  if(MX.q.trim().length>=2){
    const people=teamList().filter(([id,n])=>id!==mxMe()&&n.toLowerCase().includes(MX.q.trim().toLowerCase())&&!MX.convs.some(c=>c.type==="direct"&&mxOther(c)===id));
    if(people.length)html+=`<div class="mx-sec">People</div>`+people.map(([id,n])=>`<button class="mx-c" data-dm="${esc(id)}">${mxPAv(id)}<span class="nm">${esc(n)}</span><span class="mxt"></span><span class="pv">Start a conversation</span></button>`).join("");
    html+=`<div class="mx-sec">Messages</div>`+mxResultsHTML(MX.results,"No messages match.","Searching…");
  }
  el.innerHTML=html;hydrateIcons(el);
  $$("[data-cid]",el).forEach(b=>b.onclick=()=>mxOpen(b.dataset.cid));
  $$("[data-dm]",el).forEach(b=>b.onclick=()=>mxStartDm(b.dataset.dm));
  const nb=$("[data-new]",el);if(nb)nb.onclick=()=>mxNewChat("direct");
  mxWireResults(el);
}
function mxResultsHTML(rs,none,wait){
  if(rs===null||rs===undefined)return `<div class="mx-empty" style="padding:18px 10px">${esc(wait)}</div>`;
  if(!rs.length)return `<div class="mx-empty" style="padding:18px 10px">${esc(none)}</div>`;
  const q=MX.q.trim(),mark=s=>q.length>=2?esc(s).replace(new RegExp(esc(q).replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),"gi"),m=>`<mark>${m}</mark>`):esc(s);
  return rs.map(m=>{const c=MX.byId[m.conversation_id];return `<button class="mx-res" data-jump="${esc(m.id)}" data-jc="${esc(m.conversation_id)}"><div class="h"><b>${esc(mxName(m.sender_id))}</b>${c?esc((c.type==="group"?"in ":"")+mxTitle(c)):""}<span style="margin-left:auto">${esc(mxWhen(m.created_at))}</span></div><div class="t">${mark(mxPlain(m.content)||(m.attachments||[]).map(a=>"📎 "+a.name).join(", "))}</div></button>`}).join("")}
function mxWireResults(el){$$("[data-jump]",el).forEach(b=>b.onclick=()=>mxOpenAt(b.dataset.jc,b.dataset.jump))}
async function mxSearch(){const q=MX.q.trim();if(q.length<2){MX.results=null;return}const my=++MX.searching;MX.results=null;mxPaintList();
  const r=await mxRpc("msg_search",{p_q:q,p_limit:40});if(my!==MX.searching)return;MX.results=r.ok?r.data||[]:[];mxPaintList()}
async function mxLoadMentions(){const r=await mxRpc("msg_mentions",{p_limit:60});MX.mentions=r.ok?r.data||[]:[];if(MX.tab==="mentions")mxPaintList()}

/* ---------- opening a chat ---------- */
async function mxOpen(cid){
  if(MX.cur!==cid){MX.reply=null;MX.editing=null;MX.atts=[];MX.draft=""}
  MX.cur=cid;setP("msgLast",cid);mxClosePops();
  if(S.page!=="msgs")await go("msgs");
  mxRender();const t=mxT(cid);
  if(!t.loaded||t.gap)await mxLoad(cid);else{mxPaintMsgs({bottom:true});mxRead(cid);mxNewer(cid)}
  if(MX.info)mxLoadSide(cid);
  if(innerWidth>860){const ta=$("#mxTa");ta&&ta.focus()}
}
async function mxOpenAt(cid,mid){
  if(!mid)return mxOpen(cid);
  MX.cur=cid;setP("msgLast",cid);if(S.page!=="msgs")await go("msgs");mxRender();
  const t=mxT(cid);
  if(!t.list.some(m=>m.id===mid)){const r=await mxRpc("msg_around",{p_id:mid,p_each:25});if(!r.ok||!(r.data||[]).length){toast("That message isn't available any more.",{bad:1});return mxOpen(cid)}
    t.list=[];mxMerge(cid,r.data);t.loaded=true;t.more=true;
    const latest=MX.byId[cid]&&MX.byId[cid].last;t.gap=!!(latest&&!t.list.some(m=>m.id===latest.id))}
  mxPaintMsgs({});mxFlash(mid);mxRead(cid);
}
function mxFlash(mid){const el=$(`#mxScroll .mm[data-mid="${CSS.escape(mid)}"]`);if(!el)return;el.scrollIntoView({block:"center",behavior:REDUCE?"auto":"smooth"});
  el.classList.remove("flash");void el.offsetWidth;el.classList.add("flash")}
async function mxStartDm(uid){const r=await mxRpc("msg_start_direct",{p_other:uid});if(!r.ok)return toast(r.error||"Couldn't start the chat.",{bad:1});
  await mxOverview(true);MX.q="";const q=$("#mxQ");if(q)q.value="";mxOpen(r.data)}

/* ---------- chat panel ---------- */
function mxPaintChat(){
  const el=$("#mxChat");if(!el)return;const c=MX.byId[MX.cur];
  if(!c){el.innerHTML=`<div class="mx-empty" style="margin:auto"><div class="bub">${ic("chat")}</div><b>Your team chat</b>Pick a conversation, or start a new one.<div style="display:flex;gap:8px;margin-top:6px"><button class="btn pri" data-nd>${ic("user")}New message</button><button class="btn" data-ng>${ic("users")}New group</button></div></div>`;
    hydrateIcons(el);$("[data-nd]",el).onclick=()=>mxNewChat("direct");$("[data-ng]",el).onclick=()=>mxNewChat("group");return}
  el.innerHTML=`<div class="mx-ch"><button class="mx-ib mx-back" id="mxBack" aria-label="Back to conversations">${ic("prev")}</button><span id="mxHAv">${mxCAv(c)}</span>
     <div class="tt" id="mxHT"><h4 id="mxHTitle"></h4><div class="sub" id="mxHSub"></div></div>
     <button class="mx-ib" id="mxPinsBtn" title="Pinned messages" aria-label="Pinned messages">${ic("pin")}</button>
     <button class="mx-ib${MX.info?" on":""}" id="mxInfoBtn" title="Details" aria-label="Conversation details">${ic("users")}</button></div>
   <div class="mx-scroll" id="mxScroll"><div class="mx-sk">${"<i></i>".repeat(6)}</div></div>
   <div class="mx-typ" id="mxTyp" aria-live="polite"></div>
   <div class="mx-comp" id="mxComp"></div>`;
  hydrateIcons(el);mxPaintHead();mxPaintComposer();
  $("#mxBack").onclick=()=>{MX.cur=null;MX.info=false;mxRender()};
  $("#mxInfoBtn").onclick=$("#mxHT").onclick=()=>{MX.info=!MX.info;mxRender();if(MX.info)mxLoadSide(MX.cur)};
  $("#mxPinsBtn").onclick=e=>{e.stopPropagation();mxPinsPop($("#mxPinsBtn"))};
  const sc=$("#mxScroll");
  sc.addEventListener("scroll",()=>{if(sc.scrollTop<120)mxOlder(MX.cur);const nb=$(".mx-new");if(nb&&sc.scrollHeight-sc.scrollTop-sc.clientHeight<60)nb.remove()});
  sc.addEventListener("click",mxMsgClick);
  const comp=$("#mxComp");
  ["dragenter","dragover"].forEach(ev=>el.addEventListener(ev,e=>{if([...(e.dataTransfer||{}).types||[]].includes("Files")){e.preventDefault();comp.classList.add("drag")}}));
  ["dragleave","drop"].forEach(ev=>el.addEventListener(ev,e=>{if(ev==="dragleave"&&el.contains(e.relatedTarget))return;comp.classList.remove("drag")}));
  el.addEventListener("drop",e=>{if(e.dataTransfer&&e.dataTransfer.files.length){e.preventDefault();mxAddFiles([...e.dataTransfer.files])}});
  const t=MX.threads[c.id];if(t&&t.loaded)mxPaintMsgs({bottom:true});
}
function mxPaintHead(){const c=MX.byId[MX.cur],t=$("#mxHTitle"),s=$("#mxHSub");if(!c||!t)return;
  t.textContent=mxTitle(c);
  if(c.type==="direct"){const o=mxOther(c),p=personFull(o),on=MX.presence[o];s.innerHTML=`<span class="${on?"onl":""}">${on?"● Online":"Offline"}</span>${p.ext&&p.ext.title?" · "+esc(p.ext.title):""}`}
  else{const ms=c.members||[],on=ms.filter(m=>MX.presence[m.user_id]&&m.user_id!==mxMe()).length;s.innerHTML=`${ms.length} member${ms.length===1?"":"s"}${on?` · <span class="onl">${on} online</span>`:""}`}
  const pb=$("#mxPinsBtn");if(pb)pb.style.display=c.pinned_count?"":"none";
  const hav=$("#mxHAv");if(hav)hav.innerHTML=mxCAv(c);
}
function mxPaintTyping(){const el=$("#mxTyp");if(!el)return;const now=Date.now(),ty=Object.entries(MX.typing[MX.cur]||{}).filter(([u,t])=>t>now).map(([u])=>u);
  const txt=!ty.length?"":ty.length===1?`${mxFirst(ty[0])} is typing`:ty.length===2?`${mxFirst(ty[0])} and ${mxFirst(ty[1])} are typing`:"Several people are typing";
  if(el.dataset.t===txt)return;el.dataset.t=txt;el.innerHTML=txt?`<span class="dots"><i></i><i></i><i></i></span>${esc(txt)}`:"";
  const row=$(`.mx-c[data-cid="${CSS.escape(MX.cur||"")}"] .pv`);if(row&&MX.byId[MX.cur])row.innerHTML=ty.length?`<span class="ty">${esc(MX.byId[MX.cur].type==="group"?mxFirst(ty[0])+" is typing…":"typing…")}</span>`:esc(mxPreview(MX.byId[MX.cur]))}

function mxMsgHTML(m,prev,c){
  const me=m.sender_id===mxMe(),sys=m.message_type==="system";
  let day="";if(!prev||new Date(prev.created_at).toDateString()!==new Date(m.created_at).toDateString())day=`<div class="mx-day">${esc(mxDay(m.created_at))}</div>`;
  if(sys)return day+`<div class="mx-sys" data-mid="${esc(m.id)}">${mxSys(m)} · ${esc(mxTime(m.created_at))}</div>`;
  const cont=prev&&!day&&prev.message_type!=="system"&&prev.sender_id===m.sender_id&&(Date.parse(m.created_at)-Date.parse(prev.created_at))<5*60e3&&!m.reply;
  const atme=!me&&!m.deleted_at&&((m.mentions||[]).includes(mxMe())||m.mentions_everyone);
  const del=!!m.deleted_at,pend=m._pend;
  const body=del?`<div class="mb"><span>This message was deleted</span></div>`
    :(m.content.trim()?`<div class="mb${mxOnlyEmoji(m.content)&&!(m.attachments||[]).length?" only-emoji":""}">${mxFmt(m.content)}${m.edited_at?`<span class="ed" title="Edited ${esc(new Date(m.edited_at).toLocaleString())}">(edited)</span>`:""}</div>`:"");
  const files=del?"":(m.attachments||[]).map(a=>mxIsImg(a.type)?`<button class="mm-img" data-img="${esc(a.path)}" data-name="${esc(a.name)}" aria-label="Open ${esc(a.name)}"><img data-sp="${esc(a.path)}" alt="${esc(a.name)}"${MX.signed[a.path]?` src="${esc(MX.signed[a.path].url)}"`:""}></button>`
    :`<button class="mm-file" data-dl="${esc(a.path)}" data-name="${esc(a.name)}" title="Download ${esc(a.name)}"><span class="fi">${esc(mxExt(a.name))}</span><span class="fn"><b>${esc(a.name)}</b><span>${esc(mxSize(a.size||0))}${a._prog!==undefined?" · uploading":""}</span></span>${ic("down")}</button>`).join("");
  const rx={};(m.reactions||[]).forEach(r=>{(rx[r.emoji]=rx[r.emoji]||[]).push(r.user_id)});
  const rxh=Object.keys(rx).length?`<div class="mm-rx">${Object.entries(rx).map(([e,us])=>`<button data-rx="${esc(e)}" class="${us.includes(mxMe())?"on":""}" title="${esc(us.map(mxName).join(", "))} reacted with ${esc(e)}" aria-label="${esc(e)} ${us.length}">${esc(e)}<b>${us.length}</b></button>`).join("")}<button data-rxp aria-label="Add reaction" title="Add reaction">${ic("plus")}</button></div>`:"";
  const rp=m.reply?`<div class="mm-rp" data-goto="${esc(m.reply.id)}">${ic("undo")}<b>${esc(mxName(m.reply.sender_id))}</b><span>${m.reply.deleted?"Message deleted":esc(mxPlain(m.reply.content)||"📎 file")}</span></div>`:"";
  const st=pend?(m._state==="failed"?`<div class="mm-st bad">Not sent${m._err?": "+esc(m._err):""} · <button data-retry="${esc(m.client_op_id)}">Retry</button> · <button data-discard="${esc(m.client_op_id)}">Remove</button></div>`
      :`<div class="mm-st">${m._state==="waiting"?"Waiting for connection…":"Sending…"}</div>`):"";
  const acts=del||pend?"":`<div class="mm-act" role="toolbar" aria-label="Message actions">${MX_Q.slice(0,4).map(e=>`<button data-qr="${esc(e)}" title="React ${esc(e)}">${e}</button>`).join("")}
     <button data-rxp title="More reactions" aria-label="More reactions">${ic("plus")}</button><span class="sep"></span>
     <button data-reply title="Reply" aria-label="Reply">${ic("undo")}</button>${me?`<button data-edit title="Edit" aria-label="Edit">${ic("edit")}</button>`:""}
     <button data-pin title="${m.pinned?"Unpin":"Pin"}" aria-label="${m.pinned?"Unpin":"Pin"}">${ic("pin")}</button><button data-copy title="Copy text" aria-label="Copy text">${ic("copy")}</button>
     ${me||(S.me&&S.me.role==="admin")?`<button data-del title="Delete" aria-label="Delete">${ic("trash")}</button>`:""}</div>`;
  return day+`<div class="mm${me?" me":""}${cont?" cont":""}${atme?" atme":""}${del?" del":""}${pend?" pend":""}" data-mid="${esc(m.id)}"><div class="mm-av">${me?"":mxPAv(m.sender_id,"sm")}</div>
    <div class="mm-col"><div class="mm-h"><b data-au="${esc(m.sender_id)}">${esc(mxName(m.sender_id))}</b><span title="${esc(new Date(m.created_at).toLocaleString())}">${esc(mxTime(m.created_at))}</span></div>
    ${rp}${body}${files?`<div class="mm-files">${files}</div>`:""}${rxh}${m.pinned?`<div class="mm-pin">${ic("pin")}Pinned</div>`:""}${st}<div class="mm-rr"></div></div>${acts}</div>`;
}
function mxPendingFor(cid){return mxOut().filter(x=>x.conv===cid).map(x=>({id:"pend:"+x.op,client_op_id:x.op,conversation_id:cid,sender_id:mxMe(),content:x.content,message_type:"text",
  created_at:x.at,reactions:[],mentions:[],attachments:(x.atts||[]).map(a=>({...a})),reply:x.replyPrev||null,_pend:true,_state:x.state,_err:x.err}))}
function mxPaintMsgs(o={}){
  const sc=$("#mxScroll"),c=MX.byId[MX.cur];if(!sc||!c)return;const t=mxT(c.id);
  if(o.error&&!t.list.length){sc.innerHTML=`<div class="mx-empty"><b>Couldn't load this chat</b>${esc(o.error)}<button class="btn" data-again style="margin-top:6px">Try again</button></div>`;$("[data-again]",sc).onclick=()=>mxLoad(c.id);return}
  if(!t.loaded){sc.innerHTML=`<div class="mx-sk">${"<i></i>".repeat(6)}</div>`;return}
  const atBottom=o.bottom||sc.scrollHeight-sc.scrollTop-sc.clientHeight<80,keepTop=sc.scrollTop;
  const all=[...t.list,...mxPendingFor(c.id).filter(p=>!t.list.some(m=>m.client_op_id===p.client_op_id))];
  let html=t.more?`<button class="mx-more" data-older>${t.loading?"Loading…":"Load earlier messages"}</button>`:`<div class="mx-sys" style="margin:4px 0 14px">${c.type==="group"?`This is the start of <b>${esc(c.name)}</b>.`:`This is the start of your conversation with <b>${esc(mxTitle(c))}</b>.`}</div>`;
  all.forEach((m,i)=>{html+=mxMsgHTML(m,all[i-1],c)});
  if(t.gap)html+=`<button class="mx-more" data-latest>Jump to the latest messages ↓</button>`;
  if(!all.length)html+=`<div class="mx-empty" style="padding:30px 10px"><div class="bub">${ic("hand")}</div><b>Say hello</b>Messages you send here are only seen by ${c.type==="group"?"the people in this group":esc(mxTitle(c))+" and you"}.</div>`;
  sc.innerHTML=html;hydrateIcons(sc);
  const ob=$("[data-older]",sc);if(ob)ob.onclick=()=>mxOlder(c.id);
  const lb=$("[data-latest]",sc);if(lb)lb.onclick=()=>{t.gap=false;t.loaded=false;mxLoad(c.id)};
  if(o.fresh&&o.fresh.length&&!REDUCE)o.fresh.forEach(id=>{const e=$(`.mm[data-mid="${CSS.escape(id)}"]`,sc);if(e)e.animate([{opacity:0,transform:"translateY(10px) scale(.98)"},{opacity:1,transform:"none"}],{duration:320,easing:EASE.out})});
  if(atBottom||o.bottom)sc.scrollTop=sc.scrollHeight;else if(!o.keep){sc.scrollTop=keepTop;
    if(o.fresh&&o.fresh.length&&!$(".mx-new")){const b=document.createElement("button");b.className="mx-new";b.textContent="New messages ↓";b.onclick=()=>{sc.scrollTop=sc.scrollHeight;b.remove()};$("#mxChat").appendChild(b)}}
  mxSignVisible();mxPaintReceipts();
}
function mxPaintReceipts(){
  const c=MX.byId[MX.cur],sc=$("#mxScroll");if(!c||!sc)return;$$(".mm-rr",sc).forEach(e=>e.innerHTML="");
  const t=mxT(c.id),mine=[...t.list].reverse().find(m=>m.sender_id===mxMe()&&m.message_type==="text"&&!m.deleted_at);if(!mine)return;
  const el=$(`.mm[data-mid="${CSS.escape(mine.id)}"] .mm-rr`,sc);if(!el)return;
  const others=(c.members||[]).filter(m=>m.user_id!==mxMe()),seen=others.filter(m=>m.last_read_at>=mine.created_at);
  el.innerHTML=c.type==="direct"?`<div class="mm-st">${seen.length?"Read "+esc(mxTime(seen[0].last_read_at)):"Delivered"}</div>`
    :`<div class="mm-st">${seen.length?`<span class="rd">${seen.slice(0,5).map(m=>mxPAv(m.user_id,"xs")).join("")}</span>Seen by ${seen.length===others.length?"everyone":seen.length}`:"Delivered"}</div>`}

/* signed links for pictures and files: private bucket, short-lived links, cached a little under their lifetime */
async function mxSign(paths){const need=paths.filter(p=>!MX.signed[p]||MX.signed[p].exp<Date.now());if(!need.length)return true;
  for(let i=0;i<need.length;i+=50){const r=await api("sb_storage","sign",need.slice(i,i+50),{expires:3600}).catch(()=>null);if(!r||!r.ok)return false;
    Object.entries(r.urls||{}).forEach(([p,u])=>{if(u)MX.signed[p]={url:u,exp:Date.now()+50*60e3}})}return true}
async function mxSignVisible(){const imgs=$$("#mxScroll img[data-sp]").filter(i=>!i.getAttribute("src"));if(!imgs.length)return;
  await mxSign([...new Set(imgs.map(i=>i.dataset.sp))]);imgs.forEach(i=>{const s=MX.signed[i.dataset.sp];if(s)i.src=s.url})}
async function mxDownload(path,name){if(!(await mxSign([path]))||!MX.signed[path])return toast("Couldn't open that file. You may no longer have access to it.",{bad:1});
  const u=MX.signed[path].url;window.open(u+(u.includes("?")?"&":"?")+"download="+encodeURIComponent(name||"file"),"_blank")}
async function mxLightbox(path,name){if(!(await mxSign([path]))||!MX.signed[path])return toast("Couldn't open that picture.",{bad:1});
  const d=document.createElement("div");d.className="mx-light";d.innerHTML=`<img src="${esc(MX.signed[path].url)}" alt="${esc(name)}"><div class="mxbar"><button class="btn sm" data-d>${ic("down")}Download</button><button class="btn sm" data-x>Close</button></div>`;
  document.body.appendChild(d);hydrateIcons(d);const close=()=>{d.remove();removeEventListener("keydown",k)},k=e=>{if(e.key==="Escape")close()};addEventListener("keydown",k);
  d.onclick=e=>{if(e.target.closest("[data-d]")){e.stopPropagation();mxDownload(path,name)}else close()}}

/* clicks inside the message list */
function mxFind(mid){return mxT(MX.cur).list.find(m=>m.id===mid)}
async function mxMsgClick(e){
  const mm=e.target.closest(".mm"),mid=mm&&mm.dataset.mid,m=mid&&mxFind(mid);
  const b=e.target.closest("button,[data-goto]");
  if(!b){if(mm&&matchMedia("(hover:none)").matches){$$("#mxScroll .mm.act").forEach(x=>{if(x!==mm)x.classList.remove("act")});mm.classList.toggle("act")}return}
  if(b.dataset.retry){const it=mxOut().find(x=>x.op===b.dataset.retry);if(it){it.state="sending";it.err="";mxOutPut(it);mxPaintMsgs({});mxDeliver(it)}return}
  if(b.dataset.discard){mxOutDrop(b.dataset.discard);mxPaintMsgs({});return}
  if(b.dataset.goto!==undefined&&b.dataset.goto){mxOpenAt(MX.cur,b.dataset.goto);return}
  if(b.dataset.img){mxLightbox(b.dataset.img,b.dataset.name);return}
  if(b.dataset.dl){mxDownload(b.dataset.dl,b.dataset.name);return}
  if(!m)return;
  if(b.dataset.qr||b.dataset.rx){const em=b.dataset.qr||b.dataset.rx,on=!(m.reactions||[]).some(r=>r.emoji===em&&r.user_id===mxMe());mxReact(m,em,on,b);return}
  if(b.hasAttribute("data-rxp")){mxEmojiPop(b,em=>mxReact(m,em,!(m.reactions||[]).some(r=>r.emoji===em&&r.user_id===mxMe())));return}
  if(b.hasAttribute("data-reply")){MX.reply={id:m.id,sender_id:m.sender_id,content:m.content,files:(m.attachments||[]).length};MX.editing=null;mxPaintComposer();$("#mxTa").focus();return}
  if(b.hasAttribute("data-edit")){MX.editing={id:m.id};MX.reply=null;mxPaintComposer(mxEditText(m.content));$("#mxTa").focus();return}
  if(b.hasAttribute("data-pin")){const r=await mxRpc("msg_pin",{p_id:m.id,p_on:!m.pinned});if(!r.ok)return toast(r.error,{bad:1});toast(m.pinned?"Unpinned":"Pinned to this chat");mxFetch(MX.cur,[m.id]);delete MX.pins[MX.cur];mxOvSoon();if(MX.info)mxLoadSide(MX.cur);return}
  if(b.hasAttribute("data-copy")){try{await navigator.clipboard.writeText(mxPlain(m.content));toast("Copied")}catch(x){toast("Couldn't copy",{bad:1})}return}
  if(b.hasAttribute("data-del"))mxConfirmDelete(m);
}
async function mxReact(m,em,on,btn){
  const mine=(m.reactions||[]);m.reactions=on?[...mine,{emoji:em,user_id:mxMe()}]:mine.filter(r=>!(r.emoji===em&&r.user_id===mxMe()));mxPaintMsgs({keep:true});
  const nb=$(`.mm[data-mid="${CSS.escape(m.id)}"] .mm-rx button[data-rx="${CSS.escape(em)}"]`);if(nb){nb.classList.add("pulse")}
  if(on)mxRecent(em);
  const r=await mxRpc("msg_react",{p_id:m.id,p_emoji:em,p_on:on});if(!r.ok){toast(r.error||"Couldn't react.",{bad:1})}mxFetch(MX.cur,[m.id])}
function mxConfirmDelete(m){openModal(`<h2>Delete this message?</h2><p class="muted" style="margin:10px 0 18px;line-height:1.5">It disappears for everyone in this chat${(m.attachments||[]).length?", along with its files":""}. A small "message deleted" note stays so replies still make sense.</p>
  <div style="display:flex;gap:10px;justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn" data-ok style="background:#D62828;color:#fff">Delete</button></div>`,(ov,close)=>{
  $("[data-x]",ov).onclick=close;$("[data-ok]",ov).onclick=async()=>{close();const r=await mxRpc("msg_delete",{p_id:m.id});if(!r.ok)return toast(r.error||"Couldn't delete.",{bad:1});
    const files=(r.data&&r.data.files)||[];if(files.length)api("sb_storage","remove",files).catch(()=>{});toast("Message deleted");mxFetch(MX.cur,[m.id]);mxOvSoon()}})}

/* ---------- composer ---------- */
const MX_Q=MSG_QUICK.split(" ");
function mxEditText(t){return String(t||"").replace(/<@everyone>/g,"@everyone").replace(/<@([0-9a-f-]{36})>/g,(m,id)=>"@"+personById(id).name)}
function mxPaintComposer(text){
  const el=$("#mxComp"),c=MX.byId[MX.cur];if(!el||!c)return;
  const keep=text!==undefined?text:($("#mxTa")?$("#mxTa").value:(MX.draft||""));
  const bar=MX.editing?`<div class="mx-rpl">${ic("edit")}<span>Editing message · <b>Esc</b> to cancel</span><button data-cx aria-label="Cancel editing">${ic("plus")}</button></div>`
    :MX.reply?`<div class="mx-rpl">${ic("undo")}<span>Replying to <b>${esc(mxName(MX.reply.sender_id))}</b>: ${esc(mxPlain(MX.reply.content)||"📎 file")}</span><button data-cx aria-label="Cancel reply">${ic("plus")}</button></div>`:"";
  el.innerHTML=`${bar}<div class="mx-att" id="mxAtt"></div>
    <textarea class="mx-ta" id="mxTa" rows="1" placeholder="Message ${esc(c.type==="group"?c.name:mxFirst(mxOther(c)))}" aria-label="Message" maxlength="8000"></textarea>
    <div class="mx-tb"><button class="mx-ib" data-emo title="Emoji" aria-label="Emoji">${ic("star")}</button><button class="mx-ib" data-att title="Attach files" aria-label="Attach files">${ic("plus")}</button>
      <button class="mx-ib fmt" data-f="b" title="Bold (Ctrl+B)" aria-label="Bold">B</button><button class="mx-ib fmt" data-f="i" title="Italic (Ctrl+I)" aria-label="Italic" style="font-style:italic">I</button>
      <button class="mx-ib fmt hx" data-f="s" title="Strikethrough" aria-label="Strikethrough" style="text-decoration:line-through">S</button><button class="mx-ib fmt hx" data-f="c" title="Code" aria-label="Inline code">&lt;/&gt;</button>
      <button class="mx-ib fmt hx" data-f="l" title="Bulleted list" aria-label="Bulleted list">•</button><button class="mx-ib fmt hx" data-f="a" title="Link" aria-label="Link">${ic("globe")}</button>
      <span class="sp"></span><span class="hint">Enter to send · Shift+Enter for a new line</span><button class="mx-send" id="mxSend" disabled>${ic("send")}${MX.editing?"Save":"Send"}</button></div>
    <input type="file" id="mxFile" multiple hidden>`;
  hydrateIcons(el);const ta=$("#mxTa");ta.value=keep;mxGrow();mxPaintAtts();mxSendState();
  const cx=$("[data-cx]",el);if(cx){cx.firstChild.style.transform="rotate(45deg)";cx.onclick=()=>{const wasEdit=!!MX.editing;MX.reply=null;MX.editing=null;mxPaintComposer(wasEdit?"":undefined)}}
  ta.oninput=()=>{MX.draft=ta.value;mxGrow();mxSendState();mxTypingPing();mxMentionCheck(ta)};
  ta.onkeydown=e=>{
    if(MX.mp&&MX.mp.el){if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();MX.mp.i=(MX.mp.i+(e.key==="ArrowDown"?1:MX.mp.list.length-1))%MX.mp.list.length;mxMpDraw();return}
      if(e.key==="Enter"||e.key==="Tab"){e.preventDefault();mxMpPick(MX.mp.list[MX.mp.i]);return}if(e.key==="Escape"){mxMpClose();return}}
    if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing&&!(matchMedia("(hover:none)").matches)){e.preventDefault();mxSend();return}
    if(e.key==="Escape"&&(MX.reply||MX.editing)){const wasEdit=!!MX.editing;MX.reply=null;MX.editing=null;mxPaintComposer(wasEdit?"":undefined);return}
    if(e.key==="ArrowUp"&&!ta.value&&!MX.editing){const mine=[...mxT(MX.cur).list].reverse().find(m=>m.sender_id===mxMe()&&m.message_type==="text"&&!m.deleted_at);if(mine){e.preventDefault();MX.editing={id:mine.id};mxPaintComposer(mxEditText(mine.content))}}
    if((e.ctrlKey||e.metaKey)&&(e.key==="b"||e.key==="i")){e.preventDefault();mxWrap(e.key)}};
  ta.onpaste=e=>{const fs=[...(e.clipboardData||{}).files||[]];if(fs.length){e.preventDefault();mxAddFiles(fs.map((f,i)=>f.name&&f.name!=="image.png"?f:new File([f],`screenshot-${new Date().toISOString().slice(0,19).replace(/[T:]/g,"-")}${i?"-"+i:""}.${(f.type.split("/")[1]||"png").replace("jpeg","jpg")}`,{type:f.type})))}};
  ta.onblur=()=>setTimeout(mxMpClose,150);
  $("#mxSend").onclick=mxSend;
  $("[data-emo]",el).onclick=e=>{e.stopPropagation();mxEmojiPop($("[data-emo]",el),em=>{mxInsert(em);mxRecent(em)})};
  $("[data-att]",el).onclick=()=>$("#mxFile").click();
  $("#mxFile").onchange=e=>{mxAddFiles([...e.target.files]);e.target.value=""};
  $$("[data-f]",el).forEach(b=>b.onclick=()=>mxWrap(b.dataset.f));
}
function mxGrow(){const ta=$("#mxTa");if(!ta)return;ta.style.height="auto";ta.style.height=Math.min(200,ta.scrollHeight)+"px"}
function mxSendState(){const b=$("#mxSend"),ta=$("#mxTa");if(!b||!ta)return;const busy=MX.atts.some(a=>!a.done&&!a.err),ready=MX.atts.some(a=>a.done);
  b.disabled=busy||!(ta.value.trim()||ready);b.title=busy?"Waiting for files to finish uploading":""}
function mxInsert(s){const ta=$("#mxTa");if(!ta)return;const a=ta.selectionStart,b=ta.selectionEnd;ta.setRangeText(s,a,b,"end");ta.focus();ta.dispatchEvent(new Event("input"))}
function mxWrap(f){const ta=$("#mxTa");if(!ta)return;const a=ta.selectionStart,b=ta.selectionEnd,sel=ta.value.slice(a,b);
  if(f==="l"){const ls=(sel||"").split("\n").map(x=>"- "+x.replace(/^\s*[-*•]\s+/,""));ta.setRangeText((a&&ta.value[a-1]!=="\n"?"\n":"")+ls.join("\n"),a,b,"end")}
  else if(f==="a"){const u=/^https?:\/\//.test(sel)?sel:"https://";ta.setRangeText(sel&&!/^https?:\/\//.test(sel)?`[${sel}](https://)`:u,a,b,"end");if(sel&&!/^https?:\/\//.test(sel)){const p=ta.selectionEnd-1;ta.setSelectionRange(p-8,p)}}
  else{const w={b:"**",i:"*",s:"~~",c:"`"}[f];ta.setRangeText(w+(sel||"")+w,a,b,"select");if(!sel){const p=a+w.length;ta.setSelectionRange(p,p)}else ta.setSelectionRange(a+w.length,a+w.length+sel.length)}
  ta.focus();ta.dispatchEvent(new Event("input"))}
function mxTypingPing(){if(Date.now()-MX.typingSent<3000||!MX.cur)return;MX.typingSent=Date.now();mxRpc("msg_typing",{p_conv:MX.cur})}

/* mentions: @Name in the box, <@user-id> in the stored message (structured, not plain text) */
function mxMentionables(c){const ms=(c.members||[]).filter(m=>m.user_id!==mxMe()).map(m=>({id:m.user_id,name:personById(m.user_id).name}));
  if(c.type==="group"&&mxCan(c))ms.unshift({id:"everyone",name:"everyone"});return ms}
function mxEncode(text,c){const ms=mxMentionables(c).sort((a,b)=>b.name.length-a.name.length),ids=new Set();let everyone=false;
  let out=String(text);
  for(const p of ms){const rx=new RegExp("@"+p.name.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"(?![\\w])","gi");
    out=out.replace(rx,()=>{if(p.id==="everyone")everyone=true;else ids.add(p.id);return `<@${p.id}>`})}
  return {content:out,ids:[...ids],everyone}}
function mxMentionCheck(ta){const c=MX.byId[MX.cur];if(!c)return;const v=ta.value,cur=ta.selectionStart,m=/(^|[\s(])@([^\s@]{0,24})$/.exec(v.slice(0,cur));
  if(!m){mxMpClose();return}const q=m[2].toLowerCase(),list=mxMentionables(c).filter(p=>p.name.toLowerCase().startsWith(q)||p.name.toLowerCase().includes(" "+q)).slice(0,8);
  if(!list.length){mxMpClose();return}
  if(!MX.mp||!MX.mp.el){mxMpClose();const el=document.createElement("div");el.className="mx-pop mx-mp";el.setAttribute("role","listbox");document.body.appendChild(el);MX.mp={el,i:0}}
  MX.mp.list=list;MX.mp.start=cur-m[2].length-1;MX.mp.i=Math.min(MX.mp.i,list.length-1);mxMpDraw();
  const r=ta.getBoundingClientRect(),h=MX.mp.el.offsetHeight;Object.assign(MX.mp.el.style,{left:Math.max(8,Math.min(innerWidth-MX.mp.el.offsetWidth-8,r.left+8))+"px",top:Math.max(8,r.top-h-8)+"px"})}
function mxMpDraw(){const mp=MX.mp;if(!mp)return;mp.el.innerHTML=mp.list.map((p,i)=>`<button type="button" class="${i===mp.i?"on":""}" data-i="${i}">${p.id==="everyone"?`<span class="mav sm"><span class="gav">@</span></span><span>@everyone</span><small>Notify the whole group</small>`
  :`${mxPAv(p.id,"sm")}<span>${esc(p.name)}</span><small>${MX.presence[p.id]?"Online":"Offline"}</small>`}</button>`).join("");
  $$("button",mp.el).forEach(b=>b.onmousedown=e=>{e.preventDefault();mxMpPick(mp.list[+b.dataset.i])})}
function mxMpPick(p){const ta=$("#mxTa"),mp=MX.mp;if(!ta||!mp||!p)return;const v=ta.value,cur=ta.selectionStart,txt="@"+p.name+" ";
  ta.value=v.slice(0,mp.start)+txt+v.slice(cur);const pos=mp.start+txt.length;ta.setSelectionRange(pos,pos);mxMpClose();ta.focus();ta.dispatchEvent(new Event("input"))}
function mxMpClose(){if(MX.mp&&MX.mp.el)MX.mp.el.remove();MX.mp=null}

/* files: checked here for a quick answer, and again by the private bucket (type + 25 MB limit) */
function mxAddFiles(fs){const c=MX.byId[MX.cur];if(!c||!fs.length)return;
  for(const f of fs){if(MX.atts.length>=10){toast("Up to 10 files per message.",{bad:1});break}
    const type=f.type&&MX_TYPES.includes(f.type)?f.type:MX_EXT[(f.name.split(".").pop()||"").toLowerCase()]||"";
    if(!type){toast(`${f.name}: that kind of file can't be shared here.`,{bad:1});continue}
    if(f.size>MX_MAX){toast(`${f.name} is ${mxSize(f.size)}. Files can be up to 25 MB.`,{bad:1});continue}
    if(!f.size){toast(`${f.name} is empty.`,{bad:1});continue}
    const safe=(f.name.replace(/[^A-Za-z0-9._-]+/g,"_").replace(/^[._]+/,"").slice(-120))||"file";
    const a={key:mxId(),file:f,name:f.name.slice(0,200),type,size:f.size,prog:0,done:false,err:"",path:`${c.id}/${mxMe()}/${mxId().slice(0,8)}-${safe}`,thumb:mxIsImg(type)?URL.createObjectURL(f):""};
    MX.atts.push(a);mxUpload(a)}
  mxPaintAtts();mxSendState()}
function mxPaintAtts(){const el=$("#mxAtt");if(!el)return;
  el.innerHTML=MX.atts.map(a=>`<span class="mxch${a.err?" bad":""}" data-k="${a.key}">${a.thumb?`<img src="${esc(a.thumb)}" alt="">`:`<span class="fi" style="font-size:9px;font-weight:800;color:var(--accent-hi)">${esc(mxExt(a.name))}</span>`}<span>${esc(a.name)}</span><small>${a.err?esc(a.err):a.done?esc(mxSize(a.size)):Math.round(a.prog*100)+"%"}</small><button data-rm="${a.key}" aria-label="Remove ${esc(a.name)}">✕</button><i class="pg" style="width:${a.done||a.err?0:Math.round(a.prog*100)}%"></i></span>`).join("");
  $$("[data-rm]",el).forEach(b=>b.onclick=()=>{const a=MX.atts.find(x=>x.key===b.dataset.rm);if(a){if(a.xhr)try{a.xhr.abort()}catch(e){}if(a.done)api("sb_storage","remove",[a.path]).catch(()=>{});if(a.thumb)URL.revokeObjectURL(a.thumb)}
    MX.atts=MX.atts.filter(x=>x.key!==b.dataset.rm);mxPaintAtts();mxSendState()})}
async function mxUpload(a){
  const r=await api("sb_storage","sign_upload",[a.path]).catch(()=>null);
  if(!r||!r.ok){a.err=(r&&r.error)||"Upload refused";mxPaintAtts();mxSendState();return}
  const x=new XMLHttpRequest();a.xhr=x;x.open("PUT",r.url);x.setRequestHeader("Content-Type",a.type);x.setRequestHeader("x-upsert","false");
  x.upload.onprogress=e=>{if(e.lengthComputable){a.prog=e.loaded/e.total;const ch=$(`#mxAtt [data-k="${a.key}"]`);if(ch){$("small",ch).textContent=Math.round(a.prog*100)+"%";$("i.pg",ch).style.width=Math.round(a.prog*100)+"%"}}};
  x.onload=()=>{a.xhr=null;if(x.status>=200&&x.status<300){a.done=true;a.prog=1}else{let m="";try{m=JSON.parse(x.responseText).message}catch(e){}a.err=x.status===413?"Over 25 MB":x.status===415?"File type not allowed":m||("Upload failed ("+x.status+")")}mxPaintAtts();mxSendState()};
  x.onerror=()=>{a.xhr=null;a.err="No connection";mxPaintAtts();mxSendState()};
  x.send(a.file)}

/* sending: shown right away, kept on this device until the database confirms (same id on every retry, so never twice) */
async function mxSend(){
  const ta=$("#mxTa"),c=MX.byId[MX.cur];if(!ta||!c)return;mxMpClose();
  const text=ta.value;if(MX.atts.some(a=>!a.done&&!a.err))return toast("Wait for the files to finish uploading.");
  const atts=MX.atts.filter(a=>a.done);if(!text.trim()&&!atts.length)return;
  const enc=mxEncode(text.replace(/\s+$/,""),c);
  if(MX.editing){const id=MX.editing.id;const r=await mxRpc("msg_edit",{p_id:id,p_content:enc.content,p_mentions:enc.ids,p_everyone:enc.everyone});
    if(!r.ok)return toast(r.error||"Couldn't save the edit.",{bad:1});MX.editing=null;MX.draft="";mxPaintComposer("");mxFetch(c.id,[id]);return}
  const it={op:mxId(),conv:c.id,content:enc.content,reply:MX.reply&&MX.reply.id,replyPrev:MX.reply?{id:MX.reply.id,sender_id:MX.reply.sender_id,content:MX.reply.content}:null,
    mentions:enc.ids,everyone:enc.everyone,atts:atts.map(a=>({path:a.path,name:a.name,type:a.type,size:a.size})),at:new Date().toISOString(),state:"sending",tries:0};
  mxOutPut(it);atts.forEach(a=>{if(a.thumb)URL.revokeObjectURL(a.thumb)});MX.atts=[];MX.reply=null;MX.draft="";
  mxPaintComposer("");$("#mxTa").focus();mxPaintMsgs({bottom:true,fresh:["pend:"+it.op]});MX.typingSent=0;
  mxDeliver(it)}
async function mxDeliver(it){
  if(it._busy)return;it._busy=true;it.tries=(it.tries||0)+1;
  const r=await mxRpc("msg_send",{p_conv:it.conv,p_client_op_id:it.op,p_content:it.content,p_reply_to:it.reply||null,p_mentions:it.mentions||[],p_everyone:!!it.everyone,p_attachments:it.atts||[]});
  it._busy=false;
  if(r.ok){mxOutDrop(it.op);await mxFetch(it.conv,[r.data.id]);mxOvSoon(100);return}
  const cur=mxOut().find(x=>x.op===it.op);if(!cur)return;
  if(r.offline||r.status>=500||!r.status&&/connection|offline|respond/i.test(r.error||"")){cur.state="waiting";cur.err=""}else{cur.state="failed";cur.err=r.error||"Not sent"}
  mxOutPut(cur);if(cur.conv===MX.cur&&S.page==="msgs")mxPaintMsgs({keep:true})}
function mxFlushOut(){mxOut().filter(x=>x.state!=="failed").forEach(x=>{if(Date.now()-Date.parse(x.at)>2500||x.state==="waiting")mxDeliver(x)})}

/* ---------- emoji picker (searchable, recent ones first) ---------- */
const MX_EMO=MSG_EMOJI.map(s=>{const [cat,...rest]=s.split("|");return {cat,list:rest.map(x=>{const i=x.indexOf(" ");return {e:x.slice(0,i),k:x.slice(i+1)}})}});
function mxRecent(em){const r=[em,...getP("emojiRecent",[]).filter(x=>x!==em)].slice(0,16);setP("emojiRecent",r)}
function mxClosePops(){$$(".mx-pop").forEach(p=>p.remove());mxMpClose()}
function mxPlace(el,anchor){const r=anchor.getBoundingClientRect(),w=el.offsetWidth,h=el.offsetHeight;
  let top=r.top-h-8;if(top<8)top=Math.min(innerHeight-h-8,r.bottom+8);el.style.left=Math.max(8,Math.min(innerWidth-w-8,r.left+r.width/2-w/2))+"px";el.style.top=Math.max(8,top)+"px"}
function mxEmojiPop(anchor,pick){
  mxClosePops();const el=document.createElement("div");el.className="mx-pop mx-emo";el.setAttribute("role","dialog");el.setAttribute("aria-label","Emoji");
  const rec=getP("emojiRecent",[]);
  el.innerHTML=`<div class="quick">${MX_Q.map(e=>`<button data-e="${e}" aria-label="${e}">${e}</button>`).join("")}</div><input placeholder="Search emoji" aria-label="Search emoji">
   <div class="cats">${["🕘",...MX_EMO.map(c=>c.list[0].e)].map((e,i)=>`<button data-c="${i}" class="${i===0?"on":""}" title="${i?esc(MX_EMO[i-1].cat):"Recent"}">${e}</button>`).join("")}</div><div class="grid"></div>`;
  document.body.appendChild(el);const grid=$(".grid",el),inp=$("input",el);
  const draw=q=>{q=(q||"").trim().toLowerCase();let h="";
    if(q){const hits=MX_EMO.flatMap(c=>c.list).filter(x=>x.k.includes(q)||x.e===q);h=hits.length?hits.slice(0,96).map(x=>`<button data-e="${x.e}" title="${esc(x.k)}">${x.e}</button>`).join(""):`<div class="none">No emoji found</div>`}
    else{if(rec.length)h+=`<h6 data-sec="0">Recently used</h6>`+rec.map(e=>`<button data-e="${esc(e)}">${esc(e)}</button>`).join("");
      MX_EMO.forEach((c,i)=>{h+=`<h6 data-sec="${i+1}">${esc(c.cat)}</h6>`+c.list.map(x=>`<button data-e="${x.e}" title="${esc(x.k)}">${x.e}</button>`).join("")})}
    grid.innerHTML=h};
  draw("");inp.oninput=()=>draw(inp.value);
  $$(".cats button",el).forEach(b=>b.onclick=()=>{const h=$(`h6[data-sec="${b.dataset.c}"]`,grid);if(h)grid.scrollTop=h.offsetTop-grid.offsetTop;$$(".cats button",el).forEach(x=>x.classList.toggle("on",x===b))});
  el.addEventListener("mousedown",e=>{const b=e.target.closest("[data-e]");if(b){e.preventDefault();pick(b.dataset.e);mxClosePops()}});
  el.addEventListener("click",e=>e.stopPropagation());
  mxPlace(el,anchor);if(!matchMedia("(hover:none)").matches)inp.focus();
}
document.addEventListener("click",e=>{if(!e.target.closest(".mx-pop"))$$(".mx-pop:not(.mx-mp)").forEach(p=>p.remove())});
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&$(".mx-pop:not(.mx-mp)"))$$(".mx-pop:not(.mx-mp)").forEach(p=>p.remove())});

/* ---------- notifications ---------- */
function mxNotesPop(anchor){
  if($(".mx-nt")){mxClosePops();return}mxClosePops();const el=document.createElement("div");el.className="mx-pop mx-nt";el.setAttribute("role","dialog");el.setAttribute("aria-label","Message notifications");
  document.body.appendChild(el);el.addEventListener("click",e=>e.stopPropagation());mxPaintNotes();
  const r=anchor.getBoundingClientRect();el.style.top=(r.bottom+8)+"px";el.style.left=Math.max(8,Math.min(innerWidth-el.offsetWidth-8,r.right-el.offsetWidth))+"px";mxNotes()}
function mxPaintNotes(){const el=$(".mx-nt");if(!el)return;const un=MX.notes.filter(n=>!n.is_read).length;
  const can="Notification" in window,on=getP("msgAlerts",false)&&can&&Notification.permission==="granted";
  el.innerHTML=`<div class="hd"><b>Notifications</b>${un?`<button data-all>Mark all as read</button>`:""}</div>
   <div class="mxls">${MX.notes.length?MX.notes.map(n=>`<button class="it${n.is_read?"":" un"}" data-n="${esc(n.id)}">${mxPAv(n.actor_id,"sm")}<span class="tx">${mxNoteText(n)}${n.preview?`<span>${esc(mxPlain(n.preview))}</span>`:""}<small>${esc(ago(n.created_at))}</small></span></button>`).join("")
     :`<div class="mx-empty" style="padding:30px 10px"><div class="bub">${ic("bell")}</div>Mentions, replies and direct messages show up here.</div>`}</div>
   <div class="ft"><span>Desktop alerts when Leafline is in the background</span><button class="tgl${on?" on":""}" data-al role="switch" aria-checked="${on}" aria-label="Desktop alerts"${can?"":" disabled"}></button></div>`;
  hydrateIcons(el);
  const all=$("[data-all]",el);if(all)all.onclick=async()=>{await mxRpc("msg_mark_all_read");MX.notes.forEach(n=>n.is_read=true);mxBadges();mxPaintNotes()};
  $$("[data-n]",el).forEach(b=>b.onclick=async()=>{const n=MX.notes.find(x=>x.id===b.dataset.n);if(!n)return;mxClosePops();
    if(!n.is_read){n.is_read=true;mxBadges();api("sb_rpc","msg_mark_read",{p_conv:n.conversation_id}).catch(()=>{})}mxOpenAt(n.conversation_id,n.message_id)});
  const al=$("[data-al]",el);if(al)al.onclick=async()=>{let want=!(getP("msgAlerts",false)&&Notification.permission==="granted");
    if(want&&Notification.permission!=="granted"){try{want=(await Notification.requestPermission())==="granted"}catch(e){want=false}if(!want)toast("Alerts are blocked for Leafline in this browser's settings.",{bad:1})}
    setP("msgAlerts",want);mxPaintNotes()}}
async function mxPinsPop(anchor){
  if($(".mx-pins")){mxClosePops();return}mxClosePops();const el=document.createElement("div");el.className="mx-pop mx-nt mx-pins";el.addEventListener("click",e=>e.stopPropagation());
  el.innerHTML=`<div class="hd"><b>Pinned messages</b></div><div class="mxls"><div class="mx-empty" style="padding:24px">Loading…</div></div>`;document.body.appendChild(el);
  const r=anchor.getBoundingClientRect();el.style.top=(r.bottom+8)+"px";el.style.left=Math.max(8,Math.min(innerWidth-el.offsetWidth-8,r.right-el.offsetWidth))+"px";
  const p=await mxRpc("msg_pins",{p_conv:MX.cur});const ls=$(".mxls",el);if(!ls)return;
  ls.innerHTML=p.ok&&p.data.length?p.data.map(m=>`<button class="mx-pinr" data-pj="${esc(m.id)}"><b>${esc(mxName(m.sender_id))} · ${esc(mxWhen(m.created_at))}</b><span>${esc(mxPlain(m.content)||"📎 file")}</span></button>`).join("")
    :`<div class="mx-empty" style="padding:24px">${p.ok?"Nothing pinned yet. Hover a message and press the pin to keep it here.":esc(p.error)}</div>`;
  $$("[data-pj]",ls).forEach(b=>b.onclick=()=>{mxClosePops();mxOpenAt(MX.cur,b.dataset.pj)})}

/* ---------- details panel ---------- */
async function mxLoadSide(cid){if(!cid)return;const [p,f]=await Promise.all([mxRpc("msg_pins",{p_conv:cid}),mxRpc("msg_files",{p_conv:cid,p_limit:30})]);
  if(p.ok)MX.pins[cid]=p.data||[];if(f.ok)MX.files[cid]=f.data||[];if(MX.cur===cid&&MX.info)mxPaintInfo()}
function mxPaintInfo(){
  const box=$("#mxInfoIn"),c=MX.byId[MX.cur];if(!box)return;if(!c||!MX.info){box.innerHTML="";return}
  const pins=MX.pins[c.id],files=MX.files[c.id],can=mxCan(c),g=c.type==="group";
  let h=`<div class="mx-ih"><h4>${g?"Group details":"Details"}</h4><button class="mx-ib" data-close aria-label="Close details">${ic("plus")}</button></div>`;
  if(g){h+=`<div class="mx-pf"><button class="mx-gpic" data-pic title="Change the group picture" aria-label="Change the group picture" style="border-radius:24px">${mxCAv(c,"big")}</button>
      <h3>${esc(c.name)}</h3><div class="ds">${c.description?esc(c.description):`<span class="muted">No description</span>`}</div>
      <div class="sub">Created by ${esc(mxName(c.created_by))} · ${esc(new Date(c.created_at).toLocaleDateString([],{month:"short",day:"numeric",year:"numeric"}))}</div>
      <div class="acts"><button class="btn sm" data-ren>${ic("edit")}Edit name &amp; description</button></div><input type="file" id="mxPic" accept="image/png,image/jpeg,image/webp" hidden></div>
    <div class="mx-blk"><h5>Members · ${(c.members||[]).length}<button data-add>+ Add people</button></h5>${(c.members||[]).map(m=>`<div class="mx-mem">${mxPAv(m.user_id,"sm")}<span class="nm" data-au="${esc(m.user_id)}">${esc(personById(m.user_id).name)}${m.user_id===mxMe()?" (you)":""}</span>${m.role!=="member"?`<small>${m.role==="owner"?"Owner":"Admin"}</small>`:""}
      ${can&&m.user_id!==mxMe()&&(m.role!=="owner"||(S.me&&S.me.role==="admin"))?`<button class="rm" data-kick="${esc(m.user_id)}" title="Remove from group" aria-label="Remove ${esc(personById(m.user_id).name)}">${ic("trash")}</button>`:""}</div>`).join("")}</div>`}
  else{const o=mxOther(c),p=personFull(o),on=MX.presence[o];
    h+=`<div class="mx-pf">${mxPAv(o,"big")}<h3>${esc(p.name)}</h3><div class="sub">${esc([p.ext&&p.ext.title,p.role==="admin"?"Admin":"Rep"].filter(Boolean).join(" · "))}</div>
      <div class="sub" style="color:${on?"var(--accent-hi)":"var(--muted)"}">${on?"● Online now":"Offline"}</div>${p.ext&&p.ext.bio?`<div class="ds">${esc(p.ext.bio)}</div>`:""}
      <div class="acts"><button class="btn sm" data-prof>${ic("user")}View profile</button></div></div>`}
  h+=`<div class="mx-blk"><h5>Pinned messages</h5>${pins===undefined?`<div class="muted" style="font-size:12.5px">Loading…</div>`:pins.length?pins.slice(0,8).map(m=>`<button class="mx-pinr" data-pj="${esc(m.id)}"><b>${esc(mxName(m.sender_id))} · ${esc(mxWhen(m.created_at))}</b><span>${esc(mxPlain(m.content)||"📎 file")}</span></button>`).join(""):`<div class="muted" style="font-size:12.5px">Nothing pinned yet.</div>`}</div>
   <div class="mx-blk"><h5>Shared files</h5>${files===undefined?`<div class="muted" style="font-size:12.5px">Loading…</div>`:files.length?files.map(f=>`<button class="mx-fl" data-fdl="${esc(f.path)}" data-name="${esc(f.name)}"><span class="fi">${esc(mxExt(f.name))}</span><span>${esc(f.name)}</span><small>${esc(mxSize(f.size))}</small></button>`).join(""):`<div class="muted" style="font-size:12.5px">No files shared yet.</div>`}</div>
   <div class="mx-blk"><h5>Settings</h5>
    <div class="mx-tog">Mute notifications<button class="tgl${c.muted?" on":""}" data-mute role="switch" aria-checked="${!!c.muted}" aria-label="Mute"></button></div>
    <div class="mx-tog">Pin to the top<button class="tgl${c.pinned?" on":""}" data-pinc role="switch" aria-checked="${!!c.pinned}" aria-label="Pin conversation"></button></div>
    <div class="mx-tog">${c.archived?"Archived":"Archive"}<button class="tgl${c.archived?" on":""}" data-arch role="switch" aria-checked="${!!c.archived}" aria-label="Archive"></button></div>
    ${g?`<button class="btn sm mx-danger" data-leave style="margin-top:8px">${ic("logout")}Leave group</button>`:""}</div>`;
  box.innerHTML=h;hydrateIcons(box);
  const x=$("[data-close]",box);x.firstChild.style.transform="rotate(45deg)";x.onclick=()=>{MX.info=false;mxRender()};
  const pref=(k,v)=>async()=>{const r=await mxRpc("msg_set_prefs",{p_conv:c.id,[k]:v});if(!r.ok)return toast(r.error,{bad:1});await mxOverview(true)};
  $("[data-mute]",box).onclick=pref("p_muted",!c.muted);$("[data-pinc]",box).onclick=pref("p_pinned",!c.pinned);
  $("[data-arch]",box).onclick=async()=>{await pref("p_archived",!c.archived)();toast(c.archived?"Moved back to your chats":"Archived. It comes back when someone writes.")};
  $$("[data-pj]",box).forEach(b=>b.onclick=()=>{if(innerWidth<=860){MX.info=false;mxRender()}mxOpenAt(c.id,b.dataset.pj)});
  $$("[data-fdl]",box).forEach(b=>b.onclick=()=>mxIsImg((files.find(f=>f.path===b.dataset.fdl)||{}).type)?mxLightbox(b.dataset.fdl,b.dataset.name):mxDownload(b.dataset.fdl,b.dataset.name));
  const pf=$("[data-prof]",box);if(pf)pf.onclick=()=>personModal(personFull(mxOther(c)));
  const ad=$("[data-add]",box);if(ad)ad.onclick=()=>mxAddPeople(c);
  $$("[data-kick]",box).forEach(b=>b.onclick=()=>mxKick(c,b.dataset.kick));
  const lv=$("[data-leave]",box);if(lv)lv.onclick=()=>mxLeaveGroup(c);
  const rn=$("[data-ren]",box);if(rn)rn.onclick=()=>mxEditGroup(c);
  const pc=$("[data-pic]",box);if(pc){pc.onclick=()=>$("#mxPic").click();$("#mxPic").onchange=e=>{const f=e.target.files[0];e.target.value="";if(f)mxGroupPic(c,f)}}
}
function mxEditGroup(c){openModal(`<h2>Edit group</h2><div class="fg"><div style="grid-column:1/3"><label class="l" for="mxGn">Name</label><input class="inp" id="mxGn" maxlength="80" value="${esc(c.name)}"></div>
  <div style="grid-column:1/3"><label class="l" for="mxGd">Description</label><textarea class="inp" id="mxGd" maxlength="500" rows="3" style="height:auto;padding:10px 12px;resize:vertical">${esc(c.description||"")}</textarea></div></div>
  <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok>Save</button></div>`,(ov,close)=>{
  $("[data-x]",ov).onclick=close;$("[data-ok]",ov).onclick=async()=>{const r=await mxRpc("msg_update_group",{p_conv:c.id,p_name:$("#mxGn",ov).value,p_description:$("#mxGd",ov).value});
    if(!r.ok)return toast(r.error,{bad:1});close();toast("Group updated");await mxOverview(true)}})}
async function mxGroupPic(c,f){if(!/^image\/(png|jpeg|webp)$/.test(f.type))return toast("Pick a JPG, PNG or WebP picture.",{bad:1});
  try{const url=URL.createObjectURL(f),im=new Image();await new Promise((ok,no)=>{im.onload=ok;im.onerror=no;im.src=url});
    const s=Math.min(im.naturalWidth,im.naturalHeight),cv=document.createElement("canvas");cv.width=cv.height=256;
    cv.getContext("2d").drawImage(im,(im.naturalWidth-s)/2,(im.naturalHeight-s)/2,s,s,0,0,256,256);URL.revokeObjectURL(url);
    const data=cv.toDataURL("image/jpeg",.86),r=await api("sb_group_picture",data);if(!r||!r.ok)return toast((r&&r.error)||"Couldn't upload the picture.",{bad:1});
    const u=await mxRpc("msg_update_group",{p_conv:c.id,p_avatar_url:r.url});if(!u.ok)return toast(u.error,{bad:1});toast("Group picture updated");await mxOverview(true)}
  catch(e){toast("Couldn't read that picture.",{bad:1})}}
function mxKick(c,uid){openModal(`<h2>Remove ${esc(personById(uid).name)}?</h2><p class="muted" style="margin:10px 0 18px;line-height:1.5">They stop seeing this group and its messages. Everyone sees that they were removed.</p>
  <div style="display:flex;gap:10px;justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn" data-ok style="background:#D62828;color:#fff">Remove</button></div>`,(ov,close)=>{
  $("[data-x]",ov).onclick=close;$("[data-ok]",ov).onclick=async()=>{close();const r=await mxRpc("msg_remove_member",{p_conv:c.id,p_user:uid});if(!r.ok)return toast(r.error,{bad:1});toast("Removed");await mxOverview(true)}})}
function mxLeaveGroup(c){openModal(`<h2>Leave "${esc(c.name)}"?</h2><p class="muted" style="margin:10px 0 18px;line-height:1.5">You'll stop getting its messages. Someone in the group can add you back.</p>
  <div style="display:flex;gap:10px;justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn" data-ok style="background:#D62828;color:#fff">Leave group</button></div>`,(ov,close)=>{
  $("[data-x]",ov).onclick=close;$("[data-ok]",ov).onclick=async()=>{close();const r=await mxRpc("msg_remove_member",{p_conv:c.id,p_user:mxMe()});if(!r.ok)return toast(r.error,{bad:1});
    toast("You left the group");MX.cur=null;MX.info=false;delete MX.threads[c.id];await mxOverview(true);mxRender()}})}

/* ---------- new conversation / add people ---------- */
function mxPeoplePicker(ov,{multi,exclude=[],onChange}){
  const sel=new Set();const box=$(".mx-pick",ov),q=$("[data-pq]",ov),chips=$(".mx-chips",ov);
  const draw=()=>{const t=(q.value||"").trim().toLowerCase(),ppl=teamList().filter(([id,n])=>id!==mxMe()&&!exclude.includes(id)&&(!t||n.toLowerCase().includes(t)))
      .sort((a,b)=>(MX.presence[b[0]]?1:0)-(MX.presence[a[0]]?1:0)||a[1].localeCompare(b[1]));
    box.innerHTML=ppl.length?ppl.map(([id,n])=>{const p=personFull(id);return `<button type="button" class="${sel.has(id)?"on":""}" data-p="${esc(id)}">${mxPAv(id)}<span class="nm">${esc(n)}<small>${MX.presence[id]?"Online":"Offline"}${p.ext&&p.ext.title?" · "+esc(p.ext.title):""}</small></span>${multi?`<span class="ck">${ic("check")}</span>`:""}</button>`}).join("")
      :`<div class="mx-empty" style="padding:20px">Nobody matches.</div>`;
    hydrateIcons(box);$$("[data-p]",box).forEach(b=>b.onclick=()=>{const id=b.dataset.p;if(!multi){onChange([id]);return}sel.has(id)?sel.delete(id):sel.add(id);draw();onChange([...sel])});
    if(chips)chips.innerHTML=[...sel].map(id=>`<span>${mxPAv(id,"xs")}${esc(personById(id).name)}</span>`).join("")};
  q.oninput=draw;draw();setTimeout(()=>q.focus(),120);return sel}
function mxNewChat(mode){
  openModal(`<h2>New conversation</h2><div class="mx-seg"><button data-m="direct" class="${mode==="direct"?"on":""}">Direct message</button><button data-m="group" class="${mode==="group"?"on":""}">Group chat</button></div>
   <div data-g style="display:${mode==="group"?"block":"none"}"><div class="fg" style="margin-top:6px"><div style="grid-column:1/3"><label class="l" for="mxNg">Group name</label><input class="inp" id="mxNg" maxlength="80" placeholder="e.g. Sales floor"></div>
     <div style="grid-column:1/3"><label class="l" for="mxNd">Description (optional)</label><input class="inp" id="mxNd" maxlength="500" placeholder="What is this group for?"></div></div></div>
   <input class="inp" data-pq placeholder="Search teammates" style="width:100%;margin-top:12px" aria-label="Search teammates"><div class="mx-chips"></div><div class="mx-pick"></div>
   <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok style="display:${mode==="group"?"":"none"}" disabled>Create group</button></div>`,(ov,close)=>{
    let m=mode,picked=[];const ok=$("[data-ok]",ov);
    const sync=()=>{ok.disabled=!(picked.length&&$("#mxNg",ov).value.trim());ok.textContent=picked.length?`Create group with ${picked.length}`:"Create group"};
    const start=()=>mxPeoplePicker(ov,{multi:m==="group",onChange:async ids=>{if(m==="direct"){close();mxStartDm(ids[0])}else{picked=ids;sync()}}});
    $$("[data-m]",ov).forEach(b=>b.onclick=()=>{m=b.dataset.m;$$("[data-m]",ov).forEach(x=>x.classList.toggle("on",x===b));$("[data-g]",ov).style.display=m==="group"?"block":"none";ok.style.display=m==="group"?"":"none";picked=[];start();sync()});
    $("#mxNg",ov).oninput=sync;$("[data-x]",ov).onclick=close;start();
    ok.onclick=async()=>{ok.disabled=true;const r=await mxRpc("msg_create_group",{p_name:$("#mxNg",ov).value,p_description:$("#mxNd",ov).value,p_members:picked});
      if(!r.ok){ok.disabled=false;return toast(r.error||"Couldn't create the group.",{bad:1})}close();toast("Group created");await mxOverview(true);mxOpen(r.data)}})}
function mxAddPeople(c){const ex=(c.members||[]).map(m=>m.user_id);
  openModal(`<h2>Add people to ${esc(c.name)}</h2><p class="muted" style="margin:6px 0 0;font-size:13px">They'll see this group's messages, including earlier ones. Your other chats stay private.</p>
   <input class="inp" data-pq placeholder="Search teammates" style="width:100%;margin-top:12px"><div class="mx-chips"></div><div class="mx-pick"></div>
   <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px"><button class="btn" data-x>Cancel</button><button class="btn pri" data-ok disabled>Add</button></div>`,(ov,close)=>{
    let picked=[];const ok=$("[data-ok]",ov);mxPeoplePicker(ov,{multi:true,exclude:ex,onChange:ids=>{picked=ids;ok.disabled=!ids.length;ok.textContent=ids.length?`Add ${ids.length}`:"Add"}});
    $("[data-x]",ov).onclick=close;ok.onclick=async()=>{const r=await mxRpc("msg_add_members",{p_conv:c.id,p_users:picked});if(!r.ok)return toast(r.error,{bad:1});close();toast(`Added ${r.data}`);await mxOverview(true)}})}
/* ======================= end Messages ======================= */

'''


def inject(ui):
    """Adds Messages to the shared page."""
    import json
    data = "const MSG_EMOJI=" + json.dumps(list(MSG_EMOJI), ensure_ascii=False) + ";const MSG_QUICK=" + json.dumps(MSG_QUICK, ensure_ascii=False) + ";\n"
    css_at, js_at = "</style>\n</head>", "</script>\n</body>"
    assert ui.count(css_at) == 1 and ui.count(js_at) == 1
    return ui.replace(css_at, MSG_CSS + css_at, 1).replace(js_at, data + MSG_JS + js_at, 1)
