/* ==========================================================================
   AVLOKAN - Phase 6: Analyst Review Queue & Tamper-Evident Audit Trail
   ========================================================================== */

/* ================= PHASE 6 · REVIEW QUEUE + AUDIT TRAIL ================= */
delete STUBS.review; delete STUBS.audit;

const RQ={filter:'all',items:[]};
const AF={filter:'all'};
App.auditLog=[];App.tamper=null;
window.BackendAudit={items:[],integrity:null};

const REVIEW_SEED=[
 {id:'rq-01',name:'Mumbai Docks — Berth 7 Extension',lat:18.955,lng:72.842,conf:96,delta:8.4,cat:'Maritime infrastructure expansion',t1:'2026-03-14',t2:'2026-09-08',agree:'S2 ✓ · S1 ✓',sar:false,seed:11},
 {id:'rq-02',name:'Ladakh — Forward Sector K2',lat:34.152,lng:77.580,conf:91,delta:3.9,cat:'Forward-sector structural activity',t1:'2026-04-02',t2:'2026-09-12',agree:'S1 ✓ · optical ✗',sar:true,seed:53},
 {id:'rq-03',name:'Kandla — Container Yard Expansion',lat:23.030,lng:70.230,conf:88,delta:6.2,cat:'Port logistics expansion',t1:'2026-01-18',t2:'2026-08-27',agree:'S2 ✓ · S1 ✓',sar:false,seed:29},
 {id:'rq-04',name:'Delhi NE — Peripheral Depot',lat:28.612,lng:77.208,conf:87,delta:5.1,cat:'Industrial construction',t1:'2026-02-11',t2:'2026-09-02',agree:'S2 ✓ · S1 ✓',sar:false,seed:23},
 {id:'rq-05',name:'Chennai — Industrial Outskirts',lat:13.082,lng:80.270,conf:82,delta:6.7,cat:'Shed cluster expansion',t1:'2026-01-20',t2:'2026-08-30',agree:'S2 ✓ · S1 ◐',sar:false,seed:37},
 {id:'rq-06',name:'Jaisalmer — Track Network Widening',lat:26.910,lng:70.090,conf:80,delta:2.8,cat:'Line-of-communication improvement',t1:'2026-03-05',t2:'2026-09-01',agree:'S1 ✓ · S2 ◐',sar:true,seed:61},
 {id:'rq-07',name:'Visakhapatnam — Dry Dock Activity',lat:17.690,lng:83.280,conf:78,delta:4.4,cat:'Naval infrastructure activity',t1:'2026-02-22',t2:'2026-08-19',agree:'S2 ✓ · L8 ✓',sar:false,seed:43},
 {id:'rq-08',name:'Bhadla — Solar Phase IV',lat:27.541,lng:71.905,conf:77,delta:11.2,cat:'Energy array expansion',t1:'2026-02-08',t2:'2026-09-05',agree:'S2 ✓ · L9 ✓',sar:false,seed:71},
 {id:'rq-09',name:'Ranchi — Quarry Encroachment',lat:23.350,lng:85.300,conf:71,delta:3.3,cat:'Extractive activity — permit check',t1:'2026-04-14',t2:'2026-09-03',agree:'S2 ✓ · S1 ◐',sar:false,seed:83},
 {id:'rq-10',name:'Punjab — Flooded Field Anomaly',lat:30.900,lng:75.850,conf:68,delta:9.6,cat:'Hydrological anomaly — monsoon correlation',t1:'2026-06-02',t2:'2026-07-28',agree:'S2 ✓',sar:false,seed:97},
 {id:'rq-11',name:'Narmada — Reservoir Drawdown',lat:22.170,lng:73.720,conf:64,delta:7.8,cat:'Water-level change — seasonal',t1:'2026-05-11',t2:'2026-09-06',agree:'S2 ✓ · L8 ✓',sar:false,seed:101},
 {id:'rq-12',name:'Brahmaputra — Sandbar Migration',lat:26.200,lng:92.940,conf:61,delta:5.5,cat:'Fluvial geomorphology — natural',t1:'2026-03-30',t2:'2026-09-10',agree:'S1 ✓ · S2 ✓',sar:true,seed:113},
 {id:'rq-13',name:'Konkan — Canopy Gap Cluster',lat:17.900,lng:73.660,conf:58,delta:2.2,cat:'Possible selective felling — cloud-suspect',t1:'2026-02-27',t2:'2026-08-15',agree:'S2 ◐ · S1 ◐',sar:false,seed:127},
 {id:'rq-14',name:'Thar — Dune Field Shift',lat:27.800,lng:71.400,conf:52,delta:4.1,cat:'Aeolian transport — natural cycle',t1:'2026-04-19',t2:'2026-09-09',agree:'S2 ✓',sar:false,seed:139}];

