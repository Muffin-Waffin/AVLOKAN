/* ==========================================================================
   AVLOKAN - Phase 5: Multi-Temporal Analysis & Change Detection Pipeline
   ========================================================================== */

/* ================= PHASE 5 · MULTI-TEMPORAL / DETECTION / VERIFIED ================= */
delete STUBS.analysis; delete STUBS.detection; delete STUBS.verified;

IC.layers=ICONS.layers; IC.grid=ICONS.grid;
document.querySelectorAll('#view-scene .panel-h').forEach(h=>{if(h.innerHTML.includes('undefined'))h.innerHTML=h.innerHTML.replace('undefined ','')});

const P5={sensor:'optical',running:false,autoSarFor:null};
App.verdicts=[];

function getPair(){
 if(App.pair)return App.pair;
 if(App.stagedPair){const A=App.stagedPair[0],B=App.stagedPair[1];
  return{a:A,b:B,pin:{lat:(A.lat+B.lat)/2,lng:(A.lng+B.lng)/2,rad:4},name:(A.region||'Staged pair')+' · compare origin'}}
 return null}

const _runAnaP4=runAna;
runAna=function(){App.stagedPair=null;_runAnaP4()};
const _sendPairP4=sendPairToAnalysis;
sendPairToAnalysis=function(){App.pair=null;_sendPairP4()};

const pairSeedOf=p=>Math.floor(hash(p.a.seed||11,p.b.seed||23)*1e6)||4242;

function wireSwipe(sw,clipId,handleId){
 const set=v=>{document.getElementById(clipId).style.clipPath=`inset(0 0 0 ${v}%)`;
  document.getElementById(handleId).style.left=v+'%'};
 const move=e=>{const r=sw.getBoundingClientRect();set(clamp((e.clientX-r.left)/r.width*100,3,97))};
 sw.addEventListener('pointerdown',e=>{sw.setPointerCapture(e.pointerId);sw._d=true;move(e)});
 sw.addEventListener('pointermove',e=>{if(sw._d)move(e)});
 sw.addEventListener('pointerup',()=>sw._d=false);
 sw.addEventListener('pointercancel',()=>sw._d=false)}

function drawTileSAR(cv,seed,mode){
 const tmp=document.createElement('canvas');tmp.width=cv.width;tmp.height=cv.height;
 drawTile(tmp,seed,mode);
 const x=cv.getContext('2d');
 x.drawImage(tmp,0,0);
 const w=cv.width,h=cv.height,img=x.getImageData(0,0,w,h),d=img.data;
 for(let p=0;p<w*h;p++){const i4=p*4;
  const inten=(d[i4]*.3+d[i4+1]*.5+d[i4+2]*.2)/255;
  const spk=hash(p+seed,p*3+7)*.26-.13;
  const v=clamp(inten*.8+spk+.1,0,1);
  d[i4]=Math.round(74+v*95);d[i4+1]=Math.round(61+v*87);d[i4+2]=Math.round(82+v*91)}
 x.putImageData(img,0,0)}

function provRow(k,v){return `<div class="ev-row"><span class="k">${k}</span><span class="v mono" style="font-size:11px">${v}</span></div>`}

function catOf(name){
 const s=(name||'').toLowerCase();
 if(/dock|port|berth|coast/.test(s))return 'Maritime infrastructure expansion';
 if(/solar|bhadla/.test(s))return 'Energy array expansion';
 if(/ladakh|forward|lac/.test(s))return 'Forward-sector structural activity';
 if(/industr|shed|depot/.test(s))return 'Industrial construction';
 if(/delhi|ncr/.test(s))return 'Peripheral urban expansion';
 return 'Structural expansion — unspecified class'}

