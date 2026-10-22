'use strict';
/* Omensite Journal — local-first trading journal. All data stays in this browser (IndexedDB). */
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uid=()=>Date.now().toString(36)+Math.random().toString(36).slice(2,7);
const fmt$=v=>(v<0?'-':'')+'$'+Math.abs(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtR=v=>isFinite(v)?(v>=0?'+':'')+v.toFixed(2)+'R':'—';
const cls=v=>v>0?'pos':v<0?'neg':'';
const toast=m=>{const t=$('#toast');t.textContent=m;t.classList.add('s');setTimeout(()=>t.classList.remove('s'),1800)};

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
$('#nav').addEventListener('click',e=>{const b=e.target.closest('button');if(b)go(b.dataset.v)});
async function go(v,arg){S.view=v;$$('#nav button').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
 await load();const f={dash,trades,new:()=>form(arg),cal,plan,settings,view:()=>viewTrade(arg)}[v];await f();window.scrollTo(0,0)}

/* ---------- Dashboard ---------- */
function filtered(){const f=S.filter;return S.trades.filter(t=>!t.c.open&&(f.acct==='All'||t.account===f.acct)&&(!f.from||(t.entryTime||'')>=f.from)&&(!f.to||(t.entryTime||'').slice(0,10)<=f.to))}
function stats(ts){const n=ts.length,w=ts.filter(t=>t.c.net>0),l=ts.filter(t=>t.c.net<0);
 const gw=w.reduce((s,t)=>s+t.c.net,0),gl=-l.reduce((s,t)=>s+t.c.net,0),net=gw-gl;
 const Rs=ts.map(t=>t.c.R).filter(isFinite);let eq=0,pk=0,dd=0;ts.forEach(t=>{eq+=t.c.net;pk=Math.max(pk,eq);dd=Math.max(dd,pk-eq)});
 return {n,wr:n?w.length/n:0,pf:gl?gw/gl:(gw?Infinity:0),net,exp:n?net/n:0,avgR:Rs.length?Rs.reduce((a,b)=>a+b,0)/Rs.length:NaN,sumR:Rs.reduce((a,b)=>a+b,0),
 aw:w.length?gw/w.length:0,al:l.length?-gl/l.length:0,dd}}
function group(ts,keyFn){const m={};ts.forEach(t=>{[].concat(keyFn(t)).filter(k=>k!==''&&k!=null).forEach(k=>(m[k]=m[k]||[]).push(t))});
 return Object.entries(m).map(([k,v])=>({k,...stats(v)})).sort((a,b)=>b.net-a.net)}
function bars(title,rows){if(!rows.length)return `<div class="card"><h3>${title}</h3><div class="mut">No data yet</div></div>`;
 const mx=Math.max(...rows.map(r=>Math.abs(r.net)),1);
 return `<div class="card bars"><h3>${title}</h3>${rows.map(r=>`<div class="row"><span title="${esc(r.k)}">${esc(r.k)} <span class="mut">(${r.n}, ${(r.wr*100|0)}%)</span></span><div class="bar"><i style="left:${r.net<0?50-Math.abs(r.net)/mx*50:50}%;width:${Math.abs(r.net)/mx*50}%;background:${r.net<0?'var(--r)':'var(--g)'}"></i></div><span class="${cls(r.net)}">${fmt$(r.net)}</span></div>`).join('')}</div>`}
function equitySVG(ts){if(ts.length<1)return '<div class="mut">Log closed trades to see your equity curve.</div>';
 const W=800,H=220,P=30;let e=0;const pts=[0,...ts.map(t=>e+=t.c.net)];const mn=Math.min(...pts),mx=Math.max(...pts),rg=mx-mn||1;
 const X=i=>P+i*(W-2*P)/Math.max(pts.length-1,1),Y=v=>H-P-(v-mn)/rg*(H-2*P);
 const d=pts.map((v,i)=>(i?'L':'M')+X(i).toFixed(1)+','+Y(v).toFixed(1)).join('');
 return `<svg viewBox="0 0 ${W} ${H}" width="100%"><defs><linearGradient id="eg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#22d3a6" stop-opacity=".35"/><stop offset="1" stop-color="#22d3a6" stop-opacity="0"/></linearGradient></defs>
 <line x1="${P}" x2="${W-P}" y1="${Y(0)}" y2="${Y(0)}" stroke="#2a3447" stroke-dasharray="4"/><path d="${d}L${X(pts.length-1)},${H-P}L${X(0)},${H-P}Z" fill="url(#eg)"/><path d="${d}" fill="none" stroke="#22d3a6" stroke-width="2"/>
 <text x="4" y="${Y(mx)+4}">${fmt$(mx)}</text><text x="4" y="${Y(mn)+4}">${fmt$(mn)}</text></svg>`}
function heatmap(ts){const now=S.hm||new Date();const y=now.getFullYear(),m=now.getMonth();const first=new Date(y,m,1),days=new Date(y,m+1,0).getDate();
 const byDay={};ts.forEach(t=>{const d=(t.entryTime||'').slice(0,10);byDay[d]=(byDay[d]||0)+t.c.net});const mx=Math.max(...Object.values(byDay).map(Math.abs),1);
 let h='';['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(d=>h+=`<div style="background:none;aspect-ratio:auto">${d}</div>`);
 for(let i=0;i<first.getDay();i++)h+='<div style="background:none"></div>';
 for(let d=1;d<=days;d++){const k=`${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`,v=byDay[k];
  const bg=v==null?'':`background:${v>=0?`rgba(34,211,166,${.15+.65*Math.abs(v)/mx})`:`rgba(242,85,90,${.15+.65*Math.abs(v)/mx})`};color:#fff`;
  h+=`<div style="${bg}" title="${k}">${d}${v!=null?`<br><b>${fmt$(v)}</b>`:''}</div>`}
 return `<div class="flex"><button id="hmp">‹</button><b>${first.toLocaleString(undefined,{month:'long',year:'numeric'})}</b><button id="hmn">›</button></div><div class="heat" style="margin-top:8px">${h}</div>`}
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
 const k=(l,v,c='')=>`<div class="card kpi"><div class="l">${l}</div><div class="v ${c}">${v}</div></div>`;
 let propH='';if(prop.start){const pts=S.trades.filter(t=>!t.c.open&&(!prop.account||t.account===prop.account));let bal=+prop.start,pk=bal;pts.forEach(t=>{bal+=t.c.net;pk=Math.max(pk,bal)});
  const today=new Date().toISOString().slice(0,10),dayPL=pts.filter(t=>(t.entryTime||'').startsWith(today)).reduce((a,t)=>a+t.c.net,0);
  const floor=Math.min(pk-(+prop.trail||0),prop.lockAt?+prop.start:Infinity),room=bal-(pk-(+prop.trail||0)),prog=prop.target?(bal-prop.start)/prop.target:0;
  propH=`<div class="card"><h3>Prop firm tracker ${prop.account?'· '+esc(prop.account):''}</h3><div class="grid g4">
  ${k('Balance',fmt$(bal),cls(bal-prop.start))}${k("Today's P&L",fmt$(dayPL),cls(dayPL))}${k('Daily loss left',prop.daily?fmt$(+prop.daily+Math.min(dayPL,0)):'—',dayPL<=-prop.daily*.8?'neg':'')}${k('Room to trailing DD',prop.trail?fmt$(room):'—',room<prop.trail*.25?'neg':'')}${k('Payout target',prop.target?Math.round(prog*100)+'%':'—')}</div>
  ${prop.target?`<div class="bar" style="height:8px"><i style="left:0;width:${Math.max(0,Math.min(100,prog*100))}%;background:var(--a)"></i></div>`:''}</div>`}
 $('#app').innerHTML=`<div class="flex" style="margin-bottom:14px"><h2 class="sp" style="margin:0">Dashboard</h2>
 <select id="fa" style="width:auto">${accts.map(a=>`<option ${a===S.filter.acct?'selected':''}>${esc(a)}</option>`).join('')}</select>
 <input type="date" id="ff" value="${S.filter.from}" style="width:auto"><input type="date" id="ft" value="${S.filter.to}" style="width:auto"></div>
 <div class="grid g4">${k('Net P&L',fmt$(s.net),cls(s.net))}${k('Trades',s.n)}${k('Win rate',(s.wr*100).toFixed(1)+'%')}${k('Profit factor',isFinite(s.pf)?s.pf.toFixed(2):'∞')}${k('Expectancy',fmt$(s.exp),cls(s.exp))}${k('Avg R',fmtR(s.avgR),cls(s.avgR))}${k('Avg win / loss',`<span class="pos">${fmt$(s.aw)}</span> / <span class="neg">${fmt$(s.al)}</span>`)}${k('Max drawdown',fmt$(-s.dd),'neg')}</div>
 ${propH}
 <div class="grid g2"><div class="card"><h3>Equity curve</h3>${equitySVG(ts)}</div><div class="card"><h3>Daily P&L calendar</h3>${heatmap(ts)}</div></div>
 <div class="card"><h3>Insights</h3><ul style="margin:0;padding-left:18px">${insights(ts).map(i=>`<li>${i}</li>`).join('')}</ul></div>
 <div class="grid g2">${bars('By ICT concept',group(ts,t=>t.ict||[]))}${bars('By setup / model',group(ts,t=>t.setup))}${bars('By session',group(ts,t=>t.session))}${bars('By kill zone',group(ts,t=>t.killzone))}
 ${bars('By grade',group(ts,t=>t.grade))}${bars('By instrument',group(ts,t=>t.instrument))}${bars('Long vs short',group(ts,t=>t.side))}
 ${bars('By weekday',group(ts,t=>t.entryTime?new Date(t.entryTime).toLocaleDateString(undefined,{weekday:'short'}):''))}
 ${bars('By entry hour (ET)',group(ts,t=>t.entryTime?String(hourET(new Date(t.entryTime))).padStart(2,'0')+':00':''))}
 ${bars('By mistake',group(ts,t=>t.mistakes||[]))}${bars('By emotion (before)',group(ts,t=>t.emoBefore))}</div>`;
 $('#fa').onchange=e=>{S.filter.acct=e.target.value;dash()};$('#ff').onchange=e=>{S.filter.from=e.target.value;dash()};$('#ft').onchange=e=>{S.filter.to=e.target.value;dash()};
 $('#hmp').onclick=()=>{const d=S.hm||new Date();S.hm=new Date(d.getFullYear(),d.getMonth()-1,1);dash()};$('#hmn').onclick=()=>{const d=S.hm||new Date();S.hm=new Date(d.getFullYear(),d.getMonth()+1,1);dash()};
}

/* ---------- Trades list ---------- */
async function trades(){const ts=[...S.trades].reverse();
 $('#app').innerHTML=`<div class="flex" style="margin-bottom:14px"><h2 class="sp" style="margin:0">Trades</h2><input id="q" placeholder="Search symbol, tag, notes…" style="width:240px"><button class="pri" onclick="go('new')">+ Log Trade</button></div>
 <div class="card tw">${ts.length?`<table><thead><tr><th>Date</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th><th>P&L</th><th>R</th><th>Grade</th><th>Setup / ICT</th><th>Account</th></tr></thead><tbody id="tb">
 ${ts.map(t=>`<tr data-id="${t.id}" data-s="${esc([t.symbol,t.instrument,t.setup,...(t.ict||[]),...(t.mistakes||[]),t.notes].join(' ').toLowerCase())}"><td>${esc((t.entryTime||'').replace('T',' '))}</td><td><b>${esc(t.symbol||t.instrument)}</b></td><td class="${t.side==='Long'?'pos':'neg'}">${t.side}</td><td>${esc(t.qty)}</td><td>${esc(t.entry)}</td><td>${isFinite(t.c.avgExit)?+t.c.avgExit.toFixed(4):'<span class="tag">open</span>'}</td>
 <td class="${cls(t.c.net)}">${t.c.open?'—':fmt$(t.c.net)}</td><td class="${cls(t.c.R)}">${fmtR(t.c.R)}</td><td>${t.grade?`<span class="grade g${t.grade}">${t.grade}</span>`:''}</td><td>${esc(t.setup||'')} ${(t.ict||[]).slice(0,3).map(x=>`<span class="tag">${esc(x)}</span>`).join('')}</td><td>${esc(t.account||'')}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">No trades yet. Log your first trade or import a CSV in Settings.</div>'}</div>`;
 $$('#tb tr').forEach(r=>r.onclick=()=>go('view',r.dataset.id));
 $('#q').oninput=e=>{const q=e.target.value.toLowerCase();$$('#tb tr').forEach(r=>r.style.display=r.dataset.s.includes(q)||r.textContent.toLowerCase().includes(q)?'':'none')};
}

/* ---------- News proximity ---------- */
async function newsNear(iso){if(!iso)return [];const ev=await kv('events',[]),win=+(await kv('newsWin',15));const t=new Date(iso).getTime();
 return ev.filter(e=>e.impact==='High'&&e.date&&e.time).filter(e=>Math.abs(new Date(e.date+'T'+e.time).getTime()-t)<=win*60000)}

/* ---------- Trade form ---------- */
const chipSet=(id,opts,sel=[],bad)=>`<div class="chips" id="${id}">${opts.map(o=>`<span class="chip ${bad?'bad':''} ${sel.includes(o)?'on':''}" data-v="${esc(o)}">${esc(o)}</span>`).join('')}</div>`;
const pick=id=>$$('#'+id+' .chip.on').map(c=>c.dataset.v);
async function form(id){const t=id?await get('trades',id):{id:uid(),side:'Long',instrument:'NQ',qty:1,session:'NY AM',killzone:'NY AM KZ (7-10 ET)',account:'Personal',entryTime:new Date(Date.now()-new Date().getTimezoneOffset()*6e4).toISOString().slice(0,16),exits:[],ict:[],mistakes:[],checklist:[]};
 const check=await kv('checklist',DEF_CHECK),setups=await kv('setups',['Silver Bullet','2022 Model','Unicorn','OTE Retrace','Turtle Soup']);
 const shots=id?(await all('shots')).filter(s=>s.tradeId===id):[];S.pendingShots=shots.map(s=>({...s}));
 const F=(n,l,v,tp='text',x='')=>`<div><label>${l}</label><input name="${n}" type="${tp}" value="${esc(v??'')}" ${tp==='number'?'step="any"':''} ${x}></div>`;
 const Sel=(n,l,o,v)=>`<div><label>${l}</label><select name="${n}">${o.map(x=>`<option ${x===v?'selected':''}>${esc(x)}</option>`).join('')}</select></div>`;
 $('#app').innerHTML=`<h2>${id?'Edit':'Log'} trade</h2><form id="tf">
 <div class="card"><h3>Execution</h3><div class="form">
 ${Sel('instrument','Instrument',Object.keys(PV),t.instrument)}${F('symbol','Symbol / contract (e.g. NQZ6, AAPL)',t.symbol)}${Sel('side','Side',['Long','Short'],t.side)}${F('qty','Size (contracts / shares)',t.qty,'number')}
 ${F('entry','Entry price',t.entry,'number','required')}${F('stop','Stop loss',t.stop,'number')}${F('target','Target',t.target,'number')}${F('fees','Fees & commissions ($)',t.fees,'number')}
 ${F('entryTime','Entry time',t.entryTime,'datetime-local')}${F('exitTime','Exit time',t.exitTime,'datetime-local')}${F('maePrice','Worst price against (MAE)',t.maePrice,'number')}${F('mfePrice','Best price in favor (MFE)',t.mfePrice,'number')}
 ${Sel('account','Account',['Personal','Prop / Funded','Evaluation','Sim',...new Set(S.trades.map(x=>x.account).filter(a=>!['Personal','Prop / Funded','Evaluation','Sim'].includes(a)))],t.account)}${F('pnlOverride','Net P&L override ($, optional)',t.pnlOverride,'number')}</div>
 <h3 style="margin-top:14px">Exits (partials / scale-outs)</h3><div id="exits"></div><button type="button" id="addx">+ Add exit</button> <span class="mut">Leave empty for an open trade.</span>
 <div id="live" class="flex" style="margin-top:12px"></div><div id="nw"></div></div>
 <div class="card"><h3>ICT context</h3><div class="form">${Sel('bias','HTF bias',BIAS,t.bias)}${F('dol','Draw on liquidity',t.dol,'text','placeholder="e.g. PDH 21450, weekly BSL"')}${Sel('pd','Entry zone',['Discount','Premium','Equilibrium'],t.pd)}${Sel('session','Session',SESSIONS,t.session)}${Sel('killzone','Kill zone',KILLZONES,t.killzone)}
 <div><label>Setup / model</label><input name="setup" list="setups" value="${esc(t.setup||'')}"><datalist id="setups">${setups.map(s=>`<option>${esc(s)}</option>`).join('')}</datalist></div>${F('tf','Entry timeframe',t.tf,'text','placeholder="1m, 5m…"')}</div>
 <label style="margin-top:12px">ICT concepts present</label>${chipSet('ict',ICT,t.ict)}
 <label style="margin-top:12px">Pre-trade checklist</label>${chipSet('chk',check,t.checklist||[])}
 <div class="flex" style="margin-top:12px"><div><label>Grade (auto from checklist — click to override)</label>${chipSet('grade',['A+','A','B','C'],[t.grade||''])}</div></div></div>
 <div class="card"><h3>Psychology</h3><div class="form">${Sel('emoBefore','Emotion before',['',...EMOTIONS],t.emoBefore)}${Sel('emoAfter','Emotion after',['',...EMOTIONS],t.emoAfter)}${F('confidence','Confidence 1-10',t.confidence,'number','min=1 max=10')}${Sel('followed','Followed plan?',['Yes','Partially','No'],t.followed)}</div>
 <label style="margin-top:12px">Mistakes</label>${chipSet('mis',MISTAKES,t.mistakes,true)}</div>
 <div class="card"><h3>Chart screenshots</h3><div class="drop" id="drop" tabindex="0">Paste (Ctrl/⌘+V), drag & drop, or <label class="btn" style="display:inline;color:var(--t)">browse<input type="file" id="fi" accept="image/*" multiple hidden></label> chart images · <button type="button" id="cap">Capture screen</button></div>
 <div class="flex" style="margin:8px 0"><label style="margin:0">Next image is:</label><select id="stage" style="width:auto"><option>Before</option><option selected>Entry</option><option>After exit</option><option>HTF</option></select></div><div class="shots" id="shots"></div></div>
 <div class="card"><h3>Notes & review</h3><div class="form" style="grid-template-columns:1fr"><div><label>Why I took it</label><textarea name="notes">${esc(t.notes||'')}</textarea></div><div><label>Post-trade review / lessons</label><textarea name="review">${esc(t.review||'')}</textarea></div></div></div>
 <div class="flex"><button class="pri" type="submit">Save trade</button><button type="button" onclick="history.length;go('trades')">Cancel</button>${id?'<span class="sp"></span><button type="button" class="del" id="dl">Delete trade</button>':''}</div></form>`;
 const exBox=$('#exits'),addEx=(x={})=>{const d=document.createElement('div');d.className='form ex';d.style.marginBottom='6px';d.innerHTML=`<div><label>Exit price</label><input class="xp" type="number" step="any" value="${esc(x.price??'')}"></div><div><label>Qty</label><input class="xq" type="number" step="any" value="${esc(x.qty??'')}"></div><div style="align-self:end"><button type="button" class="del">✕</button></div>`;
  $('.del',d).onclick=()=>{d.remove();upd()};exBox.append(d)};
 (t.exits&&t.exits.length?t.exits:(t.exit!=null&&t.exit!==''?[{price:t.exit,qty:t.qty}]:[{}])).forEach(addEx);$('#addx').onclick=()=>addEx();
 $$('.chips').forEach(c=>c.onclick=e=>{const ch=e.target.closest('.chip');if(!ch)return;if(c.id==='grade'){$$('.chip',c).forEach(x=>x!==ch&&x.classList.remove('on'));S.gradeManual=true}ch.classList.toggle('on');if(c.id==='chk'&&!S.gradeManual)autoGrade(check.length);upd()});
 S.gradeManual=!!t.grade;
 const collect=()=>{const fd=Object.fromEntries(new FormData($('#tf')));return {...t,...fd,exits:$$('.ex').map(d=>({price:$('.xp',d).value,qty:$('.xq',d).value})).filter(x=>x.price!==''),ict:pick('ict'),checklist:pick('chk'),mistakes:pick('mis'),grade:pick('grade')[0]||''}};
 const upd=async()=>{const x=collect(),c=calc(x);$('#live').innerHTML=c.open?'<span class="tag">Open trade</span>':`<span>Net <b class="${cls(c.net)}">${fmt$(c.net)}</b></span><span>R <b class="${cls(c.R)}">${fmtR(c.R)}</b></span><span>Points <b>${isFinite(c.points)?c.points.toFixed(2):'—'}</b></span><span>Risk <b>${isFinite(c.risk)?fmt$(c.risk):'—'}</b></span><span>MAE <b>${isFinite(c.mae)?c.mae.toFixed(2)+'R':'—'}</b></span><span>MFE <b>${isFinite(c.mfe)?c.mfe.toFixed(2)+'R':'—'}</b></span><span>Planned <b>${isFinite(c.tgtR)?c.tgtR.toFixed(2)+'R':'—'}</b></span>${isFinite(c.hold)?`<span>Hold <b>${c.hold<60?Math.round(c.hold)+'m':(c.hold/60).toFixed(1)+'h'}</b></span>`:''}`;
  const n=await newsNear(x.entryTime);$('#nw').innerHTML=n.map(e=>`<div class="warn">⚠ High-impact news near entry: <b>${esc(e.title)}</b> at ${esc(e.date)} ${esc(e.time)}</div>`).join('')};
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
function renderShots(){const b=$('#shots');if(!b)return;b.innerHTML=S.pendingShots.map((s,i)=>`<div class="shot"><img src="${s.data}" data-i="${i}"><div class="cap"><select data-i="${i}" class="st" style="width:auto;padding:1px">${['Before','Entry','After exit','HTF'].map(o=>`<option ${o===s.stage?'selected':''}>${o}</option>`).join('')}</select><span><button type="button" data-m="${i}">✎ Markup</button> <button type="button" class="del" data-x="${i}">✕</button></span></div></div>`).join('');
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
function lightbox(src){$('#mbox').innerHTML=`<img src="${src}" style="max-width:92vw;max-height:86vh;display:block"><div style="text-align:right;margin-top:8px"><button onclick="closeM()">Close</button></div>`;$('#modal').classList.remove('hidden')}
window.closeM=()=>$('#modal').classList.add('hidden');$('#modal').onclick=e=>{if(e.target.id==='modal')closeM()};
async function markup(i){const s=S.pendingShots[i],im=await loadImg(s.data);
 $('#mbox').innerHTML=`<div class="mk"><div class="tools" id="tl"><button data-t="arrow" class="on">↗ Arrow</button><button data-t="box">▭ Box</button><button data-t="line">― Line</button><button data-t="pen">✎ Pen</button><button data-t="text">T Text</button>
 <input type="color" id="col" value="#22d3a6" style="width:44px;padding:2px"><select id="lw" style="width:auto"><option value="2">Thin</option><option value="4" selected>Medium</option><option value="7">Thick</option></select><button id="und">Undo</button><span class="sp"></span><button class="pri" id="msv">Save</button><button onclick="closeM()">Cancel</button></div><canvas id="cv"></canvas></div>`;
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
 const row=(l,v)=>`<div><div class="mut" style="font-size:12px">${l}</div><div><b>${v||'—'}</b></div></div>`;
 $('#app').innerHTML=`<div class="flex" style="margin-bottom:14px"><button onclick="go('trades')">‹ Trades</button><h2 class="sp" style="margin:0">${esc(t.symbol||t.instrument)} <span class="${t.side==='Long'?'pos':'neg'}">${t.side}</span> ${t.grade?`<span class="grade g${t.grade}">${t.grade}</span>`:''}</h2><button class="pri" onclick="go('new','${id}')">Edit</button></div>
 ${n.map(e=>`<div class="warn">⚠ Taken within the news window of <b>${esc(e.title)}</b> (${esc(e.date)} ${esc(e.time)})</div>`).join('')}
 <div class="grid g4">${[['Net P&L',fmt$(c.net),cls(c.net)],['R-multiple',fmtR(c.R),cls(c.R)],['Points',isFinite(c.points)?c.points.toFixed(2):'—',''],['$ Risk',isFinite(c.risk)?fmt$(c.risk):'—',''],['MAE',isFinite(c.mae)?c.mae.toFixed(2)+'R':'—','neg'],['MFE',isFinite(c.mfe)?c.mfe.toFixed(2)+'R':'—','pos'],['Captured of MFE',isFinite(c.mfe)&&c.mfe>0&&isFinite(c.R)?Math.round(c.R/c.mfe*100)+'%':'—',''],['Hold time',isFinite(c.hold)?(c.hold<60?Math.round(c.hold)+' min':(c.hold/60).toFixed(1)+' h'):'—','']].map(([l,v,k])=>`<div class="card kpi"><div class="l">${l}</div><div class="v ${k}">${v}</div></div>`).join('')}</div>
 <div class="card"><h3>Details</h3><div class="form">${row('Instrument',esc(t.instrument))}${row('Size',esc(t.qty))}${row('Entry',esc(t.entry))}${row('Stop',esc(t.stop))}${row('Target',esc(t.target))}${row('Exits',(t.exits||[]).map(x=>esc(x.qty)+' @ '+esc(x.price)).join(', '))}${row('Fees',t.fees?fmt$(+t.fees):'')}${row('Entry time',esc((t.entryTime||'').replace('T',' ')))}${row('Exit time',esc((t.exitTime||'').replace('T',' ')))}${row('Account',esc(t.account))}</div></div>
 <div class="card"><h3>ICT analysis</h3><div class="form">${row('HTF bias',esc(t.bias))}${row('Draw on liquidity',esc(t.dol))}${row('Entry zone',esc(t.pd))}${row('Session',esc(t.session))}${row('Kill zone',esc(t.killzone))}${row('Setup',esc(t.setup))}${row('Timeframe',esc(t.tf))}</div>
 <div style="margin-top:10px">${(t.ict||[]).map(x=>`<span class="tag">${esc(x)}</span>`).join('')||'<span class="mut">No concepts tagged</span>'}</div>
 <div style="margin-top:10px" class="mut">Checklist: ${(t.checklist||[]).length} items met — ${(t.checklist||[]).map(esc).join(' · ')}</div></div>
 <div class="card"><h3>Psychology</h3><div class="form">${row('Before',esc(t.emoBefore))}${row('After',esc(t.emoAfter))}${row('Confidence',esc(t.confidence))}${row('Followed plan',esc(t.followed))}</div><div style="margin-top:8px">${(t.mistakes||[]).map(x=>`<span class="tag" style="color:var(--r)">${esc(x)}</span>`).join('')}</div></div>
 <div class="card"><h3>Charts</h3><div class="shots">${shots.map(s=>`<div class="shot"><img src="${s.data}" onclick="lightbox(this.src)"><div class="cap">${esc(s.stage)}</div></div>`).join('')||'<span class="mut">No screenshots</span>'}</div></div>
 <div class="card"><h3>Notes</h3><p style="white-space:pre-wrap">${esc(t.notes)||'<span class="mut">—</span>'}</p><h3>Review</h3><p style="white-space:pre-wrap">${esc(t.review)||'<span class="mut">—</span>'}</p></div>`}
window.lightbox=lightbox;window.go=go;

/* ---------- News calendar ---------- */
function weekRange(off=0){const d=new Date();d.setHours(0,0,0,0);d.setDate(d.getDate()-((d.getDay()+6)%7)+off*7);const e=new Date(d);e.setDate(d.getDate()+6);return [d,e]}
const ymd=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
async function cal(){const off=S.wk||0,[a,b]=weekRange(off),ev=(await kv('events',[])).sort((x,y)=>(x.date+x.time).localeCompare(y.date+y.time)),wk=ev.filter(e=>e.date>=ymd(a)&&e.date<=ymd(b));
 const days=[...Array(7)].map((_,i)=>{const d=new Date(a);d.setDate(a.getDate()+i);return d});
 $('#app').innerHTML=`<div class="flex" style="margin-bottom:14px"><h2 class="sp" style="margin:0">News & Economic Calendar</h2><button id="pw">‹ Prev</button><b>${a.toLocaleDateString(undefined,{month:'short',day:'numeric'})} – ${b.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}</b><button id="nw2">Next ›</button>${off?'<button id="tw">This week</button>':''}</div>
 <div class="card"><h3>Live sources</h3><p class="mut" style="margin-top:0">Omensite Journal has no server, and free economic-calendar feeds don't allow direct browser access, so it doesn't show events it can't verify. Check a live source, then add this week's key releases below (times are your local time). High-impact events trigger warnings on trades taken within ${esc(await kv('newsWin',15))} minutes.</p>
 <div class="flex"><a class="btn" target="_blank" rel="noopener" href="https://www.forexfactory.com/calendar?week=this">ForexFactory (this week)</a><a class="btn" target="_blank" rel="noopener" href="https://www.investing.com/economic-calendar/">Investing.com economic</a><a class="btn" target="_blank" rel="noopener" href="https://www.investing.com/earnings-calendar/">Investing.com earnings</a><a class="btn" target="_blank" rel="noopener" href="https://www.cmegroup.com/trading-hours.html">CME holiday hours</a><a class="btn" target="_blank" rel="noopener" href="https://www.nyse.com/markets/hours-calendars">NYSE holidays</a></div></div>
 <div class="card"><h3>Add event</h3><form id="ef" class="form"><div><label>Date</label><input name="date" type="date" required value="${ymd(a)}"></div><div><label>Time (local)</label><input name="time" type="time"></div><div><label>Event</label><input name="title" required placeholder="e.g. CPI m/m, FOMC, NVDA earnings"></div>
 <div><label>Impact</label><select name="impact"><option>High</option><option>Medium</option><option>Low</option></select></div><div><label>Type</label><select name="kind"><option>Economic (USD)</option><option>Earnings</option><option>Holiday / early close</option><option>Other</option></select></div><div style="align-self:end"><button class="pri">Add</button></div></form></div>
 <div class="grid g2">${days.map(d=>{const k=ymd(d),es=wk.filter(e=>e.date===k);return `<div class="card" style="${k===ymd(new Date())?'border-color:var(--g)':''}"><h3>${d.toLocaleDateString(undefined,{weekday:'long',month:'short',day:'numeric'})}</h3>${es.length?`<table>${es.map(e=>`<tr><td style="width:60px">${esc(e.time||'All day')}</td><td class="imp-${e.impact}">●</td><td>${esc(e.title)} <span class="mut" style="font-size:11px">${esc(e.kind)}</span></td><td style="text-align:right"><button class="del" data-d="${e.id}">✕</button></td></tr>`).join('')}</table>`:'<div class="mut">No events added</div>'}</div>`}).join('')}</div>`;
 $('#pw').onclick=()=>{S.wk=off-1;cal()};$('#nw2').onclick=()=>{S.wk=off+1;cal()};if(off)$('#tw').onclick=()=>{S.wk=0;cal()};
 $('#ef').onsubmit=async e=>{e.preventDefault();const x=Object.fromEntries(new FormData(e.target));x.id=uid();await setkv('events',[...ev,x]);toast('Event added');cal()};
 $$('[data-d]').forEach(b=>b.onclick=async()=>{await setkv('events',ev.filter(e=>e.id!==b.dataset.d));cal()})}

/* ---------- Daily plan ---------- */
async function plan(){const d=S.pd||ymd(new Date()),p=(await get('plans',d))||{id:d},ts=S.trades.filter(t=>(t.entryTime||'').startsWith(d)),s=stats(ts.filter(t=>!t.c.open));
 const recent=(await all('plans')).sort((a,b)=>b.id.localeCompare(a.id)).slice(0,10);
 const T=(n,l,ph)=>`<div><label>${l}</label><textarea name="${n}" placeholder="${ph}">${esc(p[n]||'')}</textarea></div>`;
 $('#app').innerHTML=`<div class="flex" style="margin-bottom:14px"><h2 class="sp" style="margin:0">Daily Plan & Review</h2><input type="date" id="pdd" value="${d}" style="width:auto"></div>
 <form id="pf"><div class="grid g2"><div class="card"><h3>Pre-market plan</h3><div class="form" style="grid-template-columns:1fr">
 <div><label>Daily bias</label><select name="bias">${['','Bullish','Bearish','Neutral / wait'].map(o=>`<option ${o===p.bias?'selected':''}>${o}</option>`).join('')}</select></div>
 ${T('dol','Draw on liquidity','Where is price likely to go? PDH/PDL, weekly highs/lows, equal highs…')}${T('levels','Key levels','PDH, PDL, Asia high/low, London high/low, NWOG, FVGs…')}${T('news',"Today's news",'Check the News Calendar tab')}${T('rules','Rules for today','Max 2 trades, stop after -1R, only A setups…')}</div></div>
 <div class="card"><h3>End-of-day review</h3><div class="grid g4" style="margin-bottom:12px"><div class="kpi"><div class="l">Trades</div><div class="v">${s.n}</div></div><div class="kpi"><div class="l">Net</div><div class="v ${cls(s.net)}">${fmt$(s.net)}</div></div><div class="kpi"><div class="l">R</div><div class="v ${cls(s.sumR)}">${fmtR(s.sumR)}</div></div></div>
 <div class="form" style="grid-template-columns:1fr"><div><label>Did I follow my plan?</label><select name="followed">${['','Yes','Partially','No'].map(o=>`<option ${o===p.followed?'selected':''}>${o}</option>`).join('')}</select></div>
 <div><label>Mood (1-10)</label><input name="mood" type="number" min="1" max="10" value="${esc(p.mood||'')}"></div>${T('went','What went well','')}${T('wrong','What went wrong','')}${T('lesson','Lesson for tomorrow','')}</div></div></div>
 <button class="pri">Save day</button></form>
 <div class="card" style="margin-top:16px"><h3>Recent days</h3>${recent.length?recent.map(r=>`<button data-day="${r.id}" style="margin:3px">${r.id} ${r.bias?'· '+esc(r.bias):''}</button>`).join(''):'<span class="mut">No saved days yet</span>'}</div>`;
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
 $('#app').innerHTML=`<h2>Settings & Data</h2><div class="grid g2">
 <div class="card"><h3>Pre-trade checklist</h3><p class="mut" style="margin-top:0">One rule per line. Grades are auto-set from the share of rules met (≥95% A+, ≥75% A, ≥50% B, else C).</p><textarea id="ck" style="min-height:180px">${esc(check.join('\n'))}</textarea>
 <label style="margin-top:10px">Your setups / models (one per line)</label><textarea id="su">${esc(setups.join('\n'))}</textarea><button class="pri" id="cks" style="margin-top:8px">Save</button></div>
 <div class="card"><h3>Prop firm rules</h3><form id="prf" class="form"><div><label>Account name (blank = all)</label><input name="account" value="${esc(prop.account||'')}" placeholder="Prop / Funded"></div><div><label>Starting balance ($)</label><input name="start" type="number" value="${esc(prop.start||'')}"></div><div><label>Daily loss limit ($)</label><input name="daily" type="number" value="${esc(prop.daily||'')}"></div><div><label>Trailing drawdown ($)</label><input name="trail" type="number" value="${esc(prop.trail||'')}"></div><div><label>Profit target ($)</label><input name="target" type="number" value="${esc(prop.target||'')}"></div><div style="align-self:end"><button class="pri">Save</button></div></form>
 <h3 style="margin-top:16px">News warning window</h3><div class="flex"><input id="nwin" type="number" value="${esc(win)}" style="width:90px"> minutes around high-impact events <button id="nws">Save</button></div></div>
 <div class="card"><h3>Import trades (CSV)</h3><p class="mut" style="margin-top:0">Works with exports from Tradovate, NinjaTrader, Topstep, Webull, etc. when they include columns like <i>symbol, side, qty, entry, exit, entry time, exit time, fees, pnl</i>. Rename headers if needed.</p><input type="file" id="csv" accept=".csv,text/csv"><div id="csvr" class="mut" style="margin-top:6px"></div></div>
 <div class="card"><h3>Export & backup</h3><p class="mut" style="margin-top:0">Your data lives only in this browser. Back up regularly — clearing site data deletes it. ${usage}</p>
 <div class="flex"><button id="ex1">Export trades CSV</button><button id="ex2" class="pri">Download full backup (JSON)</button><label class="btn">Restore backup<input type="file" id="rs" accept=".json" hidden></label><button id="wipe" class="del">Erase all data</button></div></div></div>`;
 $('#cks').onclick=async()=>{await setkv('checklist',$('#ck').value.split('\n').map(s=>s.trim()).filter(Boolean));await setkv('setups',$('#su').value.split('\n').map(s=>s.trim()).filter(Boolean));toast('Saved')};
 $('#prf').onsubmit=async e=>{e.preventDefault();await setkv('prop',Object.fromEntries(new FormData(e.target)));toast('Prop rules saved')};
 $('#nws').onclick=async()=>{await setkv('newsWin',+$('#nwin').value||15);toast('Saved')};
 $('#csv').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const ts=mapCSV(parseCSV(await f.text()));for(const t of ts)await put('trades',t);$('#csvr').innerHTML=`<span class="pos">Imported ${ts.length} trades (account "Imported"). Open them to add ICT tags & screenshots.</span>`}catch(err){$('#csvr').innerHTML=`<span class="neg">${esc(err.message)}</span>`}};
 $('#ex1').onclick=()=>{const H=['date','symbol','instrument','side','qty','entry','avg_exit','stop','target','fees','net_pnl','r_multiple','mae_r','mfe_r','account','session','killzone','setup','ict','grade','mistakes','emotion_before','notes'];
  const q=v=>`"${String(v??'').replace(/"/g,'""')}"`;download('omensite-trades.csv',[H.join(','),...S.trades.map(t=>[t.entryTime,t.symbol,t.instrument,t.side,t.qty,t.entry,isFinite(t.c.avgExit)?t.c.avgExit:'',t.stop,t.target,t.fees,t.c.open?'':t.c.net.toFixed(2),isFinite(t.c.R)?t.c.R.toFixed(2):'',isFinite(t.c.mae)?t.c.mae.toFixed(2):'',isFinite(t.c.mfe)?t.c.mfe.toFixed(2):'',t.account,t.session,t.killzone,t.setup,(t.ict||[]).join('; '),t.grade,(t.mistakes||[]).join('; '),t.emoBefore,t.notes].map(q).join(','))].join('\n'),'text/csv')};
 $('#ex2').onclick=async()=>{const data={app:'omensite-journal',version:1,exported:new Date().toISOString()};for(const s of['trades','shots','plans','kv'])data[s]=await all(s);download(`omensite-backup-${ymd(new Date())}.json`,JSON.stringify(data),'application/json');toast('Backup downloaded')};
 $('#rs').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const d=JSON.parse(await f.text());if(d.app!=='omensite-journal')throw new Error('Not an Omensite backup');if(!confirm('Replace all current data with this backup?'))return;for(const s of['trades','shots','plans','kv']){await clear(s);for(const v of d[s]||[])await put(s,v)}toast('Backup restored');go('dash')}catch(err){alert('Restore failed: '+err.message)}};
 $('#wipe').onclick=async()=>{if(!confirm('Erase ALL trades, screenshots, plans and settings? This cannot be undone.'))return;for(const s of['trades','shots','plans','kv'])await clear(s);toast('All data erased');go('dash')}}

openDB().then(()=>go('dash')).catch(e=>{$('#app').innerHTML=`<div class="empty">Could not open browser storage (IndexedDB): ${esc(e&&e.message)}. Private/incognito modes may block it.</div>`});