function priOf(c){return c>=90?'high':c>=75?'mid':'low'}
function seedReview(){RQ.items=REVIEW_SEED.map(c=>Object.assign({flagged:false},c))}

/* ---- hash chain ---- */
function strHash(s){let h=0x811c9dc5;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,0x01000193)}return(h>>>0).toString(16).padStart(8,'0')}
function chainHash(prev,e){return strHash(prev+'|'+e.t+'|'+e.action+'|'+e.detail)}
function pushAudit(e){e.h=chainHash(App.auditLog.length?App.auditLog[App.auditLog.length-1].h:'00000000',e);App.auditLog.push(e)}
function logAudit(action,detail){pushAudit({t:istTime(),action,detail})}

/* auto-log every feed event to the ledger */
const _addFeedP6=addFeed;
addFeed=function(html){
 _addFeedP6(html);
 const action=(html.match(/class="tag [a-z]"\s*>([A-Z ]+)</)||[])[1]||'SYSTEM';
 logAudit(action,html.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim())};

const AGROUP={CONFIRMED:'v',REJECTED:'v',REVIEW:'v',DETECT:'v',QUEUE:'v',SEARCH:'o',STAC:'o',STAGE:'o',EXPORT:'o',AOI:'o',INDEX:'o',SESSION:'s',SYSTEM:'s'};
const ACOL={CONFIRMED:'g',REJECTED:'r',REVIEW:'a',QUEUE:'a',DETECT:'a',AOI:'a',SEARCH:'c',STAC:'c',STAGE:'c',EXPORT:'c',INDEX:'c',SESSION:'c',SYSTEM:'c'};

/* ---- pending-count sync (badge + stat + module card) ---- */
function syncPending(){
 document.getElementById('revBadge').textContent=pendingCount;
 const st=document.getElementById('statPending');if(st)st.textContent=pendingCount.toLocaleString('en-IN');
 const mb=document.querySelector('.mod.alert .mbadge');if(mb)mb.textContent=pendingCount+' pending'}

/* ---- cross-module feeds into the queue ---- */
const _confirmP5=confirmChange;
confirmChange=function(){
 const d=App.det;if(!d)return;
 RQ.items.push({id:'rq-live-'+Date.now(),name:d.name,lat:d.pin.lat,lng:d.pin.lng,conf:d.conf,delta:d.delta,cat:d.cat,
  t1:d.a.date.toISOString().slice(0,10),t2:d.b.date.toISOString().slice(0,10),agree:d.agree,sar:d.sar,seed:d.seed,flagged:false,live:true});
 _confirmP5();syncPending()};

const _queueAOIP6=queueAOI;
queueAOI=function(){
 if(!curAoi)return;
 RQ.items.push({id:'rq-aoi-'+Date.now(),name:curAoi.name,lat:curAoi.lat,lng:curAoi.lng,conf:curAoi.conf,delta:curAoi.change,cat:curAoi.cat,
  t1:curAoi.t1,t2:curAoi.t2,agree:curAoi.agree,sar:!!curAoi.sar,seed:curAoi.seed,flagged:false,live:true});
 _queueAOIP6();syncPending()};

const _doLoginP6=doLogin;
doLogin=function(){_doLoginP6();
 setTimeout(()=>addFeed('<span class="tag c">SESSION</span><b>Analyst 01</b> authenticated — secure console session opened'),1250)};
const _logoutP6=logout;
logout=function(){addFeed('<span class="tag c">SESSION</span><b>Analyst 01</b> signed out — session closed');_logoutP6()};