/* ---- pixel diff on same-seed before/after renders ---- */
function computeChangeDiff(seed,sar){
 const w=320,h=180;
 const ca=document.createElement('canvas');ca.width=w;ca.height=h;
 const cb=document.createElement('canvas');cb.width=w;cb.height=h;
 if(sar){drawTileSAR(ca,seed,'before');drawTileSAR(cb,seed,'after')}
 else{drawTile(ca,seed,'before');drawTile(cb,seed,'after')}
 const da=ca.getContext('2d').getImageData(0,0,w,h).data;
 const db=cb.getContext('2d').getImageData(0,0,w,h).data;
 const out=document.createElement('canvas');out.width=w;out.height=h;
 const ox=out.getContext('2d');
 const img=ox.createImageData(w,h);
 const mask=new Uint8Array(w*h);
 let changed=0;
 for(let q=0;q<w*h;q++){const i4=q*4;
  const dist=(Math.abs(da[i4]-db[i4])+Math.abs(da[i4+1]-db[i4+1])+Math.abs(da[i4+2]-db[i4+2]))/3;
  let r=239,g=233,b=216;
  if(dist>30){changed++;mask[q]=1;
   const t=Math.min(1,(dist-30)/60);
   if(t>.5){r=123;g=166;b=163}else{r=124;g=154;b=120}}
  img.data[i4]=r;img.data[i4+1]=g;img.data[i4+2]=b;img.data[i4+3]=255}
 ox.putImageData(img,0,0);
 const BS=10,bc=w/BS,br=h/BS;
 const flag=new Uint8Array(bc*br);
 for(let by=0;by<br;by++)for(let bx=0;bx<bc;bx++){
  let n=0;for(let yy=0;yy<BS;yy++)for(let xx=0;xx<BS;xx++)n+=mask[(by*BS+yy)*w+bx*BS+xx];
  if(n/(BS*BS)>.3)flag[by*bc+bx]=1}
 const seen=new Uint8Array(bc*br);const clusters=[];
 for(let q=0;q<bc*br;q++){
  if(!flag[q]||seen[q])continue;
  const stack=[q];seen[q]=1;
  let minx=99,maxx=-1,miny=99,maxy=-1,size=0;
  while(stack.length){
   const c=stack.pop(),cx=c%bc,cy=(c-cx)/bc;
   size++;minx=Math.min(minx,cx);maxx=Math.max(maxx,cx);miny=Math.min(miny,cy);maxy=Math.max(maxy,cy);
   [[1,0],[-1,0],[0,1],[0,-1]].forEach(d=>{
    const nx=cx+d[0],ny=cy+d[1];
    if(nx<0||ny<0||nx>=bc||ny>=br)return;
    const nq=ny*bc+nx;
    if(flag[nq]&&!seen[nq]){seen[nq]=1;stack.push(nq)}})}
  clusters.push({minx,maxx,miny,maxy,size})}
 clusters.sort((x,y)=>y.size-x.size);
 const boxes=clusters.slice(0,5);
 boxes.forEach((c,i)=>{
  const x=c.minx*BS-3,y=c.miny*BS-3,w2=(c.maxx-c.minx+1)*BS+6,h2=(c.maxy-c.miny+1)*BS+6;
  ox.strokeStyle='#4e6b4f';ox.setLineDash([5,4]);ox.lineWidth=1.5;
  ox.strokeRect(x,y,w2,h2);ox.setLineDash([]);
  ox.fillStyle='#4e6b4f';ox.font='800 10px ui-monospace,monospace';
  ox.fillText('Δ'+(i+1),x,y-3)});
 return{delta:+(changed/(w*h)*100).toFixed(1),regions:boxes.length,boxes,cv:out}}

function computeDet(p){
 const seed=pairSeedOf(p);
 const maxCloud=Math.max(p.a.cloud||0,p.b.cloud||0);
 const sar=maxCloud>45;
 const diff=computeChangeDiff(seed,sar);
 const gate=clamp(1-diff.delta*.02-.02,.4,.99);
 const quality=clamp(1-maxCloud/150,.5,.95);
 const sameSeason=p.a.date.getMonth()===p.b.date.getMonth();
 const conf=Math.round(clamp(60+diff.delta*2.2+(sameSeason?9:-5)+(sar?4:0)+quality*10,35,98));
 return Object.assign(diff,{seed,sar,maxCloud,gate,quality,sameSeason,conf,
  cat:catOf(p.name),verdict:diff.delta>=1.5,
  name:p.name,pin:p.pin,a:p.a,b:p.b,
  gap:Math.abs(Math.round((p.b.date-p.a.date)/864e5)),
  agree:sar?'S2 ◐ · S1 ✓':'S2 ✓ · S1 ✓',
  when:new Date().toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour12:false})})}

