'use strict';
/* Omensite Journal — local-first trading journal. All data stays in this browser (IndexedDB). */
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uid=()=>Date.now().toString(36)+Math.random().toString(36).slice(2,7);
const MINUS='−';
const fmt$=v=>(v<0?MINUS:'')+'$'+Math.abs(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const fmt$0=v=>(v<0?MINUS:v>0?'+':'')+'$'+Math.abs(Math.round(v)).toLocaleString();
const fmtK=v=>(v<0?MINUS:v>0?'+':'')+(Math.abs(v)>=1000?(Math.abs(v)/1000).toFixed(1)+'k':Math.round(Math.abs(v)));
const fmtR=v=>isFinite(v)?(v>=0?'+':MINUS)+Math.abs(v).toFixed(2)+'R':'—';
const cls=v=>v>0?'is-gain':v<0?'is-loss':'';
const toast=m=>{const t=$('#toast');t.textContent=m;t.classList.add('s');setTimeout(()=>t.classList.remove('s'),1800)};

/* ---------- UI kit (Omensite design system) ---------- */
/* Icons: Lucide paths, ISC licence. */
const ICONS={"layout-dashboard":"<rect width=\"7\" height=\"9\" x=\"3\" y=\"3\" rx=\"1\"/><rect width=\"7\" height=\"5\" x=\"14\" y=\"3\" rx=\"1\"/><rect width=\"7\" height=\"9\" x=\"14\" y=\"12\" rx=\"1\"/><rect width=\"7\" height=\"5\" x=\"3\" y=\"16\" rx=\"1\"/>",
"book-open":"<path d=\"M12 7v14\"/><path d=\"M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z\"/>",
"plus":"<path d=\"M5 12h14\"/><path d=\"M12 5v14\"/>",
"calendar-days":"<path d=\"M8 2v4\"/><path d=\"M16 2v4\"/><rect width=\"18\" height=\"18\" x=\"3\" y=\"4\" rx=\"2\"/><path d=\"M3 10h18\"/><path d=\"M8 14h.01\"/><path d=\"M12 14h.01\"/><path d=\"M16 14h.01\"/><path d=\"M8 18h.01\"/><path d=\"M12 18h.01\"/><path d=\"M16 18h.01\"/>",
"target":"<circle cx=\"12\" cy=\"12\" r=\"10\"/><circle cx=\"12\" cy=\"12\" r=\"6\"/><circle cx=\"12\" cy=\"12\" r=\"2\"/>",
"settings":"<path d=\"M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z\"/><circle cx=\"12\" cy=\"12\" r=\"3\"/>",
"search":"<circle cx=\"11\" cy=\"11\" r=\"8\"/><path d=\"m21 21-4.3-4.3\"/>",
"x":"<path d=\"M18 6 6 18\"/><path d=\"m6 6 12 12\"/>",
"chevron-right":"<path d=\"m9 18 6-6-6-6\"/>",
"triangle-alert":"<path d=\"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3\"/><path d=\"M12 9v4\"/><path d=\"M12 17h.01\"/>",
"check":"<path d=\"M20 6 9 17l-5-5\"/>",
"download":"<path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\"/><polyline points=\"7 10 12 15 17 10\"/><line x1=\"12\" x2=\"12\" y1=\"15\" y2=\"3\"/>",
"upload":"<path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\"/><polyline points=\"17 8 12 3 7 8\"/><line x1=\"12\" x2=\"12\" y1=\"3\" y2=\"15\"/>",
"panel-left":"<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\"/><path d=\"M9 3v18\"/>",
"info":"<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M12 16v-4\"/><path d=\"M12 8h.01\"/>",
"arrow-up-right":"<path d=\"M7 7h10v10\"/><path d=\"M7 17 17 7\"/>",
"arrow-down-right":"<path d=\"m7 7 10 10\"/><path d=\"M17 7v10H7\"/>",
"chart-line":"<path d=\"M3 3v16a2 2 0 0 0 2 2h16\"/><path d=\"m19 9-5 5-4-4-3 3\"/>",
"image":"<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" ry=\"2\"/><circle cx=\"9\" cy=\"9\" r=\"2\"/><path d=\"m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21\"/>",
"external-link":"<path d=\"M15 3h6v6\"/><path d=\"M10 14 21 3\"/><path d=\"M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6\"/>",
"sun":"<circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 2v2\"/><path d=\"M12 20v2\"/><path d=\"m4.93 4.93 1.41 1.41\"/><path d=\"m17.66 17.66 1.41 1.41\"/><path d=\"M2 12h2\"/><path d=\"M20 12h2\"/><path d=\"m6.34 17.66-1.41 1.41\"/><path d=\"m19.07 4.93-1.41 1.41\"/>",
"moon":"<path d=\"M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z\"/>"};
const ic=(n,s=16,c='')=>`<svg class="om-icon ${c}" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]||''}</svg>`;
const head=(over,title,sub='',actions='',pre='')=>`<header class="om-page-head"><div class="om-page-titles">${pre}<div class="om-overline">${over}</div><h1 class="om-page-title">${title}</h1>${sub?`<p class="om-page-sub">${sub}</p>`:''}</div>${actions?`<div class="om-page-actions">${actions}</div>`:''}</header>`;
const card=(title,body,o={})=>`<section class="om-card ${o.cls||''}">${title?`<header class="om-card-head"><div><h3 class="om-card-title">${title}</h3>${o.sub?`<p class="om-card-sub">${o.sub}</p>`:''}</div>${o.actions?`<div class="om-card-actions">${o.actions}</div>`:''}</header>`:''}${body}</section>`;
const metric=(l,v,c='',foot='')=>`<div class="om-card om-metric"><span class="om-metric-label" title="${l}">${l}</span><div class="om-metric-value om-num ${c}">${v}</div><div class="om-metric-foot">${foot}</div></div>`;
const stat=(l,v,c='',sub='')=>`<div class="om-stat"><span class="om-stat-label">${l}</span><span class="om-stat-value om-num ${c}">${v}</span>${sub?`<span class="om-stat-sub">${sub}</span>`:''}</div>`;
const empty=(icon,title,body,action='')=>`<div class="om-empty"><span class="om-empty-icon">${ic(icon,20)}</span><h3 class="om-empty-title">${title}</h3>${body?`<p class="om-empty-body">${body}</p>`:''}${action?`<div class="om-empty-actions">${action}</div>`:''}</div>`;
const notice=(title,body)=>`<div class="om-notice om-notice-caution">${ic('triangle-alert')}<div class="om-notice-body"><strong>${title}</strong><div>${body}</div></div></div>`;
const gradeB=(g,lg)=>g?`<span class="om-grade om-grade-${g==='A+'||g==='A'?'hi':g==='B'?'mid':'lo'} ${lg?'om-grade-lg':''}" title="Grade ${esc(g)}">${esc(g)}</span>`:'';
const sideTag=s=>`<span class="om-side-tag ${s==='Long'?'is-long':'is-short'}">${ic(s==='Long'?'arrow-up-right':'arrow-down-right',14)}${esc(s)}</span>`;
const pills=(xs,c='')=>xs.map(x=>`<span class="om-pill ${c}">${esc(x)}</span>`).join('');

/* ---------- Shell: sidebar, theme, mobile nav ---------- */
const NAV=[{v:'dash',l:'Dashboard',i:'layout-dashboard'},{v:'trades',l:'Trades',i:'book-open',b:'nb-trades'},{v:'new',l:'Log Trade',i:'plus'},{g:'Routine'},{v:'cal',l:'News Calendar',i:'calendar-days'},{v:'plan',l:'Daily Plan',i:'target'},{g:'Workspace'},{v:'settings',l:'Settings',i:'settings'}];
$('#nav').innerHTML=NAV.map(n=>n.g?`<div class="om-sidebar-group">${n.g}</div>`:`<button type="button" class="om-nav" data-v="${n.v}">${ic(n.i,18)}<span class="om-nav-label">${n.l}</span>${n.b?`<span class="om-nav-badge om-num" id="${n.b}"></span>`:''}</button>`).join('');
$$('[data-ic]').forEach(e=>e.innerHTML=ic(e.dataset.ic,+e.dataset.s||16));
const store=(k,v)=>{try{v==null?localStorage.removeItem(k):localStorage.setItem(k,v)}catch(e){}},stored=k=>{try{return localStorage.getItem(k)}catch(e){return null}};
const setCompact=c=>{$('#sidebar').classList.toggle('is-compact',c);$$('#sidebar .om-nav').forEach(b=>c?b.title=b.textContent.trim():b.removeAttribute('title'))};
setCompact(stored('om-compact')==='1');
$('#collapse').onclick=()=>{const c=!$('#sidebar').classList.contains('is-compact');setCompact(c);store('om-compact',c?'1':null)};
$('#menu').onclick=()=>document.body.classList.toggle('nav-open');$('#scrim').onclick=()=>document.body.classList.remove('nav-open');
$('#quick').onclick=()=>go('new');
const isDark=()=>{const t=document.documentElement.dataset.theme;return t?t==='dark':!matchMedia('(prefers-color-scheme: light)').matches};
const paintTheme=()=>{const d=isDark();$('#theme').innerHTML=ic(d?'sun':'moon');$('#theme').setAttribute('aria-label',d?'Switch to light theme':'Switch to dark theme');$('#theme').title=d?'Light theme':'Dark theme'};
$('#theme').onclick=()=>{const t=isDark()?'light':'dark';document.documentElement.dataset.theme=t;store('om-theme',t);paintTheme()};paintTheme();

/* ---------- IndexedDB ---------- */
let db;
function openDB(){return new Promise((res,rej)=>{const q=indexedDB.open('omensite-journal',1);
 q.onupgradeneeded=()=>{const d=q.result;['trades','shots','plans','kv'].forEach(n=>d.objectStoreNames.contains(n)||d.createObjectStore(n,{keyPath:'id'}))};
 q.onsuccess=()=>{db=q.result;res()};q.onerror=()=>rej(q.error)})}
const tx=(s,m='readonly')=>db.transaction(s,m).objectStore(s);
const all=s=>new Promise(r=>{const q=tx(s).getAll();q.onsuccess=()=>r(q.result)});
const get=(s,id)=>new Promise(r=>{const q=tx(s).get(id);q.onsuccess=()=>r(q.result)});
const put=(s,v)=>new Promise(r=>{const q=tx(s,'readwrite').put(v);q.onsuccess=()=>r()});
const del=(s,id)=>new Promise(r=>{const q=tx(s,'readwrite').delete(id);q.onsuccess=()=>r()});
const clear=s=>new Promise(r=>{const q=tx(s,'readwrite').clear();q.onsuccess=()=>r()});
async function kv(k,def){const v=await get('kv',k);return v?v.v:def}
const setkv=(k,v)=>put('kv',{id:k,v});

/* ---------- Domain ---------- */
const PV={ES:50,MES:5,NQ:20,MNQ:2,YM:5,MYM:0.5,RTY:50,M2K:5,CL:1000,MCL:100,GC:100,MGC:10,SI:5000,'6E':125000,ZB:1000,STOCK:1};
const SESSIONS=['Asia','London','NY AM','NY Lunch','NY PM'];
const KILLZONES=['None','Asia KZ','London KZ (2-5 ET)','NY AM KZ (7-10 ET)','Silver Bullet 3-4 ET','Silver Bullet 10-11 ET','Silver Bullet 2-3 PM ET','London Close','PM Session'];
const ICT=['Fair Value Gap','Inverse FVG','Order Block','Breaker Block','Mitigation Block','Liquidity Sweep (BSL)','Liquidity Sweep (SSL)','Market Structure Shift','Break of Structure','OTE 62-79%','Silver Bullet','Judas Swing','Power of 3 (AMD)','SMT Divergence','Balanced Price Range','Turtle Soup','NWOG/NDOG','Equal Highs/Lows','Premium/Discount'];
const BIAS=['Bullish','Bearish','Neutral'];
const MISTAKES=['FOMO','Revenge trade','Moved stop','Oversized','Overtrading','Early exit','Late entry','No setup','Ignored news','Chased','Broke daily limit'];
const EMOTIONS=['Calm','Confident','Anxious','Greedy','Fearful','Frustrated','Bored','Euphoric'];
const DEF_CHECK=['HTF bias identified','Draw on liquidity marked','Liquidity taken before entry','Displacement / MSS confirmed','Entry in discount (long) / premium (short)','Inside a kill zone','No high-impact news within window','Stop beyond structure, R ≥ 2'];
const hourET=d=>+new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',hour12:false}).format(d)%24;

function calc(t){
 const pv=t.instrument==='STOCK'?1:(PV[t.instrument]||+t.pointValue||1),dir=t.side==='Short'?-1:1;
 const qty=+t.qty||0,e=+t.entry;
 const exits=(t.exits&&t.exits.length?t.exits:[{price:t.exit,qty:t.qty}]).filter(x=>x.price!==''&&x.price!=null&&+x.qty);
 let gross=0,eq=0;exits.forEach(x=>{gross+=(+x.price-e)*dir*(+x.qty)*pv;eq+=+x.qty});
 const avgExit=eq?exits.reduce((s,x)=>s+ +x.price*+x.qty,0)/eq:NaN;
 const fees=+t.fees||0,net=t.pnlOverride!==''&&t.pnlOverride!=null&&!isNaN(+t.pnlOverride)?+t.pnlOverride:gross-fees;
 const riskPts=t.stop!==''&&t.stop!=null?Math.abs(e-+t.stop):NaN,risk=riskPts*pv*qty;
 const R=risk>0?net/risk:NaN;
 const points=eq?(avgExit-e)*dir:NaN;
 const mae=t.maePrice!==''&&t.maePrice!=null&&riskPts?Math.abs(e-+t.maePrice)/riskPts:NaN;
 const mfe=t.mfePrice!==''&&t.mfePrice!=null&&riskPts?Math.abs(+t.mfePrice-e)/riskPts:NaN;
 const tgtR=t.target&&riskPts?Math.abs(+t.target-e)/riskPts:NaN;
 const hold=t.entryTime&&t.exitTime?(new Date(t.exitTime)-new Date(t.entryTime))/60000:NaN;
 return {net,gross,R,points,risk,mae,mfe,tgtR,hold,avgExit,open:!eq}
}
const enrich=ts=>ts.map(t=>({...t,c:calc(t)})).sort((a,b)=>(a.entryTime||'').localeCompare(b.entryTime||''));

let S={view:'dash',trades:[],edit:null,filter:{acct:'All',from:'',to:''}};
async function load(){S.trades=enrich(await all('trades'))}

/* ---------- Router ---------- */
$('#nav').addEventListener('click',e=>{const b=e.target.closest('[data-v]');if(b)go(b.dataset.v)});
async function go(v,arg){S.view=v;const nv=v==='view'?'trades':v;
 $$('#nav [data-v]').forEach(b=>{const on=b.dataset.v===nv;b.classList.toggle('is-active',on);on?b.setAttribute('aria-current','page'):b.removeAttribute('aria-current')});
 document.body.classList.remove('nav-open');
 await load();$('#nb-trades').textContent=S.trades.length||'';
 const f={dash,trades,new:()=>form(arg),cal,plan,settings,view:()=>viewTrade(arg)}[v];await f();
 const a=$('#app');a.classList.remove('om-page-anim');void a.offsetWidth;a.classList.add('om-page-anim');window.scrollTo(0,0)}

/* ---------- Dashboard ---------- */
function filtered(){const f=S.filter;return S.trades.filter(t=>!t.c.open&&(f.acct==='All'||t.account===f.acct)&&(!f.from||(t.entryTime||'')>=f.from)&&(!f.to||(t.entryTime||'').slice(0,10)<=f.to))}
function stats(ts){const n=ts.length,w=ts.filter(t=>t.c.net>0),l=ts.filter(t=>t.c.net<0);
 const gw=w.reduce((s,t)=>s+t.c.net,0),gl=-l.reduce((s,t)=>s+t.c.net,0),net=gw-gl;
 const Rs=ts.map(t=>t.c.R).filter(isFinite);let eq=0,pk=0,dd=0;ts.forEach(t=>{eq+=t.c.net;pk=Math.max(pk,eq);dd=Math.max(dd,pk-eq)});
 return {n,w:w.length,l:l.length,wr:n?w.length/n:0,pf:gl?gw/gl:(gw?Infinity:0),net,exp:n?net/n:0,avgR:Rs.length?Rs.reduce((a,b)=>a+b,0)/Rs.length:NaN,sumR:Rs.reduce((a,b)=>a+b,0),
 aw:w.length?gw/w.length:0,al:l.length?-gl/l.length:0,dd}}
function group(ts,keyFn){const m={};ts.forEach(t=>{[].concat(keyFn(t)).filter(k=>k!==''&&k!=null).forEach(k=>(m[k]=m[k]||[]).push(t))});
 return Object.entries(m).map(([k,v])=>({k,...stats(v)})).sort((a,b)=>b.net-a.net)}
function bars(title,rows){if(!rows.length)return card(title,'<p class="om-none">No data yet</p>');
 const mx=Math.max(...rows.map(r=>Math.abs(r.net)),1);
 return card(title,`<div class="om-bars"><div class="om-bars-row om-bars-head"><span>Group</span><span class="num">n · Win</span><span></span><span class="num">Net P&amp;L</span></div>${rows.map(r=>`<div class="om-bars-row"><span class="om-bars-k" title="${esc(r.k)}">${esc(r.k)}</span><span class="om-bars-n om-num">${r.n} · ${(r.wr*100|0)}%</span><span class="om-bars-track"><i class="${r.net<0?'is-loss':'is-gain'}" style="left:${r.net<0?50-Math.abs(r.net)/mx*50:50}%;width:${Math.abs(r.net)/mx*50}%"></i></span><span class="om-bars-v om-num ${cls(r.net)}">${fmt$(r.net)}</span></div>`).join('')}</div>`,{sub:`${rows.length} group${rows.length===1?'':'s'}`})}
function equitySVG(ts){if(ts.length<1)return '<div class="om-chart-empty">Log closed trades to see your equity curve.</div>';
 const W=800,H=240;let e=0;const pts=[0,...ts.map(t=>e+=t.c.net)];const mn=Math.min(...pts),mx=Math.max(...pts),rg=mx-mn||1;
 const X=i=>i*W/Math.max(pts.length-1,1),Y=v=>(mx-v)/rg*H,f=v=>(mx-v)/rg;
 const d=pts.map((v,i)=>(i?'L':'M')+X(i).toFixed(1)+','+Y(v).toFixed(1)).join('');
 const lbl=(v,k)=>`<span class="om-equity-lbl om-num" style="top:calc(12px + (100% - 24px) * ${k.toFixed(4)})">${fmt$(v)}</span>`;
 const z=f(0);
 return `<div class="om-equity"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="Equity curve from ${fmt$(0)} to ${fmt$(pts[pts.length-1])}" role="img">
 <line class="om-equity-grid" x1="0" x2="${W}" y1="0" y2="0"/><line class="om-equity-grid" x1="0" x2="${W}" y1="${H}" y2="${H}"/><line class="om-equity-zero" x1="0" x2="${W}" y1="${Y(0)}" y2="${Y(0)}"/>
 <path class="om-equity-area" d="${d}L${X(pts.length-1)},${Y(Math.max(mn,Math.min(mx,0)))}L${X(0)},${Y(Math.max(mn,Math.min(mx,0)))}Z"/><path class="om-equity-line" d="${d}"/></svg>
 ${lbl(mx,0)}${lbl(mn,1)}${z>.12&&z<.88?lbl(0,z):''}</div>`}
function heatmap(ts){const now=S.hm||new Date();const y=now.getFullYear(),m=now.getMonth();const first=new Date(y,m,1),days=new Date(y,m+1,0).getDate();
 const byDay={};ts.forEach(t=>{const d=(t.entryTime||'').slice(0,10);byDay[d]=(byDay[d]||0)+t.c.net});const mx=Math.max(...Object.values(byDay).map(Math.abs),1);
 const mk=`${y}-${String(m+1).padStart(2,'0')}`,mDays=Object.keys(byDay).filter(k=>k.startsWith(mk)),mNet=mDays.reduce((s,k)=>s+byDay[k],0),today=ymd(new Date());
 let h='';['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(d=>h+=`<div class="om-cal-wd">${d}</div>`);
 for(let i=0;i<first.getDay();i++)h+='<div class="om-cal-day is-blank" aria-hidden="true"></div>';
 for(let d=1;d<=days;d++){const k=`${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`,v=byDay[k];
  const st=v==null?'':v>0?'is-up'+(v/mx>.5?' is-strong':''):v<0?'is-down':'';
  h+=`<div class="om-cal-day ${st} ${k===today?'is-today':''}" title="${k}${v!=null?' · '+fmt$(v):''}"><span class="om-cal-d om-num">${d}</span>${v!=null?`<span class="om-cal-net om-num ${cls(v)}"><span class="f">${fmt$0(v)}</span><span class="s">${fmtK(v)}</span></span>`:''}</div>`}
 return `<div class="om-cal-head"><button type="button" class="om-btn om-btn-ghost om-btn-sm om-btn-icononly" id="hmp" aria-label="Previous month">${ic('chevron-right',16,'om-flip')}</button><h4 class="om-cal-title">${first.toLocaleString(undefined,{month:'long',year:'numeric'})}</h4><button type="button" class="om-btn om-btn-ghost om-btn-sm om-btn-icononly" id="hmn" aria-label="Next month">${ic('chevron-right')}</button>
 <span class="om-cal-sum">${mDays.length?`<span class="om-num ${cls(mNet)}">${fmt$(mNet)}</span> across ${mDays.length} day${mDays.length===1?'':'s'}`:'No trades this month'}</span></div><div class="om-cal-grid">${h}</div>`}
function insights(ts){const out=[];if(ts.length<5)return ['Log at least 5 closed trades to unlock insights.'];
 const dims=[['setup',t=>t.ict||[]],['session',t=>t.session],['kill zone',t=>t.killzone],['instrument',t=>t.instrument],['grade',t=>t.grade],['side',t=>t.side]];
 dims.forEach(([n,f])=>{const g=group(ts,f).filter(r=>r.n>=3);if(!g.length)return;const b=g[0],w=g[g.length-1];
  if(b.net>0)out.push(`Best ${n}: <b>${esc(b.k)}</b> — ${fmt$(b.net)} over ${b.n} trades, avg ${fmtR(b.avgR)}.`);
  if(w.net<0&&w!==b)out.push(`Weakest ${n}: <b>${esc(w.k)}</b> — ${fmt$(w.net)} over ${w.n} trades. Consider cutting it.`)});
 const mk=ts.filter(t=>(t.mistakes||[]).length),cl=ts.filter(t=>!(t.mistakes||[]).length);
 if(mk.length)out.push(`Rule-break cost: trades with mistakes netted <b class="${cls(stats(mk).net)}">${fmt$(stats(mk).net)}</b> vs <b class="${cls(stats(cl).net)}">${fmt$(stats(cl).net)}</b> on clean trades.`);
 const cut=ts.filter(t=>isFinite(t.c.mfe)&&isFinite(t.c.R)&&t.c.mfe-t.c.R>1);if(cut.length)out.push(`${cut.length} trades ran 1R+ further than where you exited (MFE). Review your exits.`);
 return out}
async function dash(){const ts=filtered(),s=stats(ts),accts=['All',...new Set(S.trades.map(t=>t.account).filter(Boolean))];const prop=await kv('prop',{});
 let propH='';if(prop.start){const pts=S.trades.filter(t=>!t.c.open&&(!prop.account||t.account===prop.account));let bal=+prop.start,pk=bal;pts.forEach(t=>{bal+=t.c.net;pk=Math.max(pk,bal)});
  const today=new Date().toISOString().slice(0,10),dayPL=pts.filter(t=>(t.entryTime||'').startsWith(today)).reduce((a,t)=>a+t.c.net,0);
  const floor=Math.min(pk-(+prop.trail||0),prop.lockAt?+prop.start:Infinity),room=bal-(pk-(+prop.trail||0)),prog=prop.target?(bal-prop.start)/prop.target:0;
  const meter=(l,v,max,mode,foot)=>{const p=Math.max(0,Math.min(1,max?v/max:0));return `<div class="om-meter om-meter-${mode} ${mode==='drawdown'&&p>=.8?'is-near':''}"><div class="om-meter-head"><span class="om-meter-label">${l}</span><span class="om-meter-val om-num">${fmt$(v)} / ${fmt$(max)}</span></div><div class="om-meter-track" role="meter" aria-valuemin="0" aria-valuemax="${max}" aria-valuenow="${v}" aria-label="${l}"><div class="om-meter-fill" style="width:${(p*100).toFixed(1)}%"></div></div><div class="om-meter-foot om-num">${Math.round(p*100)}% ${foot}</div></div>`};
  const meters=(prop.target?meter('Payout target',bal-prop.start,+prop.target,'target','of profit target'):'')+(prop.daily?meter('Daily loss used',Math.max(0,-dayPL),+prop.daily,'drawdown','of daily loss limit'):'');
  propH=card('Prop firm tracker',`<div class="om-stat-row">${stat('Balance',fmt$(bal),cls(bal-prop.start),'Start '+fmt$(+prop.start))}${stat("Today's P&L",fmt$(dayPL),cls(dayPL))}${stat('Daily loss left',prop.daily?fmt$(+prop.daily+Math.min(dayPL,0)):'—',dayPL<=-prop.daily*.8?'is-warn':'')}${stat('Room to trailing DD',prop.trail?fmt$(room):'—',room<prop.trail*.25?'is-warn':'')}${stat('Payout target',prop.target?Math.round(prog*100)+'%':'—')}</div>${meters?`<div class="om-meters">${meters}</div>`:''}`,{sub:prop.account?esc(prop.account):'All accounts'})}
 const scope=`${S.filter.acct==='All'?'All accounts':esc(S.filter.acct)} · ${S.filter.from||S.filter.to?`${S.filter.from||'start'} → ${S.filter.to||'today'}`:'all time'}`;
 const breakdowns=[bars('By ICT concept',group(ts,t=>t.ict||[])),bars('By setup / model',group(ts,t=>t.setup)),bars('By session',group(ts,t=>t.session)),bars('By kill zone',group(ts,t=>t.killzone)),
 bars('By grade',group(ts,t=>t.grade)),bars('By instrument',group(ts,t=>t.instrument)),bars('Long vs short',group(ts,t=>t.side)),
 bars('By weekday',group(ts,t=>t.entryTime?new Date(t.entryTime).toLocaleDateString(undefined,{weekday:'short'}):'')),
 bars('By entry hour (ET)',group(ts,t=>t.entryTime?String(hourET(new Date(t.entryTime))).padStart(2,'0')+':00':'')),
 bars('By mistake',group(ts,t=>t.mistakes||[])),bars('By emotion (before)',group(ts,t=>t.emoBefore))];
 $('#app').innerHTML=head('Dashboard','Performance overview',`Closed trades only · as of ${new Date().toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric',year:'numeric'})}`,
 `<label class="om-filter"><span>Account</span><select id="fa">${accts.map(a=>`<option ${a===S.filter.acct?'selected':''}>${esc(a)}</option>`).join('')}</select></label>
 <label class="om-filter"><span>From</span><input type="date" id="ff" value="${S.filter.from}"></label><label class="om-filter"><span>To</span><input type="date" id="ft" value="${S.filter.to}"></label>`)+
 `<div class="om-scope"><span class="om-scope-all">${scope}</span><span class="om-scope-n om-num">${s.n} closed trade${s.n===1?'':'s'} · ${S.trades.length} logged</span></div>
 ${S.trades.length?'':`<div class="om-notice">${ic('info')}<div class="om-notice-body"><strong>No trades yet</strong><div>Log your first trade, or import a CSV from your broker in Settings.</div></div><button type="button" class="om-btn om-btn-primary om-btn-sm" onclick="go('new')">${ic('plus',14)}Log trade</button></div>`}
 <div class="om-kpis">${metric('Net P&L',fmt$(s.net),cls(s.net),'After fees')}${metric('Trades',s.n,'',`Closed · ${S.trades.filter(t=>t.c.open).length} open excluded`)}${metric('Win rate',(s.wr*100).toFixed(1)+'%','',`${s.w} win${s.w===1?'':'s'} · ${s.l} loss${s.l===1?'':'es'}`)}${metric('Profit factor',isFinite(s.pf)?s.pf.toFixed(2):'∞','','Gross win ÷ gross loss')}
 ${metric('Expectancy',fmt$(s.exp),cls(s.exp),'Average net per trade')}${metric('Avg R',fmtR(s.avgR),cls(s.avgR),`Total <span class="om-num">${fmtR(s.sumR)}</span>`)}${metric('Avg win / loss',fmt$(s.aw),cls(s.aw),`Avg loss <span class="om-num">${fmt$(s.al)}</span>`)}${metric('Max drawdown',fmt$(-s.dd),cls(-s.dd),'Peak to trough, closed P&L')}</div>
 ${propH}
 <div class="om-grid-2">${card('Equity curve',equitySVG(ts),{sub:'Cumulative net P&L, trade by trade',cls:'om-equity-card'})}${card('Daily P&L calendar',heatmap(ts),{sub:'Net P&L by entry date'})}</div>
 ${card('Insights',`<ul class="om-insights">${insights(ts).map(i=>`<li>${ic('chevron-right',16)}<span>${i}</span></li>`).join('')}</ul>`,{sub:'Best and weakest groups with 3+ trades'})}
 ${ts.length?`<div class="om-breakdowns">${breakdowns.join('')}</div>`:empty('chart-line','No closed trades in this view','Breakdowns by concept, session, kill zone, grade and more appear once trades in this filter are closed.')}`;
 $('#fa').onchange=e=>{S.filter.acct=e.target.value;dash()};$('#ff').onchange=e=>{S.filter.from=e.target.value;dash()};$('#ft').onchange=e=>{S.filter.to=e.target.value;dash()};
 $('#hmp').onclick=()=>{const d=S.hm||new Date();S.hm=new Date(d.getFullYear(),d.getMonth()-1,1);dash()};$('#hmn').onclick=()=>{const d=S.hm||new Date();S.hm=new Date(d.getFullYear(),d.getMonth()+1,1);dash()};
}

/* ---------- Trades list ---------- */
async function trades(){const ts=[...S.trades].reverse();
 $('#app').innerHTML=head('Journal','Trades',`${ts.length} trade${ts.length===1?'':'s'} logged · newest first`,
 ts.length?`<label class="om-searchbox">${ic('search')}<input id="q" placeholder="Search symbol, tag, notes…" aria-label="Search trades"></label><button type="button" class="om-btn om-btn-primary om-btn-md" onclick="go('new')">${ic('plus')}Log trade</button>`:'')+
 (ts.length?`<div class="om-table-wrap"><table class="om-table"><thead><tr><th>Date</th><th>Symbol</th><th>Side</th><th class="num">Qty</th><th class="num">Entry</th><th class="num">Exit</th><th class="num">P&amp;L</th><th class="num">R</th><th>Grade</th><th>Setup / ICT</th><th>Account</th></tr></thead><tbody id="tb">
 ${ts.map(t=>`<tr class="is-clickable" data-id="${t.id}" data-s="${esc([t.symbol,t.instrument,t.setup,...(t.ict||[]),...(t.mistakes||[]),t.notes].join(' ').toLowerCase())}"><td class="om-num om-date">${esc((t.entryTime||'').replace('T',' '))}</td><td class="om-sym">${esc(t.symbol||t.instrument)}</td><td>${sideTag(t.side)}</td><td class="num om-num">${esc(t.qty)}</td><td class="num om-num">${esc(t.entry)}</td><td class="num om-num">${isFinite(t.c.avgExit)?+t.c.avgExit.toFixed(4):'<span class="om-pill">Open</span>'}</td>
 <td class="num om-num ${cls(t.c.net)}">${t.c.open?'—':fmt$(t.c.net)}</td><td class="num om-num ${cls(t.c.R)}">${fmtR(t.c.R)}</td><td>${gradeB(t.grade)}</td><td><div class="om-cell-tags" title="${esc((t.ict||[]).join(' · '))}">${t.setup?`<span>${esc(t.setup)}</span>`:''}${pills((t.ict||[]).slice(0,1))}${(t.ict||[]).length>1?`<span class="om-pill">+${t.ict.length-1}</span>`:''}</div></td><td class="om-muted">${esc(t.account||'')}</td></tr>`).join('')}</tbody></table></div>`
 :empty('book-open','No trades yet','Log your first trade, or import a CSV export from Tradovate, NinjaTrader, Topstep and others in Settings.',`<button type="button" class="om-btn om-btn-primary om-btn-md" onclick="go('new')">${ic('plus')}Log trade</button><button type="button" class="om-btn om-btn-secondary om-btn-md" onclick="go('settings')">${ic('upload')}Import CSV</button>`));
 $$('#tb tr').forEach(r=>r.onclick=()=>go('view',r.dataset.id));
 if(ts.length)$('#q').oninput=e=>{const q=e.target.value.toLowerCase();$$('#tb tr').forEach(r=>r.style.display=r.dataset.s.includes(q)||r.textContent.toLowerCase().includes(q)?'':'none')};
}

/* ---------- News proximity ---------- */
async function newsNear(iso){if(!iso)return [];const ev=await kv('events',[]),win=+(await kv('newsWin',15));const t=new Date(iso).getTime();
 return ev.filter(e=>e.impact==='High'&&e.date&&e.time).filter(e=>Math.abs(new Date(e.date+'T'+e.time).getTime()-t)<=win*60000)}

/* ---------- Trade form ---------- */
const chipSet=(id,opts,sel=[],bad)=>`<div class="om-chiprow chips" id="${id}">${opts.map(o=>`<button type="button" class="om-chip chip ${bad?'bad':''} ${sel.includes(o)?'on':''}" data-v="${esc(o)}">${esc(o)}</button>`).join('')}</div>`;
const pick=id=>$$('#'+id+' .chip.on').map(c=>c.dataset.v);
const fieldset=(l,hint,body)=>`<div class="om-fieldset"><div class="om-fieldset-head"><span class="om-field-label">${l}</span>${hint?`<span class="om-field-hint">${hint}</span>`:''}</div>${body}</div>`;
async function form(id){const t=id?await get('trades',id):{id:uid(),side:'Long',instrument:'NQ',qty:1,session:'NY AM',killzone:'NY AM KZ (7-10 ET)',account:'Personal',entryTime:new Date(Date.now()-new Date().getTimezoneOffset()*6e4).toISOString().slice(0,16),exits:[],ict:[],mistakes:[],checklist:[]};
 const check=await kv('checklist',DEF_CHECK),setups=await kv('setups',['Silver Bullet','2022 Model','Unicorn','OTE Retrace','Turtle Soup']);
 const shots=id?(await all('shots')).filter(s=>s.tradeId===id):[];S.pendingShots=shots.map(s=>({...s}));
 const F=(n,l,v,tp='text',x='',sp='')=>`<label class="om-field ${sp}"><span class="om-field-label" title="${l}">${l}</span><input name="${n}" type="${tp}" value="${esc(v??'')}" ${tp==='number'?'step="any"':''} ${x}></label>`;
 const Sel=(n,l,o,v,sp='')=>`<label class="om-field ${sp}"><span class="om-field-label" title="${l}">${l}</span><select name="${n}">${o.map(x=>`<option ${x===v?'selected':''}>${esc(x)}</option>`).join('')}</select></label>`;
 $('#app').innerHTML=head('Journal',id?'Edit trade':'Log a trade','Execution, ICT context, psychology and charts — P&amp;L and R update as you type.','',id?`<button type="button" class="om-back" onclick="go('view','${id}')">${ic('chevron-right',14,'om-flip')}Back to trade</button>`:'')+`<form id="tf" class="om-stack">
 ${card('Execution',`<div class="om-form-grid">
 ${Sel('instrument','Instrument',Object.keys(PV),t.instrument)}${F('symbol','Symbol / contract',t.symbol,'text','placeholder="e.g. NQZ6, AAPL"')}${Sel('side','Side',['Long','Short'],t.side)}${F('qty','Size (contracts / shares)',t.qty,'number')}
 ${F('entry','Entry price',t.entry,'number','required')}${F('stop','Stop loss',t.stop,'number')}${F('target','Target',t.target,'number')}${F('fees','Fees & commissions ($)',t.fees,'number')}
 ${F('entryTime','Entry time',t.entryTime,'datetime-local')}${F('exitTime','Exit time',t.exitTime,'datetime-local')}${F('maePrice','Worst price against (MAE)',t.maePrice,'number')}${F('mfePrice','Best price in favor (MFE)',t.mfePrice,'number')}
 ${Sel('account','Account',['Personal','Prop / Funded','Evaluation','Sim',...new Set(S.trades.map(x=>x.account).filter(a=>!['Personal','Prop / Funded','Evaluation','Sim'].includes(a)))],t.account,'om-span-2')}${F('pnlOverride','Net P&L override ($)',t.pnlOverride,'number','placeholder="Optional — replaces calculated P&amp;L"','om-span-2')}</div>
 <div class="om-subhead"><h4>Exits</h4><span>Partials and scale-outs · leave empty for an open trade</span></div><div id="exits" class="om-exits"></div>
 <div class="om-inline" style="margin-top:12px"><button type="button" class="om-btn om-btn-secondary om-btn-sm" id="addx">${ic('plus',14)}Add exit</button></div>
 <div id="live" class="om-live"></div><div id="nw" class="om-warns"></div>`,{sub:'Prices, size, timing and excursion'})}
 ${card('ICT context',`<div class="om-form-grid">${Sel('bias','HTF bias',BIAS,t.bias)}${Sel('pd','Entry zone',['Discount','Premium','Equilibrium'],t.pd)}${Sel('session','Session',SESSIONS,t.session)}${Sel('killzone','Kill zone',KILLZONES,t.killzone)}
 ${F('dol','Draw on liquidity',t.dol,'text','placeholder="e.g. PDH 21450, weekly BSL"','om-span-2')}<label class="om-field"><span class="om-field-label">Setup / model</span><input name="setup" list="setups" value="${esc(t.setup||'')}"><datalist id="setups">${setups.map(s=>`<option>${esc(s)}</option>`).join('')}</datalist></label>${F('tf','Entry timeframe',t.tf,'text','placeholder="1m, 5m…"')}</div>
 ${fieldset('ICT concepts present','',chipSet('ict',ICT,t.ict))}
 ${fieldset('Pre-trade checklist','',chipSet('chk',check,t.checklist||[]))}
 ${fieldset('Grade','Auto-set from the checklist · click to override',chipSet('grade',['A+','A','B','C'],[t.grade||'']))}`,{sub:'Bias, liquidity, timing and confluence'})}
 ${card('Psychology',`<div class="om-form-grid">${Sel('emoBefore','Emotion before',['',...EMOTIONS],t.emoBefore)}${Sel('emoAfter','Emotion after',['',...EMOTIONS],t.emoAfter)}${F('confidence','Confidence (1–10)',t.confidence,'number','min=1 max=10')}${Sel('followed','Followed plan?',['Yes','Partially','No'],t.followed)}</div>
 ${fieldset('Mistakes','',chipSet('mis',MISTAKES,t.mistakes,true))}`,{sub:'State of mind and rule breaks'})}
 ${card('Chart screenshots',`<div class="om-drop" id="drop" tabindex="0">${ic('image',20)}<span>Paste (Ctrl/⌘+V) or drag &amp; drop chart images here</span><div class="om-btn-group"><label class="om-btn om-btn-secondary om-btn-sm" style="cursor:pointer">${ic('upload',14)}Browse files<input type="file" id="fi" accept="image/*" multiple hidden></label><button type="button" class="om-btn om-btn-secondary om-btn-sm" id="cap">Capture screen</button></div></div>
 <div class="om-shot-bar"><label class="om-inline om-fine"><span>Next image is</span><select id="stage" class="om-select-sm"><option>Before</option><option selected>Entry</option><option>After exit</option><option>HTF</option></select></label></div><div class="shots" id="shots"></div>`,{sub:'Before, entry, after exit and higher-timeframe context'})}
 ${card('Notes & review',`<div class="om-form-grid cols-2"><label class="om-field"><span class="om-field-label">Why I took it</span><textarea name="notes">${esc(t.notes||'')}</textarea></label><label class="om-field"><span class="om-field-label">Post-trade review / lessons</span><textarea name="review">${esc(t.review||'')}</textarea></label></div>`)}
 <div class="om-form-actions"><button class="om-btn om-btn-primary om-btn-md" type="submit">${ic('check')}Save trade</button><button type="button" class="om-btn om-btn-secondary om-btn-md" onclick="go('trades')">Cancel</button>${id?'<span class="sp"></span><button type="button" class="om-btn om-btn-destructive om-btn-md" id="dl">Delete trade</button>':''}</div></form>`;
 const exBox=$('#exits'),addEx=(x={})=>{const d=document.createElement('div');d.className='om-exit ex';d.innerHTML=`<label class="om-field"><span class="om-field-label">Exit price</span><input class="xp" type="number" step="any" value="${esc(x.price??'')}"></label><label class="om-field"><span class="om-field-label">Qty</span><input class="xq" type="number" step="any" value="${esc(x.qty??'')}"></label><button type="button" class="om-btn om-btn-secondary om-btn-md om-btn-icononly del" aria-label="Remove exit">${ic('x')}</button>`;
  $('.del',d).onclick=()=>{d.remove();upd()};exBox.append(d)};
 (t.exits&&t.exits.length?t.exits:(t.exit!=null&&t.exit!==''?[{price:t.exit,qty:t.qty}]:[{}])).forEach(addEx);$('#addx').onclick=()=>addEx();
 $$('.chips').forEach(c=>c.onclick=e=>{const ch=e.target.closest('.chip');if(!ch)return;if(c.id==='grade'){$$('.chip',c).forEach(x=>x!==ch&&x.classList.remove('on'));S.gradeManual=true}ch.classList.toggle('on');if(c.id==='chk'&&!S.gradeManual)autoGrade(check.length);upd()});
 S.gradeManual=!!t.grade;
 const collect=()=>{const fd=Object.fromEntries(new FormData($('#tf')));return {...t,...fd,exits:$$('.ex').map(d=>({price:$('.xp',d).value,qty:$('.xq',d).value})).filter(x=>x.price!==''),ict:pick('ict'),checklist:pick('chk'),mistakes:pick('mis'),grade:pick('grade')[0]||''}};
 const upd=async()=>{const x=collect(),c=calc(x);$('#live').innerHTML=c.open?`<div class="om-live-open"><span class="om-pill">Open trade</span><span class="om-muted">Add an exit price to calculate P&amp;L and R.</span></div>`:stat('Net',fmt$(c.net),cls(c.net))+stat('R',fmtR(c.R),cls(c.R))+stat('Points',isFinite(c.points)?c.points.toFixed(2):'—')+stat('Risk',isFinite(c.risk)?fmt$(c.risk):'—')+stat('MAE',isFinite(c.mae)?c.mae.toFixed(2)+'R':'—')+stat('MFE',isFinite(c.mfe)?c.mfe.toFixed(2)+'R':'—')+stat('Planned',isFinite(c.tgtR)?c.tgtR.toFixed(2)+'R':'—')+(isFinite(c.hold)?stat('Hold',c.hold<60?Math.round(c.hold)+'m':(c.hold/60).toFixed(1)+'h'):'');
  const n=await newsNear(x.entryTime);$('#nw').innerHTML=n.map(e=>notice('High-impact news near entry',`<b>${esc(e.title)}</b> at ${esc(e.date)} ${esc(e.time)}`)).join('')};
 $('#tf').addEventListener('input',upd);upd();
 renderShots();setupShotInput();
 $('#tf').onsubmit=async e=>{e.preventDefault();const x=collect();delete x.c;delete x.exit;
  if(x.exits.length&&!x.exitTime)x.exitTime=x.entryTime;
  await put('trades',x);const old=(await all('shots')).filter(s=>s.tradeId===x.id);for(const o of old)if(!S.pendingShots.find(p=>p.id===o.id))await del('shots',o.id);
  for(const p of S.pendingShots)await put('shots',{...p,tradeId:x.id});toast('Trade saved');go('view',x.id)};
 if(id)$('#dl').onclick=async()=>{if(!confirm('Delete this trade and its screenshots?'))return;await del('trades',id);for(const s of shots)await del('shots',s.id);toast('Deleted');go('trades')};
}
function autoGrade(total){const n=pick('chk').length,p=total?n/total:0,g=p>=.95?'A+':p>=.75?'A':p>=.5?'B':'C';$$('#grade .chip').forEach(c=>c.classList.toggle('on',c.dataset.v===g&&n>0))}

/* ---------- Screenshots ---------- */
function renderShots(){const b=$('#shots');if(!b)return;b.innerHTML=S.pendingShots.map((s,i)=>`<figure class="shot"><img src="${s.data}" data-i="${i}" alt="${esc(s.stage)} chart screenshot"><figcaption class="cap"><select data-i="${i}" class="st" aria-label="Screenshot stage">${['Before','Entry','After exit','HTF'].map(o=>`<option ${o===s.stage?'selected':''}>${o}</option>`).join('')}</select><span class="om-shot-actions"><button type="button" class="om-btn om-btn-ghost om-btn-sm" data-m="${i}">Markup</button><button type="button" class="om-btn om-btn-ghost om-btn-sm om-btn-icononly" data-x="${i}" aria-label="Remove screenshot">${ic('x',14)}</button></span></figcaption></figure>`).join('');
 $$('img',b).forEach(im=>im.onclick=()=>lightbox(S.pendingShots[im.dataset.i].data));$$('.st',b).forEach(s=>s.onchange=()=>S.pendingShots[s.dataset.i].stage=s.value);
 $$('[data-x]',b).forEach(x=>x.onclick=()=>{S.pendingShots.splice(x.dataset.x,1);renderShots()});$$('[data-m]',b).forEach(x=>x.onclick=()=>markup(+x.dataset.m))}
function fileToData(f){return new Promise(r=>{const fr=new FileReader();fr.onload=()=>r(fr.result);fr.readAsDataURL(f)})}
async function shrink(data,max=2200){const im=await loadImg(data);if(im.width<=max)return data;const c=document.createElement('canvas');c.width=max;c.height=im.height*max/im.width;c.getContext('2d').drawImage(im,0,0,c.width,c.height);return c.toDataURL('image/jpeg',.9)}
const loadImg=src=>new Promise((r,j)=>{const i=new Image();i.onload=()=>r(i);i.onerror=j;i.src=src});
async function addShot(data){S.pendingShots.push({id:uid(),data:await shrink(data),stage:$('#stage').value,added:new Date().toISOString()});renderShots();toast('Screenshot added')}
function setupShotInput(){const d=$('#drop');
 document.onpaste=async e=>{if(S.view!=='new')return;for(const it of e.clipboardData.items)if(it.type.startsWith('image/')){e.preventDefault();addShot(await fileToData(it.getAsFile()))}};
 d.ondragover=e=>{e.preventDefault();d.classList.add('hov')};d.ondragleave=()=>d.classList.remove('hov');
 d.ondrop=async e=>{e.preventDefault();d.classList.remove('hov');for(const f of e.dataTransfer.files)if(f.type.startsWith('image/'))addShot(await fileToData(f))};
 $('#fi').onchange=async e=>{for(const f of e.target.files)addShot(await fileToData(f));e.target.value=''};
 $('#cap').onclick=async()=>{if(!navigator.mediaDevices?.getDisplayMedia)return toast('Screen capture not supported here — use paste or upload');
  try{const st=await navigator.mediaDevices.getDisplayMedia({video:true});const v=document.createElement('video');v.srcObject=st;v.muted=true;await v.play();await new Promise(r=>setTimeout(r,300));
   const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);st.getTracks().forEach(t=>t.stop());addShot(c.toDataURL('image/png'))}catch(e){toast('Capture cancelled')}}}
function lightbox(src){$('#mbox').innerHTML=`<img class="om-lightbox-img" src="${src}" alt="Chart screenshot"><div class="om-modal-foot"><button type="button" class="om-btn om-btn-secondary om-btn-sm" onclick="closeM()">Close</button></div>`;$('#modal').classList.remove('hidden')}
window.closeM=()=>$('#modal').classList.add('hidden');$('#modal').onclick=e=>{if(e.target.id==='modal'||e.target.classList.contains('om-scrim'))closeM()};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#modal').classList.contains('hidden'))closeM()});
async function markup(i){const s=S.pendingShots[i],im=await loadImg(s.data);const tb=(t,l,on='')=>`<button type="button" data-t="${t}" class="om-btn om-btn-secondary om-btn-sm ${on}">${l}</button>`;
 $('#mbox').innerHTML=`<div class="mk"><div class="tools" id="tl">${tb('arrow','↗ Arrow','on')}${tb('box','▭ Box')}${tb('line','― Line')}${tb('pen','✎ Pen')}${tb('text','T Text')}
 <input type="color" id="col" value="#84f5a5" aria-label="Markup color"><select id="lw" class="om-select-sm" aria-label="Line width"><option value="2">Thin</option><option value="4" selected>Medium</option><option value="7">Thick</option></select><button type="button" class="om-btn om-btn-ghost om-btn-sm" id="und">Undo</button><span class="sp"></span><button type="button" class="om-btn om-btn-primary om-btn-sm" id="msv">Save</button><button type="button" class="om-btn om-btn-secondary om-btn-sm" onclick="closeM()">Cancel</button></div><canvas id="cv"></canvas></div>`;
 $('#modal').classList.remove('hidden');const cv=$('#cv'),x=cv.getContext('2d');cv.width=im.width;cv.height=im.height;cv.style.width=Math.min(im.width,innerWidth*.9)+'px';
 let tool='arrow',ops=[],cur=null;const draw=()=>{x.drawImage(im,0,0);[...ops,cur].filter(Boolean).forEach(o=>{x.strokeStyle=x.fillStyle=o.c;x.lineWidth=o.w*cv.width/1000*1.5;x.lineCap='round';
  if(o.t==='box'){x.strokeRect(o.a.x,o.a.y,o.b.x-o.a.x,o.b.y-o.a.y);x.globalAlpha=.12;x.fillRect(o.a.x,o.a.y,o.b.x-o.a.x,o.b.y-o.a.y);x.globalAlpha=1}
  else if(o.t==='line'||o.t==='arrow'){x.beginPath();x.moveTo(o.a.x,o.a.y);x.lineTo(o.b.x,o.b.y);x.stroke();if(o.t==='arrow'){const an=Math.atan2(o.b.y-o.a.y,o.b.x-o.a.x),h=x.lineWidth*5;x.beginPath();x.moveTo(o.b.x,o.b.y);x.lineTo(o.b.x-h*Math.cos(an-.45),o.b.y-h*Math.sin(an-.45));x.lineTo(o.b.x-h*Math.cos(an+.45),o.b.y-h*Math.sin(an+.45));x.closePath();x.fill()}}
  else if(o.t==='pen'){x.beginPath();o.p.forEach((p,j)=>j?x.lineTo(p.x,p.y):x.moveTo(p.x,p.y));x.stroke()}
  else if(o.t==='text'){x.font=`bold ${Math.round(cv.width/45)}px system-ui`;x.fillText(o.s,o.a.x,o.a.y)}})};draw();
 const P=e=>{const r=cv.getBoundingClientRect();return {x:(e.clientX-r.left)*cv.width/r.width,y:(e.clientY-r.top)*cv.height/r.height}};
 $('#tl').onclick=e=>{const b=e.target.closest('[data-t]');if(!b)return;tool=b.dataset.t;$$('#tl [data-t]').forEach(z=>z.classList.toggle('on',z===b))};
 cv.onpointerdown=e=>{const p=P(e),c=$('#col').value,w=+$('#lw').value;if(tool==='text'){const s=prompt('Label text (e.g. FVG, BSL, MSS):');if(s){ops.push({t:'text',a:p,s,c,w});draw()}return}cur={t:tool,a:p,b:p,p:[p],c,w};cv.setPointerCapture(e.pointerId)};
 cv.onpointermove=e=>{if(!cur)return;const p=P(e);cur.b=p;cur.p.push(p);draw()};cv.onpointerup=()=>{if(cur){ops.push(cur);cur=null;draw()}};
 $('#und').onclick=()=>{ops.pop();draw()};$('#msv').onclick=()=>{s.data=cv.toDataURL('image/jpeg',.92);closeM();renderShots();toast('Markup saved')}}

/* ---------- Trade detail ---------- */
async function viewTrade(id){const t=S.trades.find(x=>x.id===id);if(!t)return go('trades');const c=t.c,shots=(await all('shots')).filter(s=>s.tradeId===id),n=await newsNear(t.entryTime);
 const kvl=rows=>`<dl class="om-kv">${rows.map(([l,v])=>`<div><dt>${l}</dt><dd>${v||'<span class="om-faint">—</span>'}</dd></div>`).join('')}</dl>`;
 const when=(t.entryTime||'').replace('T',' ');
 $('#app').innerHTML=`<header class="om-page-head"><div class="om-page-titles"><button type="button" class="om-back" onclick="go('trades')">${ic('chevron-right',14,'om-flip')}All trades</button><div class="om-overline">Trade${when?' · '+esc(when):''}</div><div class="om-page-title-row"><h1 class="om-page-title">${esc(t.symbol||t.instrument)}</h1>${sideTag(t.side)}${gradeB(t.grade,true)}</div><p class="om-page-sub">${[t.account,t.setup,t.session].filter(Boolean).map(esc).join(' · ')||'No account or setup recorded'}</p></div>
 <div class="om-page-actions"><button type="button" class="om-btn om-btn-primary om-btn-md" onclick="go('new','${id}')">Edit trade</button></div></header>
 ${n.map(e=>notice('Taken inside a news window',`<b>${esc(e.title)}</b> (${esc(e.date)} ${esc(e.time)})`)).join('')}
 <div class="om-kpis">${[['Net P&L',c.open?'—':fmt$(c.net),c.open?'':cls(c.net),c.open?'Open trade':'After fees'],['R-multiple',fmtR(c.R),cls(c.R),'Net ÷ initial risk'],['Points',isFinite(c.points)?c.points.toFixed(2):'—','','Avg exit vs entry'],['$ Risk',isFinite(c.risk)?fmt$(c.risk):'—','','Entry to stop × size'],['MAE',isFinite(c.mae)?c.mae.toFixed(2)+'R':'—','','Worst excursion against'],['MFE',isFinite(c.mfe)?c.mfe.toFixed(2)+'R':'—','','Best excursion in favor'],['Captured of MFE',isFinite(c.mfe)&&c.mfe>0&&isFinite(c.R)?Math.round(c.R/c.mfe*100)+'%':'—','','Realized share of MFE'],['Hold time',isFinite(c.hold)?(c.hold<60?Math.round(c.hold)+' min':(c.hold/60).toFixed(1)+' h'):'—','','Entry to final exit']].map(([l,v,k,f])=>metric(l,v,k,f)).join('')}</div>
 <div class="om-grid-2 om-align-start">
 ${card('Details',kvl([['Instrument',esc(t.instrument)],['Size',esc(t.qty)],['Entry',esc(t.entry)],['Stop',esc(t.stop)],['Target',esc(t.target)],['Exits',(t.exits||[]).map(x=>esc(x.qty)+' @ '+esc(x.price)).join(', ')],['Fees',t.fees?fmt$(+t.fees):''],['Entry time',esc((t.entryTime||'').replace('T',' '))],['Exit time',esc((t.exitTime||'').replace('T',' '))],['Account',esc(t.account)]]),{sub:'Execution'})}
 ${card('ICT analysis',kvl([['HTF bias',esc(t.bias)],['Draw on liquidity',esc(t.dol)],['Entry zone',esc(t.pd)],['Session',esc(t.session)],['Kill zone',esc(t.killzone)],['Setup',esc(t.setup)],['Timeframe',esc(t.tf)]])+
 `<div class="om-kv-section"><span class="om-overline">Concepts</span>${(t.ict||[]).length?`<div class="om-pills">${pills(t.ict,'om-pill-accent')}</div>`:'<span class="om-none">No concepts tagged</span>'}</div>
 <div class="om-kv-section"><span class="om-overline">Checklist · ${(t.checklist||[]).length} met</span>${(t.checklist||[]).length?`<ul class="om-checklist">${t.checklist.map(x=>`<li>${ic('check',14)}<span>${esc(x)}</span></li>`).join('')}</ul>`:'<span class="om-none">No checklist items met</span>'}</div>`,{sub:'Context and confluence'})}
 ${card('Psychology',kvl([['Before',esc(t.emoBefore)],['After',esc(t.emoAfter)],['Confidence',esc(t.confidence)],['Followed plan',esc(t.followed)]])+`<div class="om-kv-section"><span class="om-overline">Mistakes</span>${(t.mistakes||[]).length?`<div class="om-pills">${pills(t.mistakes,'om-pill-caution')}</div>`:'<span class="om-none">No mistakes tagged</span>'}</div>`,{sub:'State of mind'})}
 ${card('Notes & review',`<div class="om-notes"><div><span class="om-overline">Why I took it</span><p class="om-prose">${esc(t.notes)||'<span class="om-faint">—</span>'}</p></div><div><span class="om-overline">Review</span><p class="om-prose">${esc(t.review)||'<span class="om-faint">—</span>'}</p></div></div>`)}</div>
 ${card('Charts',shots.length?`<div class="shots">${shots.map(s=>`<figure class="shot"><img src="${s.data}" alt="${esc(s.stage)} chart screenshot" onclick="lightbox(this.src)"><figcaption class="cap">${esc(s.stage)}</figcaption></figure>`).join('')}</div>`:'<p class="om-none">No screenshots</p>',{sub:`${shots.length} screenshot${shots.length===1?'':'s'}`})}`}
window.lightbox=lightbox;window.go=go;

/* ---------- News calendar ---------- */
function weekRange(off=0){const d=new Date();d.setHours(0,0,0,0);d.setDate(d.getDate()-((d.getDay()+6)%7)+off*7);const e=new Date(d);e.setDate(d.getDate()+6);return [d,e]}
const ymd=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
async function cal(){const off=S.wk||0,[a,b]=weekRange(off),ev=(await kv('events',[])).sort((x,y)=>(x.date+x.time).localeCompare(y.date+y.time)),wk=ev.filter(e=>e.date>=ymd(a)&&e.date<=ymd(b));
 const days=[...Array(7)].map((_,i)=>{const d=new Date(a);d.setDate(a.getDate()+i);return d});
 const lnk=(h,l)=>`<a class="om-btn om-btn-secondary om-btn-sm" target="_blank" rel="noopener" href="${h}">${l}${ic('external-link',14)}</a>`;
 $('#app').innerHTML=head('Calendar','News &amp; economic calendar',`${a.toLocaleDateString(undefined,{month:'short',day:'numeric'})} – ${b.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})} · ${wk.length} event${wk.length===1?'':'s'}`,
 `<button type="button" class="om-btn om-btn-secondary om-btn-sm" id="pw">${ic('chevron-right',14,'om-flip')}Prev</button>${off?'<button type="button" class="om-btn om-btn-ghost om-btn-sm" id="tw">This week</button>':''}<button type="button" class="om-btn om-btn-secondary om-btn-sm" id="nw2">Next${ic('chevron-right',14)}</button>`)+
 `<div class="om-grid-2 om-align-start">${card('Live sources',`<p class="om-fine">Omensite Journal has no server, and free economic-calendar feeds don't allow direct browser access, so it doesn't show events it can't verify. Check a live source, then add this week's key releases (times are your local time). High-impact events trigger warnings on trades taken within ${esc(await kv('newsWin',15))} minutes.</p>
 <div class="om-links">${lnk('https://www.forexfactory.com/calendar?week=this','ForexFactory (this week)')}${lnk('https://www.investing.com/economic-calendar/','Investing.com economic')}${lnk('https://www.investing.com/earnings-calendar/','Investing.com earnings')}${lnk('https://www.cmegroup.com/trading-hours.html','CME holiday hours')}${lnk('https://www.nyse.com/markets/hours-calendars','NYSE holidays')}</div>`)}
 ${card('Add event',`<form id="ef" class="om-form-grid cols-2"><label class="om-field"><span class="om-field-label">Date</span><input name="date" type="date" required value="${ymd(a)}"></label><label class="om-field"><span class="om-field-label">Time (local)</span><input name="time" type="time"></label><label class="om-field om-span-2"><span class="om-field-label">Event</span><input name="title" required placeholder="e.g. CPI m/m, FOMC, NVDA earnings"></label>
 <label class="om-field"><span class="om-field-label">Impact</span><select name="impact"><option>High</option><option>Medium</option><option>Low</option></select></label><label class="om-field"><span class="om-field-label">Type</span><select name="kind"><option>Economic (USD)</option><option>Earnings</option><option>Holiday / early close</option><option>Other</option></select></label><div class="om-span-2 om-end"><button class="om-btn om-btn-primary om-btn-md">${ic('plus')}Add event</button></div></form>`)}</div>
 <div class="om-week">${days.map(d=>{const k=ymd(d),es=wk.filter(e=>e.date===k),td=k===ymd(new Date());return `<section class="om-card om-week-day ${td?'is-today':''}"><header><span class="om-num">${d.getDate()}</span><span class="om-overline">${d.toLocaleDateString(undefined,{weekday:'long'})}</span>${td?'<span class="om-pill om-pill-accent">Today</span>':''}</header>
 ${es.length?`<ul class="om-evs">${es.map(e=>`<li class="om-ev ${e.impact==='High'?'is-high':''}"><div class="om-ev-top"><span class="om-num">${esc(e.time||'All day')}</span><span class="om-impact imp-${e.impact==='High'?3:e.impact==='Medium'?2:1}" title="${esc(e.impact)} impact" aria-label="${esc(e.impact)} impact"><i></i><i></i><i></i></span><button type="button" class="om-btn om-btn-ghost om-btn-sm om-btn-icononly" data-d="${e.id}" aria-label="Delete event">${ic('x',14)}</button></div><strong>${esc(e.title)}</strong><span class="om-ev-kind">${esc(e.kind)}</span></li>`).join('')}</ul>`:'<p class="om-none">No events added</p>'}</section>`}).join('')}</div>`;
 $('#pw').onclick=()=>{S.wk=off-1;cal()};$('#nw2').onclick=()=>{S.wk=off+1;cal()};if(off)$('#tw').onclick=()=>{S.wk=0;cal()};
 $('#ef').onsubmit=async e=>{e.preventDefault();const x=Object.fromEntries(new FormData(e.target));x.id=uid();await setkv('events',[...ev,x]);toast('Event added');cal()};
 $$('[data-d]').forEach(b=>b.onclick=async()=>{await setkv('events',ev.filter(e=>e.id!==b.dataset.d));cal()})}

/* ---------- Daily plan ---------- */
async function plan(){const d=S.pd||ymd(new Date()),p=(await get('plans',d))||{id:d},ts=S.trades.filter(t=>(t.entryTime||'').startsWith(d)),s=stats(ts.filter(t=>!t.c.open));
 const recent=(await all('plans')).sort((a,b)=>b.id.localeCompare(a.id)).slice(0,10);
 const T=(n,l,ph)=>`<label class="om-field"><span class="om-field-label">${l}</span><textarea name="${n}" placeholder="${ph}">${esc(p[n]||'')}</textarea></label>`;
 const long=new Date(d+'T12:00').toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric',year:'numeric'});
 $('#app').innerHTML=head('Routine','Daily plan &amp; review',long,`<label class="om-filter"><span>Day</span><input type="date" id="pdd" value="${d}"></label>`)+
 `<form id="pf" class="om-stack"><div class="om-grid-2 om-align-start">${card('Pre-market plan',`<div class="om-form-grid cols-1">
 <label class="om-field"><span class="om-field-label">Daily bias</span><select name="bias">${['','Bullish','Bearish','Neutral / wait'].map(o=>`<option ${o===p.bias?'selected':''}>${o}</option>`).join('')}</select></label>
 ${T('dol','Draw on liquidity','Where is price likely to go? PDH/PDL, weekly highs/lows, equal highs…')}${T('levels','Key levels','PDH, PDL, Asia high/low, London high/low, NWOG, FVGs…')}${T('news',"Today's news",'Check the News Calendar tab')}${T('rules','Rules for today','Max 2 trades, stop after -1R, only A setups…')}</div>`,{sub:'Set before the open'})}
 ${card('End-of-day review',`<div class="om-live" style="margin-top:0;margin-bottom:20px">${stat('Trades',s.n)}${stat('Net',fmt$(s.net),cls(s.net))}${stat('R',fmtR(s.sumR),cls(s.sumR))}</div>
 <div class="om-form-grid cols-2"><label class="om-field"><span class="om-field-label">Did I follow my plan?</span><select name="followed">${['','Yes','Partially','No'].map(o=>`<option ${o===p.followed?'selected':''}>${o}</option>`).join('')}</select></label>
 <label class="om-field"><span class="om-field-label">Mood (1–10)</span><input name="mood" type="number" min="1" max="10" value="${esc(p.mood||'')}"></label><div class="om-span-2 om-form-grid cols-1">${T('went','What went well','')}${T('wrong','What went wrong','')}${T('lesson','Lesson for tomorrow','')}</div></div>`,{sub:'Closed trades entered on this day'})}</div>
 <div class="om-form-actions"><button class="om-btn om-btn-primary om-btn-md">${ic('check')}Save day</button></div></form>
 ${card('Recent days',recent.length?`<div class="om-chiprow">${recent.map(r=>`<button type="button" class="om-chip ${r.id===d?'on':''}" data-day="${r.id}"><span class="om-num">${r.id}</span>${r.bias?`<span class="om-faint">${esc(r.bias)}</span>`:''}</button>`).join('')}</div>`:'<p class="om-none">No saved days yet</p>',{sub:'Last 10 saved plans'})}`;
 $('#pdd').onchange=e=>{S.pd=e.target.value;plan()};$$('[data-day]').forEach(b=>b.onclick=()=>{S.pd=b.dataset.day;plan()});
 $('#pf').onsubmit=async e=>{e.preventDefault();await put('plans',{...p,...Object.fromEntries(new FormData(e.target))});toast('Day saved');plan()}}

/* ---------- Settings / import / export ---------- */
function parseCSV(s){const rows=[];let r=[],f='',q=false;for(let i=0;i<s.length;i++){const ch=s[i];if(q){if(ch=='"'){if(s[i+1]=='"'){f+='"';i++}else q=false}else f+=ch}else if(ch=='"')q=true;else if(ch==','){r.push(f);f=''}else if(ch=='\n'||ch=='\r'){if(ch=='\r'&&s[i+1]=='\n')i++;r.push(f);rows.push(r);r=[];f=''}else f+=ch}
 if(f||r.length){r.push(f);rows.push(r)}return rows.filter(x=>x.some(v=>v.trim()))}
const COLS={symbol:['symbol','contract','instrument','ticker'],side:['side','direction','b/s','action','type'],qty:['qty','quantity','size','contracts','shares','filled qty'],entry:['entry','entry price','buyprice','avg entry','open price','entryprice'],exit:['exit','exit price','sellprice','avg exit','close price','exitprice'],entryTime:['entry time','open time','boughttimestamp','entrytime','date','time'],exitTime:['exit time','close time','soldtimestamp','exittime'],fees:['fees','commission','commissions'],pnl:['pnl','p&l','profit','net p&l','realized p&l','net pnl']};
function mapCSV(rows){const h=rows[0].map(x=>x.trim().toLowerCase()),ix={};for(const[k,al]of Object.entries(COLS))ix[k]=h.findIndex(c=>al.includes(c));
 if(ix.entry<0)throw new Error('Could not find an entry price column. Expected headers like: symbol, side, qty, entry, exit, entry time, exit time, fees, pnl');
 const num=v=>v==null?'':String(v).replace(/[$,()\s]/g,m=>m==='('?'-':'');const dt=v=>{if(!v)return '';const d=new Date(v);return isNaN(d)?'':new Date(d-d.getTimezoneOffset()*6e4).toISOString().slice(0,16)};
 return rows.slice(1).map(r=>{const g=k=>ix[k]>=0?r[ix[k]]:'';const sym=(g('symbol')||'').toUpperCase().trim(),root=Object.keys(PV).sort((a,b)=>b.length-a.length).find(k=>k!=='STOCK'&&sym.startsWith(k)&&/^[A-Z0-9]{0,3}\d?$/.test(sym.slice(k.length)));
  const sd=(g('side')||'').toLowerCase();return {id:uid(),symbol:sym,instrument:root||'STOCK',side:/sell|short|^s$/.test(sd)?'Short':'Long',qty:num(g('qty'))||1,entry:num(g('entry')),exits:g('exit')?[{price:num(g('exit')),qty:num(g('qty'))||1}]:[],entryTime:dt(g('entryTime')),exitTime:dt(g('exitTime')),fees:num(g('fees')),pnlOverride:g('pnl')?num(g('pnl')):'',account:'Imported',ict:[],mistakes:[],checklist:[],imported:true}}).filter(t=>t.entry!=='')}
function download(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
async function settings(){const check=await kv('checklist',DEF_CHECK),prop=await kv('prop',{}),setups=await kv('setups',['Silver Bullet','2022 Model','Unicorn','OTE Retrace','Turtle Soup']),win=await kv('newsWin',15);
 let usage='';if(navigator.storage?.estimate){const e=await navigator.storage.estimate();usage=`Using ${(e.usage/1048576).toFixed(1)} MB of ~${(e.quota/1073741824).toFixed(1)} GB browser storage.`}
 const PF=(n,l,tp='number',ph='')=>`<label class="om-field"><span class="om-field-label">${l}</span><input name="${n}" type="${tp}" value="${esc(prop[n]||'')}" ${ph?`placeholder="${ph}"`:''}></label>`;
 $('#app').innerHTML=head('Workspace','Settings &amp; data','Checklist, setups, prop-firm rules, imports and backups.')+`<div class="om-grid-2 om-align-start">
 ${card('Pre-trade checklist',`<div class="om-form-grid cols-1"><label class="om-field"><span class="om-field-label">Rules (one per line)</span><textarea id="ck" style="min-height:200px">${esc(check.join('\n'))}</textarea></label>
 <label class="om-field"><span class="om-field-label">Your setups / models (one per line)</span><textarea id="su">${esc(setups.join('\n'))}</textarea></label><div><button type="button" class="om-btn om-btn-primary om-btn-md" id="cks">Save checklist &amp; setups</button></div></div>`,{sub:'Grades are auto-set from the share of rules met: ≥95% A+, ≥75% A, ≥50% B, else C.'})}
 ${card('Prop firm rules',`<form id="prf" class="om-form-grid cols-2">${PF('account','Account name','text','Prop / Funded')}${PF('start','Starting balance ($)')}${PF('daily','Daily loss limit ($)')}${PF('trail','Trailing drawdown ($)')}${PF('target','Profit target ($)')}<div class="om-end"><button class="om-btn om-btn-primary om-btn-md">Save rules</button></div></form>
 <div class="om-subhead"><h4>News warning window</h4><span>Flags trades near high-impact events</span></div><div class="om-inline"><input id="nwin" type="number" value="${esc(win)}" aria-label="News warning window in minutes"><span class="om-fine">minutes around high-impact events</span><button type="button" class="om-btn om-btn-secondary om-btn-md" id="nws">Save</button></div>`,{sub:'Powers the prop firm tracker on the dashboard. Leave the account blank to track all accounts.'})}
 ${card('Import trades (CSV)',`<label class="om-drop om-drop-file">${ic('upload',20)}<strong>Choose a CSV file</strong><span>Columns like <i>symbol, side, qty, entry, exit, entry time, exit time, fees, pnl</i> are detected automatically.</span><input type="file" id="csv" accept=".csv,text/csv"></label><div id="csvr" class="om-fine" style="margin-top:12px"></div>`,{sub:'Works with exports from Tradovate, NinjaTrader, Topstep, Webull and others. Rename headers if needed.'})}
 ${card('Export & backup',`<p class="om-fine">Your data lives only in this browser. Back up regularly — clearing site data deletes it. ${usage}</p>
 <div class="om-links"><button type="button" class="om-btn om-btn-primary om-btn-md" id="ex2">${ic('download')}Download full backup (JSON)</button><button type="button" class="om-btn om-btn-secondary om-btn-md" id="ex1">Export trades CSV</button><label class="om-btn om-btn-secondary om-btn-md" style="cursor:pointer">${ic('upload')}Restore backup<input type="file" id="rs" accept=".json" hidden></label></div>
 <div class="om-subhead"><h4>Danger zone</h4><span>Permanently removes every trade, screenshot, plan and setting</span></div><div><button type="button" id="wipe" class="om-btn om-btn-destructive om-btn-md">Erase all data</button></div>`,{sub:'CSV for spreadsheets, JSON for a complete restorable copy'})}</div>`;
 $('#cks').onclick=async()=>{await setkv('checklist',$('#ck').value.split('\n').map(s=>s.trim()).filter(Boolean));await setkv('setups',$('#su').value.split('\n').map(s=>s.trim()).filter(Boolean));toast('Saved')};
 $('#prf').onsubmit=async e=>{e.preventDefault();await setkv('prop',Object.fromEntries(new FormData(e.target)));toast('Prop rules saved')};
 $('#nws').onclick=async()=>{await setkv('newsWin',+$('#nwin').value||15);toast('Saved')};
 $('#csv').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const ts=mapCSV(parseCSV(await f.text()));for(const t of ts)await put('trades',t);$('#csvr').innerHTML=`<span class="is-gain">Imported ${ts.length} trades (account "Imported"). Open them to add ICT tags &amp; screenshots.</span>`;$('#nb-trades').textContent=(await all('trades')).length}catch(err){$('#csvr').innerHTML=`<span class="om-err">${esc(err.message)}</span>`}};
 $('#ex1').onclick=()=>{const H=['date','symbol','instrument','side','qty','entry','avg_exit','stop','target','fees','net_pnl','r_multiple','mae_r','mfe_r','account','session','killzone','setup','ict','grade','mistakes','emotion_before','notes'];
  const q=v=>`"${String(v??'').replace(/"/g,'""')}"`;download('omensite-trades.csv',[H.join(','),...S.trades.map(t=>[t.entryTime,t.symbol,t.instrument,t.side,t.qty,t.entry,isFinite(t.c.avgExit)?t.c.avgExit:'',t.stop,t.target,t.fees,t.c.open?'':t.c.net.toFixed(2),isFinite(t.c.R)?t.c.R.toFixed(2):'',isFinite(t.c.mae)?t.c.mae.toFixed(2):'',isFinite(t.c.mfe)?t.c.mfe.toFixed(2):'',t.account,t.session,t.killzone,t.setup,(t.ict||[]).join('; '),t.grade,(t.mistakes||[]).join('; '),t.emoBefore,t.notes].map(q).join(','))].join('\n'),'text/csv')};
 $('#ex2').onclick=async()=>{const data={app:'omensite-journal',version:1,exported:new Date().toISOString()};for(const s of['trades','shots','plans','kv'])data[s]=await all(s);download(`omensite-backup-${ymd(new Date())}.json`,JSON.stringify(data),'application/json');toast('Backup downloaded')};
 $('#rs').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const d=JSON.parse(await f.text());if(d.app!=='omensite-journal')throw new Error('Not an Omensite backup');if(!confirm('Replace all current data with this backup?'))return;for(const s of['trades','shots','plans','kv']){await clear(s);for(const v of d[s]||[])await put(s,v)}toast('Backup restored');go('dash')}catch(err){alert('Restore failed: '+err.message)}};
 $('#wipe').onclick=async()=>{if(!confirm('Erase ALL trades, screenshots, plans and settings? This cannot be undone.'))return;for(const s of['trades','shots','plans','kv'])await clear(s);toast('All data erased');go('dash')}}

openDB().then(()=>go('dash')).catch(e=>{$('#app').innerHTML=empty('triangle-alert','Browser storage unavailable',`Could not open IndexedDB: ${esc(e&&e.message)}. Private or incognito modes may block it.`)});