/* ---- REVIEW QUEUE ---- */
function renderReview(){
 const el=document.getElementById('view-review');
 const counts={all:RQ.items.length,high:0,mid:0,low:0,flagged:0};
 RQ.items.forEach(c=>{counts[priOf(c.conf)]++;if(c.flagged)counts.flagged++});
 const list=RQ.items
  .filter(c=>RQ.filter==='all'||(RQ.filter==='flagged'?c.flagged:priOf(c.conf)===RQ.filter))
  .sort((a,b)=>b.conf-a.conf);
 const chips=[['all','ALL'],['high','HIGH'],['mid','MEDIUM'],['low','LOW'],['flagged','FLAGGED']];
 el.innerHTML=`
  <div class="flowstrip">${flowStrip('review')}</div>
  <div class="res-head">
   <div><div class="res-q">Analyst Review Queue</div>
    <div class="res-meta mono">${RQ.items.length} pending · AI-prioritized · highest confidence first · every decision hash-logged to the audit chain</div></div>
  </div>
  <div class="rev-filters">${chips.map(c=>`<span class="qchip${RQ.filter===c[0]?' on':''}" onclick="RQ.filter='${c[0]}';renderReview()">${c[1]} · ${counts[c[0]]}</span>`).join('')}</div>
  ${list.length?`<div class="rev-grid" id="revGrid"></div>`
   :`<div class="panel rev-empty">${ICONS.check}
     <div style="font-weight:800;font-size:15px;color:var(--text)">Queue clear — all candidates resolved</div>
     <div style="font-size:12px;margin-top:4px">session decisions are permanently recorded in the audit ledger</div>
     <button class="btn btn-ghost" style="width:auto;margin:16px auto 0" onclick="go('audit')">→ Open Audit Trail</button></div>`}`;
 const grid=document.getElementById('revGrid');if(!grid)return;
 list.forEach(c=>{
  if(!c._diff)c._diff=computeChangeDiff(c.seed,c.sar);
  const pri=priOf(c.conf);
  const card=document.createElement('div');card.className='cand-card';
  card.innerHTML=`
   <div class="cand-head">
    <span class="badge ${pri==='high'?'h':pri==='mid'?'m':'lo'}">${pri==='high'?'HIGH':pri==='mid'?'MEDIUM':'LOW'}</span>
    <div style="flex:1;min-width:0"><div class="cand-name">${c.name}</div>
     <div class="cand-sub mono">${Math.abs(c.lat).toFixed(3)}°${c.lat>=0?'N':'S'} ${Math.abs(c.lng).toFixed(3)}°${c.lng>=0?'E':'W'} · ${c.t1} → ${c.t2}</div></div>
    ${c.flagged?'<span class="flag-pill">◐ 2ND ANALYST</span>':''}
   </div>
   <div class="cand-body">
    <div class="cand-ev" onclick="openRevEv('${c.id}')" title="Open evidence">
     <canvas width="320" height="180"></canvas><span class="zoom">EVIDENCE ⇱</span></div>
    <div class="cand-info">
     <div class="cand-mrow mono"><span>CONF <b>${c.conf}%</b></span><span>Δ <b>${c._diff.delta}%</b></span><span>REG <b>${c._diff.regions}</b></span></div>
     <div class="cand-src">${c.cat}</div>
     <div style="font-size:10.5px;color:var(--faint)">${c.agree}${c.sar?' · <span style="color:var(--violet-d);font-weight:800">SAR</span>':''}</div>
     <div class="cand-actions">
      <span class="act ok" onclick="decideReview('${c.id}','confirm')">✓ Confirm</span>
      <span class="act no" onclick="decideReview('${c.id}','reject')">✕ Reject</span>
      <span class="act maybe" onclick="decideReview('${c.id}','need')">◐ Review</span>
     </div>
    </div>
   </div>`;
  card.querySelector('canvas').getContext('2d').drawImage(c._diff.cv,0,0);
  grid.appendChild(card)})}