/* ---- ANALYSIS VIEW ---- */
function renderAnalysis(){
 const p=getPair();
 const el=document.getElementById('view-analysis');
 if(!p){el.innerHTML=`<div class="flowstrip">${flowStrip('analysis')}</div>
  <div class="panel stub"><div class="si">${ICONS.layers}</div><h2>No pair staged</h2>
  <p>Lock a T1 / T2 scene pair in Select Area / Scene, or send a pair from Compare, to begin multi-temporal analysis.</p>
  <button class="btn btn-primary" style="width:auto" onclick="go('scene')">→ Select Area / Scene</button></div>`;return}
 const seed=pairSeedOf(p);
 const gap=Math.abs(Math.round((p.b.date-p.a.date)/864e5));
 const same=p.a.date.getMonth()===p.b.date.getMonth();
 const maxCloud=Math.max(p.a.cloud||0,p.b.cloud||0);
 if(P5.autoSarFor!==seed){P5.autoSarFor=seed;P5.sensor=maxCloud>45?'sar':'optical'}
 el.innerHTML=`
  <div class="flowstrip">${flowStrip('analysis')}</div>
  <div class="res-head">
   <div><div class="res-q">Multi-Temporal Analysis — ${p.name}</div>
    <div class="res-meta mono">T1 ${p.a.id} (${p.a.date.toISOString().slice(0,10)}) ↔ T2 ${p.b.id} (${p.b.date.toISOString().slice(0,10)}) · ${gap}-day gap · ${same?'same-season pair':'cross-season pair'} · max cloud ${maxCloud}%</div></div>
   <div class="sensor-tabs">
    <button class="sensor-tab opt${P5.sensor==='optical'?' on':''}" onclick="setAnaSensor('optical')">OPTICAL</button>
    <button class="sensor-tab${P5.sensor==='sar'?' on':''}" onclick="setAnaSensor('sar')">SAR</button>
   </div>
  </div>
  <div class="ana-layout">
   <div class="panel">
    <div class="panel-h">${IC.layers} T1 ↔ T2 Swipe <span class="mh-sub">drag the handle · co-registered</span>${maxCloud>45?'<span class="badge violet" style="margin-left:auto">SAR AUTO-SELECTED · CLOUD '+maxCloud+'%</span>':''}</div>
    <div class="panel-b">
     <div class="swipe" id="anaSwipe">
      <canvas id="anCvB" width="640" height="360"></canvas>
      <canvas id="anCvA" width="640" height="360" style="clip-path:inset(0 0 0 50%)"></canvas>
      <div class="sw-handle" id="anHandle" style="left:50%"><span>⇄</span></div>
      <span class="sw-tag l mono">T1 · ${p.a.date.toISOString().slice(0,10)}</span>
      <span class="sw-tag r mono">T2 · ${p.b.date.toISOString().slice(0,10)}</span>
     </div>
     <div class="inv-tip">DRAG TO COMPARE · T1 BASELINE LEFT ↔ T2 CURRENT RIGHT</div>
     <div class="runbar" style="margin-top:14px">
      <button class="btn btn-primary" style="width:auto" onclick="startDetection()">${IC.cpu} Run Change Detection →</button>
      <button class="btn btn-ghost" style="width:auto" onclick="go('scene')">← Re-pick Pair</button>
     </div>
    </div>
   </div>
   <div class="dash-right">
    <div class="panel"><div class="panel-h">${IC.db} Pair Provenance</div><div class="panel-b">
     ${provRow('T1 scene',p.a.id)}
     ${provRow('T1 sensor',p.a.sensor.name+' · cloud '+(p.a.cloud||0)+'%')}
     ${provRow('T2 scene',p.b.id)}
     ${provRow('T2 sensor',p.b.sensor.name+' · cloud '+(p.b.cloud||0)+'%')}
     ${provRow('AOI center',Math.abs(p.pin.lat).toFixed(3)+'°'+(p.pin.lat>=0?'N':'S')+' · '+Math.abs(p.pin.lng).toFixed(3)+'°'+(p.pin.lng>=0?'E':'W'))}
     ${provRow('Radius',p.pin.rad+' km')}
    </div></div>
    <div class="panel"><div class="panel-h">${IC.bulb} Pipeline Preview</div><div class="panel-b">
     <div class="tip"><b>1 · Embedding gate.</b> RemoteCLIP cosine between T1/T2 — cheap semantic screen.</div>
     <div class="tip"><b>2 · BIT verifier.</b> Bitemporal image transformer, per-pixel change mask.</div>
     <div class="tip"><b>3 · SAR fallback.</b> Engaged automatically when optical cloud exceeds 45%.</div>
     <div class="tip"><b>4 · Synthesis.</b> Region clustering, confidence calibration, category.</div>
    </div></div>
   </div>
  </div>`;
 const B=document.getElementById('anCvB'),A=document.getElementById('anCvA');
 if(P5.sensor==='sar'){drawTileSAR(B,seed,'before');drawTileSAR(A,seed,'after')}
 else{drawTile(B,seed,'before');drawTile(A,seed,'after')}
 wireSwipe(document.getElementById('anaSwipe'),'anCvA','anHandle')}

function setAnaSensor(s){P5.sensor=s;renderAnalysis()}

/* ---- DETECTION VIEW ---- */
function startDetection(){App.det=null;go('detection');runDetPipeline()}

function refreshDetection(){
 if(P5.running)return;
 const el=document.getElementById('view-detection');
 if(App.det){renderDetResults();return}
 const p=getPair();
 if(p){el.innerHTML=`<div class="flowstrip">${flowStrip('detection')}</div>
  <div class="panel stub"><div class="si">${ICONS.cpu}</div><h2>Pair staged — pipeline idle</h2>
  <p>${p.a.id} ↔ ${p.b.id} is locked and co-registered. Run the 4-stage verifier to produce verified change evidence.</p>
  <button class="btn btn-primary" style="width:auto" onclick="runDetPipeline()">▶ Run Detection Pipeline</button></div>`;return}
 el.innerHTML=`<div class="flowstrip">${flowStrip('detection')}</div>
  <div class="panel stub"><div class="si">${ICONS.cpu}</div><h2>No pair staged</h2>
  <p>Lock a T1 / T2 scene pair in Select Area / Scene to run change detection.</p>
  <button class="btn btn-primary" style="width:auto" onclick="go('scene')">→ Select Area / Scene</button></div>`}