function decideReview(id,act){
 const it=RQ.items.find(x=>x.id===id);if(!it)return;
 if(act==='need'){
  if(it.flagged){toast('Already flagged — awaiting second analyst');return}
  it.flagged=true;
  addFeed('<span class="tag a">REVIEW</span><b>Analyst 01</b> flagged '+it.name+' — second-analyst examination requested');
  toast('Flagged for second analyst — evidence attached','success');
  renderReview();return}
 RQ.items=RQ.items.filter(x=>x.id!==id);
 pendingCount=Math.max(0,pendingCount-1);
 syncPending();
 App.verdicts.push({name:it.name,conf:it.conf,action:act==='confirm'?'CONFIRMED':'REJECTED',when:istTime(),cat:it.cat,t1:it.t1,t2:it.t2,delta:it.delta});
 if(act==='confirm')
  addFeed('<span class="tag g">CONFIRMED</span><b>Analyst 01</b> confirmed change at '+it.name+' — '+it.conf+'% confidence · '+(it._diff?it._diff.regions:'—')+' regions');
 else
  addFeed('<span class="tag r">REJECTED</span><b>Analyst 01</b> rejected candidate at '+it.name+' — false alarm · '+it.cat);
 toast(act==='confirm'?'Verdict recorded — change confirmed':'Candidate rejected — false alarm logged','success');
 renderReview()}

/* ---- review evidence modal ---- */
let curRev=null;
function injectReviewModal(){
 if(document.getElementById('revOverlay'))return;
 const o=document.createElement('div');
 o.className='overlay hidden';o.id='revOverlay';
 o.onclick=e=>{if(e.target===o)closeRevEv()};
 o.innerHTML=`
 <div class="modal" style="width:860px">
  <div class="modal-h">
   <span class="inv-dot" id="rvDot"></span>
   <div><div class="inv-t" id="rvName">—</div><div class="inv-s mono" id="rvSub">—</div></div>
   <span class="badge" id="rvPri">—</span>
   <span class="badge violet hidden" id="rvSar">SAR FALLBACK ENGAGED</span>
   <button class="icon-btn" style="margin-left:auto" onclick="closeRevEv()">✕</button>
  </div>
  <div class="modal-b">
   <div class="swipe" id="rvSwipe">
    <canvas id="rvCvB" width="640" height="360"></canvas>
    <canvas id="rvCvA" width="640" height="360" style="clip-path:inset(0 0 0 50%)"></canvas>
    <div class="sw-handle" id="rvHandle" style="left:50%"><span>⇄</span></div>
    <span class="sw-tag l mono" id="rvT1">T1</span>
    <span class="sw-tag r mono" id="rvT2">T2</span>
   </div>
   <div class="inv-tip">DRAG TO COMPARE · T1 BASELINE ↔ T2 CURRENT</div>
   <div class="metrics" id="rvMetrics"></div>
   <div class="inv-sec">Δ EVIDENCE — PIXEL-LEVEL CHANGE HEAT</div>
   <canvas id="rvDet" width="320" height="180" style="width:100%;border-radius:10px;border:1px solid var(--line2);display:block"></canvas>
   <div class="dossier" id="rvCat"></div>
  </div>
  <div class="modal-f">
   <button class="btn btn-primary" style="width:auto" onclick="decideFromModal('confirm')">✓ Confirm Change</button>
   <button class="btn btn-ghost" style="width:auto" onclick="decideFromModal('reject')">✕ Reject — False Alarm</button>
   <button class="btn btn-ghost" style="width:auto" onclick="decideFromModal('need')">◐ Need Review</button>
   <button class="btn btn-ghost" style="width:auto;margin-left:auto" onclick="closeRevEv()">Close</button>
  </div>
 </div>`;
 document.body.appendChild(o);
 wireSwipe(document.getElementById('rvSwipe'),'rvCvA','rvHandle')}