function runDetPipeline(){
 if(P5.running)return;
 const p=getPair();
 if(!p){toast('No pair staged — lock T1/T2 in Select Area / Scene first');return}
 P5.running=true;
 const d=computeDet(p);
 App.det=d;
 document.getElementById('view-detection').innerHTML=`
  <div class="flowstrip">${flowStrip('detection')}</div>
  <div class="res-head"><div><div class="res-q">Change Detection — ${p.name}</div>
   <div class="res-meta mono">${p.a.id} ↔ ${p.b.id} · running 4-stage verifier</div></div></div>
  <div class="panel">
   <div class="panel-h">${IC.cpu} Detection Pipeline <span class="mh-sub">embedding gate → BIT verifier → SAR fallback → synthesis</span></div>
   <div class="panel-b" id="detSteps"></div>
  </div>`;
 const steps=[
  ['Co-registered pair loaded · '+p.a.id+' ↔ '+p.b.id,340],
  ['Embedding gate · RemoteCLIP cosine T1↔T2 · '+(d.gate*100).toFixed(1)+'% · '+(d.gate<.95?'OPEN':'CLOSED'),420],
  ['Pixel-level BIT verification · bitemporal transformer · 57,600 px',640],
  [d.sar?'SAR fallback ENGAGED · optical cloud '+d.maxCloud+'% · S1 VV/VH cross-check':'Optical quality clean · SAR standby',d.sar?560:280],
  ['Synthesis · region clustering · confidence calibration',320]];
 const total=steps.reduce((a,s)=>a+s[1],0);
 document.getElementById('detSteps').innerHTML=
  steps.map((s,i)=>`<div class="pstep" id="ds${i}"><span class="pnum">${i+1}</span><span>${s[0]}</span><span class="pms" id="dm${i}"></span></div>`).join('')+
  `<div class="pbar"><i id="dbarI" style="width:0%"></i></div>`;
 let i=0,done=0;
 (function next(){
  if(i>0){const q=document.getElementById('ds'+(i-1));q.className='pstep done';
   q.querySelector('.pnum').textContent='✓';
   document.getElementById('dm'+(i-1)).textContent=steps[i-1][1]+' ms'}
  if(i>=steps.length){
   document.getElementById('dbarI').style.width='100%';
   P5.running=false;
   renderDetResults();
   addFeed('<span class="tag a">DETECT</span>Pipeline verified '+p.a.id+' ↔ '+p.b.id+' — '+(d.verdict?d.delta+'% change · '+d.conf+'% conf':'no significant change'));
   toast(d.verdict?'Change verified — '+d.regions+' regions · '+d.conf+'% confidence':'No significant change — candidate suppressed','success');
   return}
  document.getElementById('ds'+i).className='pstep run';
  done+=steps[i][1];
  document.getElementById('dbarI').style.width=Math.round(done/total*100)+'%';
  setTimeout(next,steps[i][1]);i++})()}

function renderDetResults(){
 const d=App.det;if(!d)return;
 const chips=d.boxes.map((c,i)=>{
  const frac=((c.maxx-c.minx+1)*(c.maxy-c.miny+1))/(32*18);
  return `<span class="reg-chip">Δ${i+1} · <b>${(frac*Math.PI*d.pin.rad*d.pin.rad).toFixed(2)} km²</b> · ${d.sar?'S1':'S2'}</span>`}).join('');
 document.getElementById('view-detection').innerHTML=`
  <div class="flowstrip">${flowStrip('detection')}</div>
  <div class="res-head">
   <div><div class="res-q">Change Detection — ${d.name}</div>
    <div class="res-meta mono">${d.a.id} ↔ ${d.b.id} · ${d.gap}-day gap · ${d.sameSeason?'same-season':'cross-season'} · max cloud ${d.maxCloud}%</div></div>
   <span class="badge ${d.sar?'violet':'lo'}">${d.sar?'SAR FALLBACK ENGAGED':'OPTICAL VERIFIED'}</span>
  </div>
  <div class="ana-layout">
   <div>
    <div class="verdict-strip${d.verdict?'':' alert'}">
     <div><div class="vt">${d.verdict?'CHANGE DETECTED — '+d.regions+' region'+(d.regions>1?'s':''):'NO SIGNIFICANT CHANGE'}</div>
      <div class="vs">${d.verdict?d.delta+'% of AOI · confidence '+d.conf+'% · '+d.cat:'below the 1.5% change floor · confidence '+d.conf+'%'}</div></div>
     <button class="btn btn-primary" style="width:auto;margin-left:auto" onclick="go('verified')">View Verified Evidence →</button>
    </div>
    <div class="metrics" style="margin-top:14px">
     <div class="metric"><div class="mk">CHANGE RATIO</div><div class="mv a">${d.delta}%</div></div>
     <div class="metric"><div class="mk">CONFIDENCE</div><div class="mv ${d.conf>=85?'g':'c'}">${d.conf}%</div></div>
     <div class="metric"><div class="mk">EMBEDDING GATE</div><div class="mv c">${(d.gate*100).toFixed(1)}%</div></div>
     <div class="metric"><div class="mk">REGIONS</div><div class="mv ${d.regions?'g':'c'}">${d.regions}</div></div>
    </div>
    <div class="gate-wrap">
     <div class="gate-bar"><i style="width:${(d.gate*100).toFixed(1)}%;background:${d.gate<.95?'linear-gradient(90deg,#d3a656,#c98d68)':'linear-gradient(90deg,#7ba6a3,#7c9a78)'}"></i></div>
     <div class="gate-ticks"><span>0.40</span><span>GATE THRESHOLD 0.95 — ${d.gate<.95?'OPEN · SEMANTIC SHIFT':'CLOSED'}</span><span>1.00</span></div>
    </div>
    <div class="inv-sec">Δ EVIDENCE — PIXEL-LEVEL CHANGE HEAT${d.sar?' · S1 VV/VH RENDER':''}</div>
    <canvas id="detCv" width="320" height="180" style="width:100%;border-radius:10px;border:1px solid var(--line2);display:block"></canvas>
    <div style="margin-top:9px">${chips||'<span class="reg-chip">no regions above floor</span>'}</div>
   </div>
   <div class="dash-right">
    <div class="panel"><div class="panel-h">${IC.cpu} Verifier Trace</div><div class="panel-b">
     ${provRow('Embedding gate',(d.gate*100).toFixed(1)+'% cosine · '+(d.gate<.95?'OPEN':'CLOSED'))}
     ${provRow('BIT verifier','bitemporal · 320×180 · thr 12%')}
     ${provRow('SAR fallback',d.sar?'ENGAGED · cloud '+d.maxCloud+'%':'STANDBY · optical clean')}
     ${provRow('Regions',d.regions+' cluster'+(d.regions===1?'':'s'))}
     ${provRow('Verdict',d.verdict?'ESCALATE — verified':'SUPPRESS — nominal')}
    </div></div>
    <div class="panel"><div class="panel-h">${IC.db} Source Pair</div><div class="panel-b">
     ${provRow('T1',d.a.id)}
     ${provRow('T1 sensor',d.a.sensor.name+' · '+d.a.date.toISOString().slice(0,10))}
     ${provRow('T2',d.b.id)}
     ${provRow('T2 sensor',d.b.sensor.name+' · '+d.b.date.toISOString().slice(0,10))}
     ${provRow('AOI',Math.abs(d.pin.lat).toFixed(3)+'°'+(d.pin.lat>=0?'N':'S')+' · '+Math.abs(d.pin.lng).toFixed(3)+'°'+(d.pin.lng>=0?'E':'W')+' · r='+d.pin.rad+' km')}
    </div></div>
   </div>
  </div>`;
 document.getElementById('detCv').getContext('2d').drawImage(d.cv,0,0)}

/* ---- VERIFIED VIEW ---- */
function renderVerified(){
 const d=App.det;
 const el=document.getElementById('view-verified');
 if(!d){el.innerHTML=`<div class="flowstrip">${flowStrip('verified')}</div>
  <div class="panel stub"><div class="si">${ICONS.check}</div><h2>No verified change yet</h2>
  <p>Run the detection pipeline on a locked T1/T2 pair — verified evidence lands here with full provenance.</p>
  <button class="btn btn-primary" style="width:auto" onclick="go('analysis')">→ Multi-Temporal Analysis</button></div>`;return}
 el.innerHTML=`
  <div class="flowstrip">${flowStrip('verified')}</div>
  <div class="res-head">
   <div><div class="res-q">Verified Change — ${d.name}</div>
    <div class="res-meta mono">every verdict provable · source scenes + verifier trace + analyst sign-off</div></div>
   <span class="badge ${d.sar?'violet':'lo'}">${d.sar?'SAR-CORROBORATED':'OPTICAL-VERIFIED'}</span>
  </div>
  <div class="ana-layout">
   <div>
    <div class="swipe" id="vfSwipe">
     <canvas id="vfCvB" width="640" height="360"></canvas>
     <canvas id="vfCvA" width="640" height="360" style="clip-path:inset(0 0 0 50%)"></canvas>
     <div class="sw-handle" id="vfHandle" style="left:50%"><span>⇄</span></div>
     <span class="sw-tag l mono">T1 · ${d.a.date.toISOString().slice(0,10)}</span>
     <span class="sw-tag r mono">T2 · ${d.b.date.toISOString().slice(0,10)}</span>
    </div>
    <div class="inv-tip">DRAG TO COMPARE · T1 BASELINE ↔ T2 CURRENT</div>
    <div class="metrics">
     <div class="metric"><div class="mk">CHANGE RATIO</div><div class="mv a">${d.delta}%</div></div>
     <div class="metric"><div class="mk">CONFIDENCE</div><div class="mv ${d.conf>=85?'g':'c'}">${d.conf}%</div></div>
     <div class="metric"><div class="mk">SENSOR AGREEMENT</div><div class="mv sm">${d.agree}</div></div>
     <div class="metric"><div class="mk">QUALITY SCORE</div><div class="mv ${d.quality>=.85?'g':'c'}">${d.quality.toFixed(2)}</div></div>
    </div>
    <div class="inv-sec">Δ EVIDENCE — REGION HEAT</div>
    <canvas id="vfDet" width="320" height="180" style="width:100%;border-radius:10px;border:1px solid var(--line2);display:block"></canvas>
    <div class="dossier" style="margin-top:12px"><b>Δ Category:</b> ${d.cat} · <b>Regions:</b> ${d.regions} · <b>Window:</b> ${d.a.date.toISOString().slice(0,10)} → ${d.b.date.toISOString().slice(0,10)} (${d.gap} days) · <b>Method:</b> embedding gate ${(d.gate*100).toFixed(1)}% → BIT pixel verification${d.sar?' → S1 SAR fallback':''}. Synthetic demo imagery — deterministic render, honestly labeled.</div>
    <div class="verdict-strip${d.verdict?'':' alert'}" style="margin-top:14px">
     <div><div class="vt">${d.verdict?'AWAITING ANALYST SIGN-OFF':'CANDIDATE BELOW FLOOR'}</div>
      <div class="vs">confirm to send to the review queue · reject to log a false alarm</div></div>
    </div>
    <div class="runbar" style="margin-top:14px">
     <button class="btn btn-primary" style="width:auto" onclick="confirmChange()">✓ Confirm — Send to Review Queue</button>
     <button class="btn btn-ghost" style="width:auto" onclick="rejectChange()">✕ Reject — False Alarm</button>
     <button class="btn btn-ghost" style="width:auto;margin-left:auto" onclick="exportVerified()">Export Dossier</button>
    </div>
   </div>
   <div class="dash-right">
    <div class="panel"><div class="panel-h">${ICONS.file} Provenance</div><div class="panel-b">
     ${provRow('T1 scene',d.a.id)}
     ${provRow('T1 sensor',d.a.sensor.name+' · cloud '+(d.a.cloud||0)+'%')}
     ${provRow('T2 scene',d.b.id)}
     ${provRow('T2 sensor',d.b.sensor.name+' · cloud '+(d.b.cloud||0)+'%')}
     ${provRow('AOI center',Math.abs(d.pin.lat).toFixed(3)+'°'+(d.pin.lat>=0?'N':'S')+' · '+Math.abs(d.pin.lng).toFixed(3)+'°'+(d.pin.lng>=0?'E':'W'))}
     ${provRow('Gate',(d.gate*100).toFixed(1)+'% · '+(d.gate<.95?'open':'closed'))}
     ${provRow('Verifier','BIT · pixel-level')}
     ${provRow('SAR fallback',d.sar?'engaged':'standby')}
     ${provRow('Analyst','Analyst 01')}
     ${provRow('Signed',d.when+' IST')}
    </div></div>
   </div>
  </div>`;
 const B=document.getElementById('vfCvB'),A=document.getElementById('vfCvA');
 if(d.sar){drawTileSAR(B,d.seed,'before');drawTileSAR(A,d.seed,'after')}
 else{drawTile(B,d.seed,'before');drawTile(A,d.seed,'after')}
 wireSwipe(document.getElementById('vfSwipe'),'vfCvA','vfHandle');
 document.getElementById('vfDet').getContext('2d').drawImage(d.cv,0,0)}