function openRevEv(id){
 const it=RQ.items.find(x=>x.id===id);if(!it)return;
 curRev=it;
 const pri=priOf(it.conf);
 document.getElementById('rvDot').style.background=colOf(pri);
 document.getElementById('rvName').textContent=it.name;
 document.getElementById('rvSub').textContent=Math.abs(it.lat).toFixed(4)+'°'+(it.lat>=0?'N':'S')+', '+Math.abs(it.lng).toFixed(4)+'°'+(it.lng>=0?'E':'W')+' · window '+it.t1+' → '+it.t2;
 const pb=document.getElementById('rvPri');
 pb.className='badge '+(pri==='high'?'h':pri==='mid'?'m':'lo');
 pb.textContent=pri==='high'?'HIGH PRIORITY':pri==='mid'?'UNDER REVIEW':'ROUTINE MONITOR';
 document.getElementById('rvSar').classList.toggle('hidden',!it.sar);
 const B=document.getElementById('rvCvB'),A=document.getElementById('rvCvA');
 if(it.sar){drawTileSAR(B,it.seed,'before');drawTileSAR(A,it.seed,'after')}
 else{drawTile(B,it.seed,'before');drawTile(A,it.seed,'after')}
 if(!it._diff)it._diff=computeChangeDiff(it.seed,it.sar);
 document.getElementById('rvDet').getContext('2d').drawImage(it._diff.cv,0,0);
 document.getElementById('rvT1').textContent='T1 · '+it.t1;
 document.getElementById('rvT2').textContent='T2 · '+it.t2;
 document.getElementById('rvMetrics').innerHTML=`
  <div class="metric"><div class="mk">CHANGE RATIO</div><div class="mv a">${it._diff.delta}%</div></div>
  <div class="metric"><div class="mk">CONFIDENCE</div><div class="mv ${it.conf>=85?'g':'c'}">${it.conf}%</div></div>
  <div class="metric"><div class="mk">REGIONS</div><div class="mv c">${it._diff.regions}</div></div>
  <div class="metric"><div class="mk">SENSOR AGREEMENT</div><div class="mv sm">${it.agree}</div></div>`;
 document.getElementById('rvCat').innerHTML='<b>Δ Category:</b> '+it.cat+' · <b>Source:</b> '+(it.live?'detection pipeline':'AOI monitor sweep')+' · Synthetic demo imagery — deterministic render, honestly labeled.';
 document.getElementById('revOverlay').classList.remove('hidden')}

function closeRevEv(){document.getElementById('revOverlay').classList.add('hidden')}
function decideFromModal(act){const it=curRev;closeRevEv();if(it)decideReview(it.id,act)}

/* ---- AUDIT TRAIL ---- */
function renderAudit(){
 const el=document.getElementById('view-audit');
 let prev='00000000',trust=true,firstBad=-1;
 const marks=App.auditLog.map((e,i)=>{
  const exp=chainHash(prev,e);
  const ok=trust&&exp===e.h;
  if(!ok){if(firstBad<0)firstBad=i;trust=false}
  prev=e.h;return ok});
 const nV=App.auditLog.filter(e=>(AGROUP[e.action]||'s')==='v').length;
 const nO=App.auditLog.filter(e=>(AGROUP[e.action]||'s')==='o').length;
 const nS=App.auditLog.filter(e=>(AGROUP[e.action]||'s')==='s').length;
 const confN=App.auditLog.filter(e=>e.action==='CONFIRMED').length;
 const rejN=App.auditLog.filter(e=>e.action==='REJECTED').length;
 const flagN=App.auditLog.filter(e=>e.action==='REVIEW').length;
 const shown=App.auditLog.filter(e=>AF.filter==='all'||(AGROUP[e.action]||'s')===AF.filter);
 const fch=[['all','ALL',App.auditLog.length],['v','VERDICTS',nV],['o','OPS',nO],['s','SYSTEM',nS]];
 el.innerHTML=`
  <div class="flowstrip">${flowStrip('audit')}</div>
  <div class="res-head">
   <div><div class="res-q">Provenance & Audit Trail</div>
    <div class="res-meta mono">append-only · FNV-1a hash chain · ${App.auditLog.length} entries · every decision traceable to analyst, scene and timestamp</div></div>
   <span class="chain-pill ${firstBad<0?'chain-ok':'chain-bad'}">${firstBad<0?'⛓ HASH-CHAIN INTACT · '+App.auditLog.length+' VERIFIED':'⚠ TAMPER DETECTED — BROKEN AT ENTRY '+(firstBad+1)}</span>
  </div>
  <div class="metrics" style="margin-bottom:14px">
   <div class="metric"><div class="mk">LEDGER ENTRIES</div><div class="mv">${App.auditLog.length}</div></div>
   <div class="metric"><div class="mk">CONFIRMED</div><div class="mv g">${confN}</div></div>
   <div class="metric"><div class="mk">REJECTED</div><div class="mv" style="color:#a4574d">${rejN}</div></div>
   <div class="metric"><div class="mk">FLAGGED / REVIEW</div><div class="mv a">${flagN}</div></div>
  </div>
  <div class="res-toolbar">
   <span class="rt-label">Filter</span>
   ${fch.map(f=>`<span class="qchip${AF.filter===f[0]?' on':''}" onclick="AF.filter='${f[0]}';renderAudit()">${f[1]} · ${f[2]}</span>`).join('')}
   <span class="rt-spacer"></span>
   <button class="rt-btn" onclick="simulateTamper()">${App.tamper?'↺ Restore Integrity':'⚠ Simulate Tamper'}</button>
   <button class="rt-btn pri" onclick="exportAuditCSV()">↓ Export Ledger CSV</button>
  </div>
  <div class="panel"><div class="panel-b" style="padding-top:6px">
   <div class="arow head"><span>TIME</span><span>ACTION</span><span>DETAIL</span><span style="text-align:right">HASH</span></div>
   ${shown.map(e=>{
    const i=App.auditLog.indexOf(e),ok=marks[i];
    return `<div class="arow${ok?'':' broken'}">
     <span class="at">${e.t}</span>
     <span><span class="tag2 ${ACOL[e.action]||'c'}">${e.action}</span></span>
     <span class="ad">${e.detail}</span>
     <span class="ah">${ok?'§'+e.h:'✕ '+e.h.slice(0,6)}</span></div>`}).join('')}
  </div></div>`}

function simulateTamper(){
 if(App.tamper){restoreTamper();return}
 if(App.auditLog.length<4){toast('Not enough ledger entries to tamper yet');return}
 const idx=1+Math.floor(Math.random()*(App.auditLog.length-2));
 App.tamper={idx,orig:App.auditLog[idx].detail};
 App.auditLog[idx].detail+=' — [externally redacted]';
 renderAudit();
 toast('Ledger entry mutated — watch the chain verification catch it')}

function restoreTamper(){
 if(!App.tamper)return;
 App.auditLog[App.tamper.idx].detail=App.tamper.orig;
 App.tamper=null;
 renderAudit();
 toast('Ledger restored — hash-chain intact','success')}

function exportAuditCSV(){
 let prev='00000000',trust=true;
 const rows=[['time','action','detail','hash','chain_status']].concat(App.auditLog.map(e=>{
  const exp=chainHash(prev,e);
  const ok=trust&&exp===e.h;if(!ok)trust=false;prev=e.h;
  return[e.t,e.action,e.detail,'§'+e.h,ok?'intact':'broken']}));
 const csv=rows.map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\r\n');
 const fname='avlokan_audit_'+new Date().toISOString().slice(0,10)+'.csv';
 const a=document.createElement('a');
 a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
 a.download=fname;document.body.appendChild(a);a.click();a.remove();
 addFeed('<span class="tag c">EXPORT</span><b>Analyst 01</b> exported audit ledger — '+App.auditLog.length+' entries · '+fname);
 toast('Audit ledger exported — '+fname,'success')}

/* ---- nav hooks + boot ---- */
const _goP5=go;
go=function(id){_goP5(id);
 if(id==='review')renderReview();
 if(id==='audit')renderAudit()};