function confirmChange(){
 const d=App.det;if(!d)return;
 pendingCount++;
 document.getElementById('revBadge').textContent=pendingCount;
 document.getElementById('statPending').textContent=pendingCount.toLocaleString('en-IN');
 App.verdicts.push({name:d.name,conf:d.conf,action:'CONFIRMED',when:istTime(),cat:d.cat,t1:d.a.id,t2:d.b.id,delta:d.delta});
 addFeed('<span class="tag g">CONFIRMED</span><b>Analyst 01</b> confirmed change at '+d.name+' — '+d.conf+'% confidence · '+d.regions+' regions');
 toast('Verdict recorded — sent to Review Queue','success');
 go('dashboard')}

function rejectChange(){
 const d=App.det;if(!d)return;
 App.verdicts.push({name:d.name,conf:d.conf,action:'REJECTED',when:istTime(),cat:d.cat,t1:d.a.id,t2:d.b.id,delta:d.delta});
 addFeed('<span class="tag r">REJECTED</span><b>Analyst 01</b> rejected candidate at '+d.name+' — false alarm · '+d.cat);
 toast('Candidate rejected — logged to audit trail');
 go('dashboard')}

function exportVerified(){toast('Evidence dossier exported — archived to local store (demo build)')}

/* ---- NAV HOOKS + BOOT ---- */
const _goP4=go;
go=function(id){_goP4(id);
 if(id==='analysis')renderAnalysis();
 if(id==='detection')refreshDetection();
 if(id==='verified')renderVerified()};

/* Phase 9: use the server ChangeAnalyzer and its saved artifacts. */
renderAnalysis=function(){
 const p=getPair(),el=document.getElementById('view-analysis');
 if(!p){el.innerHTML=`<div class="flowstrip">${flowStrip('analysis')}</div><div class="panel stub"><div class="si">${ICONS.layers}</div><h2>No temporal pair selected</h2><p>Choose two real, locally available Sentinel-2 observations from the scene catalog.</p><button class="btn btn-primary" style="width:auto" onclick="go('scene')">→ Select Area / Scene</button></div>`;return}
 const dates= p.a.date&&p.b.date;
 el.innerHTML=`<div class="flowstrip">${flowStrip('analysis')}</div><div class="res-head"><div><div class="res-q">Change Analysis — ${escapeHtml(p.name)}</div><div class="res-meta mono">${escapeHtml(p.a.id)} → ${escapeHtml(p.b.id)} · actual observation metadata</div></div></div>
  <div class="ana-layout"><div class="panel"><div class="panel-h">${IC.layers} Selected temporal pair</div><div class="panel-b">
   <div class="pairrow"><div><div class="rtitle">T1 · ${escapeHtml(p.a.id)}</div><div class="pair-m mono">${dates?p.a.date.toISOString().slice(0,10):'Date unavailable'} · ${escapeHtml(p.a.sensor.name)}</div></div></div>
   <div class="pairrow"><div><div class="rtitle">T2 · ${escapeHtml(p.b.id)}</div><div class="pair-m mono">${dates?p.b.date.toISOString().slice(0,10):'Date unavailable'} · ${escapeHtml(p.b.sensor.name)}</div></div></div>
   <div class="tip">BIT will run on the backend against the selected local rasters. The API provides no percentage progress.</div>
   <div class="runbar"><button class="btn btn-primary" style="width:auto" onclick="startDetection()">${IC.cpu} Run Change Analysis</button><button class="btn btn-ghost" style="width:auto" onclick="go('scene')">← Re-pick Pair</button></div>
  </div></div><div class="dash-right"><div class="panel"><div class="panel-h">Input availability</div><div class="panel-b">${provRow('T1 local path',escapeHtml(p.a.localPath||'Unavailable'))}${provRow('T2 local path',escapeHtml(p.b.localPath||'Unavailable'))}${provRow('Sensor',escapeHtml(p.a.sensor.name))}${provRow('AOI',escapeHtml(p.name))}</div></div></div></div>`;
};

startDetection=function(){App.backendAnalysis=null;App.det=null;go('detection');runDetPipeline()};
refreshDetection=function(){
 if(P5.running)return;
 if(App.backendAnalysis){renderDetResults();return}
 const p=getPair(),el=document.getElementById('view-detection');
 el.innerHTML=`<div class="flowstrip">${flowStrip('detection')}</div><div class="panel stub"><div class="si">${ICONS.cpu}</div><h2>${p?'Analysis ready':'No temporal pair selected'}</h2><p>${p?'Start the AVLOKAN backend analysis for the selected local observations.':'Select two local Sentinel-2 observations first.'}</p><button class="btn btn-primary" style="width:auto" onclick="${p?'runDetPipeline()':'go(\'scene\')'}">${p?'Run Change Analysis':'→ Select observations'}</button></div>`;
};

runDetPipeline=async function(){
 if(P5.running)return;
 const p=getPair(),prototypePair=p&&p.a.record_type==='prototype_analysis_ready'&&p.b.record_type==='prototype_analysis_ready'&&p.a.observation_role==='T1'&&p.b.observation_role==='T2'&&p.a.pair_id===p.b.pair_id;
 if(!p||(!prototypePair&&(!p.a.localPath||!p.b.localPath))){toast('Select two compatible locally available observations for analysis','error');return}
 P5.running=true;
 const el=document.getElementById('view-detection');
 el.innerHTML=`<div class="flowstrip">${flowStrip('detection')}</div><div class="res-head"><div><div class="res-q">Running change analysis</div><div class="res-meta mono">${escapeHtml(p.a.id)} → ${escapeHtml(p.b.id)}</div></div></div><div class="panel"><div class="panel-b"><span class="spinner"></span> Running BIT inference and writing artifacts on the backend…</div></div>`;
 try{
  const payload=prototypePair?{
   t1_observation_id:p.a.id,t2_observation_id:p.b.id,
   tile_id:p.name||p.a.pair_id,pair_id:p.a.pair_id,name:p.name||'AVLOKAN prototype analysis-ready pair'
  }:{t1_path:p.a.localPath,t2_path:p.b.localPath,
   t1_date:p.a.date.toISOString(),t2_date:p.b.date.toISOString(),sensor:'sentinel-2',
   tile_id:p.name||p.a.id,pair_id:p.a.id+'__'+p.b.id,name:p.name,aoi_id:p.aoiId||undefined};
  const result=await apiJson('/api/change-analyses',payload);
  App.backendAnalysis=result;
  try{App.backendProvenance=await apiRequest(result.artifacts.metadata)}catch(_){App.backendProvenance=null}
  renderDetResults();toast('Backend change analysis completed','success');
 }catch(error){
  el.innerHTML=`<div class="flowstrip">${flowStrip('detection')}</div><div class="panel rev-empty" role="alert"><b>Change analysis failed</b><div>${escapeHtml(apiError(error))}</div><button class="btn btn-ghost" style="width:auto;margin:14px auto 0" onclick="go('scene')">Return to scene selection</button></div>`;
  toast(apiError(error),'error');
 }finally{P5.running=false}
};

function backendArtifactPreview(result,kind){
 const base=result.artifacts[kind];
 return base?apiAsset(base+'_preview'):'';
}