/* Phase 9: backend records replace the seeded review/audit demo ledger. */
renderReview=async function(){
 const el=document.getElementById('view-review');
 el.innerHTML=`<div class="flowstrip">${flowStrip('review')}</div><div class="panel"><div class="panel-b"><span class="spinner"></span> Loading backend review queue…</div></div>`;
 try{
  const response=await apiRequest('/api/review-queue?status='+encodeURIComponent(RQ.filter)+'&limit=500');
  RQ.items=response.items||[];
  const statuses=['pending','flagged','confirmed','rejected','all'];
  const labels={pending:'PENDING',flagged:'NEED REVIEW',confirmed:'CONFIRMED',rejected:'REJECTED',all:'ALL'};
  el.innerHTML=`<div class="flowstrip">${flowStrip('review')}</div>
   <div class="res-head"><div><div class="res-q">Analyst Review Queue</div>
   <div class="res-meta mono">${response.count} backend candidates · triage score is not confidence</div></div></div>
   <div class="rev-filters">${statuses.map(status=>`<span class="qchip${RQ.filter===status?' on':''}" onclick="RQ.filter='${status}';renderReview()">${labels[status]}${RQ.filter===status?' · '+response.count:''}</span>`).join('')}</div>
   ${RQ.items.length?'<div class="rev-grid" id="revGrid"></div>':'<div class="panel rev-empty"><div style="font-weight:800;font-size:15px;color:var(--text)">No candidates in this backend queue.</div><div style="font-size:12px;margin-top:4px">Candidates are created by successful API change analyses.</div></div>'}`;
  const grid=document.getElementById('revGrid');if(!grid)return;
  RQ.items.forEach(candidate=>{
   const score=Number.isFinite(candidate.candidate_score)?candidate.candidate_score.toFixed(4):'Unavailable';
   const mean=Number.isFinite(candidate.mean_probability)?candidate.mean_probability.toFixed(4):'Unavailable';
   const card=document.createElement('div');card.className='cand-card';
   card.innerHTML=`<div class="cand-head"><span class="badge m">${escapeHtml(candidate.status||response.status)}</span>
    <div style="flex:1;min-width:0"><div class="cand-name">Candidate ${escapeHtml(candidate.component_id)}</div>
    <div class="cand-sub mono">Analysis ${escapeHtml(candidate.analysis_id||'Unavailable')} · ${escapeHtml(candidate.sensor||'Sensor unavailable')} · ${escapeHtml(candidate.t1||'')} → ${escapeHtml(candidate.t2||'')}</div></div></div>
    <div class="cand-info"><div class="cand-mrow mono"><span>AREA <b>${Number.isFinite(candidate.area_pixels)?candidate.area_pixels:'—'} px</b></span><span>MEAN MODEL PROBABILITY <b>${mean}</b></span></div>
    <div class="cand-src">Candidate score: ${score} · deterministic triage score, not confidence</div>
    <div class="cand-actions">${candidate.analysis_id?`<span class="act maybe" onclick="openCandidateAnalysis('${escapeHtml(candidate.analysis_id)}')">View analysis</span>`:''}
     ${candidate.status==='pending'||candidate.status==='flagged'?`<span class="act ok" onclick="decideReview('${escapeHtml(candidate.id)}','confirm',this)">✓ Confirm</span><span class="act no" onclick="decideReview('${escapeHtml(candidate.id)}','reject',this)">✕ Reject</span><span class="act maybe" onclick="decideReview('${escapeHtml(candidate.id)}','need_review',this)">◐ Need review</span>`:''}</div></div>`;
   grid.appendChild(card);
  });
 }catch(error){el.innerHTML=`<div class="flowstrip">${flowStrip('review')}</div><div class="panel rev-empty" role="alert">Review queue unavailable: ${escapeHtml(apiError(error))}</div>`}
};

decideReview=async function(id,decision,button){
 if(button)button.classList.add('disabled');if(button)button.style.pointerEvents='none';
 try{
  await apiJson('/api/review-queue/'+encodeURIComponent(id)+'/decision',{decision,analyst:'Analyst 01'});
  toast('Review decision recorded in the backend audit ledger','success');
  await renderReview();await loadApiDashboard();
 }catch(error){toast(apiError(error),'error');if(button){button.classList.remove('disabled');button.style.pointerEvents='auto'}}
};