renderDetResults=function(){
 const r=App.backendAnalysis;if(!r)return refreshDetection();
 const stats=r.statistics||{},model=r.model||{},temporal=r.temporal||{},spatial=r.spatial||{};
 const prob=backendArtifactPreview(r,'probability'),raw=backendArtifactPreview(r,'raw_mask'),mask=backendArtifactPreview(r,'candidate_mask');
 const pairImages=`<div class="api-pair-images"><figure><img src="${apiAsset(r.artifacts.t1_preview)}" alt="T1 raster preview"><figcaption>T1 · ${escapeHtml(temporal.t1_date||'')}</figcaption></figure><figure><img src="${apiAsset(r.artifacts.t2_preview)}" alt="T2 raster preview"><figcaption>T2 · ${escapeHtml(temporal.t2_date||'')}</figcaption></figure></div>`;
 const artifact=(title,url,alt)=>`<figure class="api-artifact"><img src="${url}" alt="${alt}" loading="lazy" onerror="this.alt='Artifact preview unavailable'"><figcaption>${title}</figcaption></figure>`;
 const candidates=(r.candidates||[]).filter(c=>c.retained);
 const candidateRows=candidates.map(c=>{const cid=c.id||`${r.analysis_id}:${c.component_id}`;return `<div class="pairrow"><div><div class="rtitle">Candidate ${c.component_id}</div><div class="pair-m mono">${c.area_pixels} px · mean probability ${Number(c.mean_probability).toFixed(4)} · triage score ${c.candidate_score==null?'unavailable':Number(c.candidate_score).toFixed(4)}</div></div><span class="rbtns"><button class="act ok" onclick="decideAnalysisCandidate('${escapeHtml(cid)}','confirm')">Confirm</button><button class="act no" onclick="decideAnalysisCandidate('${escapeHtml(cid)}','reject')">Reject</button></span></div>`}).join('');
 const provenance=App.backendProvenance&&App.backendProvenance.provenance||{};
 document.getElementById('view-detection').innerHTML=`<div class="flowstrip">${flowStrip('detection')}</div>
  <div class="res-head"><div><div class="res-q">Change Analysis · ${escapeHtml(r.name)}</div><div class="res-meta mono">Analysis ${escapeHtml(r.analysis_id)} · ${escapeHtml(r.sensor)} · ${escapeHtml(temporal.t1_date||'')} → ${escapeHtml(temporal.t2_date||'')}</div></div><button class="btn btn-primary" style="width:auto" onclick="go('verified')">View Evidence &amp; Review →</button></div>
  <div class="metrics"><div class="metric"><div class="mk">CHANGED PIXELS</div><div class="mv a">${stats.changed_pixels??'—'}</div></div><div class="metric"><div class="mk">CHANGED FRACTION</div><div class="mv">${stats.changed_percentage==null?'—':Number(stats.changed_percentage).toFixed(4)+'%'}</div></div><div class="metric"><div class="mk">COMPONENTS</div><div class="mv">${stats.connected_component_count??'—'}</div></div><div class="metric"><div class="mk">AREA</div><div class="mv">${stats.changed_area_m2==null?'Unavailable':Number(stats.changed_area_m2).toLocaleString()+' m²'}</div></div></div>
  <div class="panel" style="margin-top:14px"><div class="panel-h">Source observations</div><div class="panel-b">${pairImages}</div></div>
  <div class="panel" style="margin-top:14px"><div class="panel-h">Model outputs · previews preserve raster meaning</div><div class="panel-b"><div class="api-artifact-grid">${artifact('Probability · grayscale linear 0–1',prob,'Probability raster preview')}${artifact('Raw model mask',raw,'Raw threshold mask preview')}${artifact('Final candidate mask',mask,'Postprocessed candidate mask preview')}</div></div></div>
  <div class="ana-layout" style="margin-top:14px"><div class="panel"><div class="panel-h">Retained change candidates</div><div class="panel-b">${candidateRows||'<div class="tip">No retained candidates.</div>'}<div class="tip">Candidate score is an analyst triage score; it is not calibrated confidence.</div></div></div><div class="panel"><div class="panel-h">Analysis provenance</div><div class="panel-b">${provRow('Analysis ID',escapeHtml(r.analysis_id))}${provRow('Checkpoint SHA-256',escapeHtml(model.checkpoint_sha256||'Unavailable'))}${provRow('Threshold',r.threshold??'Unavailable')}${provRow('CRS',escapeHtml(spatial.crs||'Unavailable'))}${provRow('Dimensions',spatial.width&&spatial.height?spatial.width+' × '+spatial.height:'Unavailable')}${provRow('T1 source',escapeHtml(provenance.source_files&&provenance.source_files.T1||'See metadata artifact'))}${provRow('T2 source',escapeHtml(provenance.source_files&&provenance.source_files.T2||'See metadata artifact'))}${provRow('Model load',r.timings_seconds.model_load??'Unavailable')}${provRow('Preprocessing',r.timings_seconds.preprocessing??'Unavailable')}${provRow('Inference',r.timings_seconds.inference??'Unavailable')}${provRow('Postprocessing',r.timings_seconds.postprocessing??'Unavailable')}</div></div></div>`;
};

renderVerified=function(){
 const r=App.backendAnalysis,el=document.getElementById('view-verified');
 if(!r){el.innerHTML=`<div class="flowstrip">${flowStrip('verified')}</div><div class="panel stub"><div class="si">${ICONS.check}</div><h2>No backend analysis selected</h2><p>Run an analysis on a real, locally available temporal pair.</p><button class="btn btn-primary" style="width:auto" onclick="go('scene')">→ Select Area / Scene</button></div>`;return}
 renderDetResults();
 el.innerHTML=`<div class="flowstrip">${flowStrip('verified')}</div><div class="res-head"><div><div class="res-q">Analysis Evidence</div><div class="res-meta mono">${escapeHtml(r.analysis_id)} · provenance and artifacts supplied by the backend</div></div><button class="btn btn-ghost" style="width:auto" onclick="go('detection')">← Analysis results</button></div><div class="panel"><div class="panel-b"><p>Review retained candidates individually. Decisions are written to the backend review queue and SHA-256 audit chain.</p><button class="btn btn-primary" style="width:auto" onclick="go('review')">Open Review Queue</button><button class="btn btn-ghost" style="width:auto;margin-left:8px" onclick="go('audit')">Open Audit Trail</button></div></div>`;
};

async function decideAnalysisCandidate(id,decision){
 try{await apiJson('/api/review-queue/'+encodeURIComponent(id)+'/decision',{decision,analyst:'Analyst 01'});
  toast('Decision recorded in backend audit ledger','success');await loadApiDashboard();go('review');}
 catch(error){toast(apiError(error),'error')}
}

confirmChange=function(){const c=(App.backendAnalysis&&App.backendAnalysis.candidates||[]).find(item=>item.retained);if(c)decideAnalysisCandidate(c.id,'confirm')};
rejectChange=function(){const c=(App.backendAnalysis&&App.backendAnalysis.candidates||[]).find(item=>item.retained);if(c)decideAnalysisCandidate(c.id,'reject')};

renderAnalysis();
refreshDetection();
renderVerified();