renderAudit=async function(){
 const el=document.getElementById('view-audit');
 el.innerHTML=`<div class="flowstrip">${flowStrip('audit')}</div><div class="panel"><div class="panel-b"><span class="spinner"></span> Loading server audit ledger…</div></div>`;
 const filterMap={all:'all',v:'verdicts',o:'ops',s:'system'};
 try{
  const result=await apiRequest('/api/audit?action='+filterMap[AF.filter]+'&limit=500');
  const items=result.items||[];window.BackendAudit={items,integrity:result.integrity};
  App.auditLog=items.map(event=>({...event,t:event.timestamp,h:event.event_hash}));
  const counts={all:result.integrity.verified_events,
   v:items.filter(item=>['CONFIRMED','REJECTED','REVIEW'].includes(item.action)).length,
   o:items.filter(item=>['AOI','ANALYSIS','SEARCH','SCENES','EXPORT'].includes(item.action)).length,
   s:items.filter(item=>['SYSTEM','SESSION'].includes(item.action)).length};
  const chips=[['all','ALL'],['v','VERDICTS'],['o','OPS'],['s','SYSTEM']];
  const integrity=result.integrity||{};
  el.innerHTML=`<div class="flowstrip">${flowStrip('audit')}</div><div class="res-head"><div><div class="res-q">Provenance &amp; Audit Trail</div>
   <div class="res-meta mono">Server SHA-256 event chain · ${integrity.verified_events??0} events verified</div></div>
   <span class="chain-pill ${integrity.intact?'chain-ok':'chain-bad'}">${integrity.intact?'SERVER CHAIN INTACT':'SERVER CHAIN INTEGRITY FAILURE'}</span></div>
   <div class="res-toolbar"><span class="rt-label">Filter</span>${chips.map(c=>`<span class="qchip${AF.filter===c[0]?' on':''}" onclick="AF.filter='${c[0]}';renderAudit()">${c[1]} · ${counts[c[0]]||0}</span>`).join('')}<span class="rt-spacer"></span><button class="rt-btn pri" onclick="exportAuditCSV()">↓ Export Ledger CSV</button></div>
   <div class="panel"><div class="panel-b" style="padding-top:6px"><div class="arow head"><span>TIME</span><span>ACTION</span><span>DETAIL</span><span style="text-align:right">SHA-256</span></div>
   ${items.length?items.map(event=>`<div class="arow"><span class="at">${escapeHtml(event.timestamp||'')}</span><span><span class="tag2 ${ACOL[event.action]||'c'}">${escapeHtml(event.action)}</span></span><span class="ad">${escapeHtml(event.detail||'')}</span><span class="ah">${escapeHtml((event.event_hash||'').slice(0,16))}</span></div>`).join(''):'<div class="tip">No audit events in this filter.</div>'}</div></div>`;
 }catch(error){el.innerHTML=`<div class="flowstrip">${flowStrip('audit')}</div><div class="panel rev-empty" role="alert">Audit ledger unavailable: ${escapeHtml(apiError(error))}</div>`}
};

exportAuditCSV=function(){
 const rows=[['timestamp','action','detail','event_hash','previous_hash']].concat((window.BackendAudit.items||[]).map(e=>[e.timestamp,e.action,e.detail,e.event_hash,e.previous_hash]));
 const csv=rows.map(row=>row.map(value=>'"'+String(value??'').replace(/"/g,'""')+'"').join(',')).join('\r\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
 a.download='avlokan_server_audit_'+new Date().toISOString().slice(0,10)+'.csv';document.body.appendChild(a);a.click();a.remove();
};

async function openCandidateAnalysis(analysisId){
 try{App.backendAnalysis=await apiRequest('/api/change-analyses/'+encodeURIComponent(analysisId));go('detection')}
 catch(error){toast(apiError(error),'error')}
}

queueAOI=function(){toast('Review items are created only by completed backend analyses.','info')};
confirmChange=function(){
 const result=App.backendAnalysis;if(!result)return;
 const candidate=(result.candidates||[]).find(item=>item.retained);if(candidate)decideReview(candidate.id||`${result.analysis_id}:${candidate.component_id}`,'confirm');
};
rejectChange=function(){
 const result=App.backendAnalysis;if(!result)return;
 const candidate=(result.candidates||[]).find(item=>item.retained);if(candidate)decideReview(candidate.id||`${result.analysis_id}:${candidate.component_id}`,'reject');
};

injectReviewModal();
renderReview();
renderAudit();
