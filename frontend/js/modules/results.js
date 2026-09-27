/* ==========================================================================
   AVLOKAN - Phase 3: Results Ranking, Compare Modal & CSV Export
   ========================================================================== */

/* ================= PHASE 3 · RANKING / COMPARE / EXPORT ================= */
Object.assign(S,{sort:'sim',density:'comfort',qf:{s2:true,s1:true,l8:true,bh:true},compare:[],lastLabel:''});

const _genResultsP2=genResults;
genResults=function(label){S.compare=[];_genResultsP2(label)};

function sortResults(list){
 const c=[...list];
 if(S.sort==='dateNew')c.sort((a,b)=>b.date-a.date);
 else if(S.sort==='dateOld')c.sort((a,b)=>a.date-b.date);
 else if(S.sort==='cloud')c.sort((a,b)=>a.cloud-b.cloud);
 else c.sort((a,b)=>b.sim-a.sim);
 return c}

function shownResults(){return sortResults(S.results.filter(r=>S.qf[r.sensor.id]))}

function setDensity(d){S.density=d;renderResults(S.lastLabel)}
function qfToggle(id){S.qf[id]=!S.qf[id];renderResults(S.lastLabel)}

function toggleCompare(i){
 if(S.compare.includes(i))S.compare=S.compare.filter(x=>x!==i);
 else{if(S.compare.length>=2){S.compare.shift();toast('Compare holds two tiles — replaced the oldest selection')}
  S.compare.push(i)}
 renderResults(S.lastLabel)}

function renderResults(label){
 S.lastLabel=label;
 S.results.forEach((r,idx)=>r._i=idx);
 const shown=shownResults();
 const active=SENSORS.filter(s=>S.sensors[s.id]).map(s=>s.tag).join(' · ');
 const el=document.getElementById('view-results');
 el.innerHTML=`
  <div class="flowstrip">${flowStrip('results')}</div>
  <div class="res-head">
   <div>
    <div class="res-q">Results — ${label}</div>
    <div class="res-meta mono">${shown.length} of ${S.results.length} backend tiles · sensors ${active} · ${S.searchWarnings&&S.searchWarnings.length?S.searchWarnings.map(escapeHtml).join(' · '):'Similarity is retrieval similarity, not confidence.'}</div>
   </div>
   <button class="btn btn-ghost" style="width:auto" onclick="go('search')">← Refine Search</button>
  </div>
  <div class="res-toolbar">
   <span class="rt-label">Sort</span>
   <select class="rsort" onchange="S.sort=this.value;renderResults(S.lastLabel)">
    <option value="sim"${S.sort==='sim'?' selected':''}>Similarity ↓</option>
    <option value="dateNew"${S.sort==='dateNew'?' selected':''}>Newest first</option>
    <option value="dateOld"${S.sort==='dateOld'?' selected':''}>Oldest first</option>
    <option value="cloud"${S.sort==='cloud'?' selected':''}>Lowest cloud</option>
   </select>
   <span class="rt-label">Density</span>
   <span class="dens-toggle">
    <button class="dens-btn${S.density==='comfort'?' on':''}" onclick="setDensity('comfort')">Comfort</button>
    <button class="dens-btn${S.density==='compact'?' on':''}" onclick="setDensity('compact')">Compact</button>
   </span>
   <span class="rt-label">Sensor</span>
   ${SENSORS.map(s=>`<span class="schip ${s.cls}${S.qf[s.id]?' on':''}" onclick="qfToggle('${s.id}')"><span class="sdot"></span>${s.tag}</span>`).join('')}
   <span class="rt-spacer"></span>
   <button class="rt-btn" onclick="openCompare()"${S.compare.length<2||S.results.some(r=>r._api)?' disabled':''} title="Canvas comparison is demo-only; temporal analysis requires observations">⇄ Compare ${S.compare.length}/2</button>
   <button class="rt-btn pri" onclick="exportCSV()">↓ Export CSV</button>
  </div>
  ${shown.length?`<div class="rgrid${S.density==='compact'?' compact':''}" id="rgrid"></div>`
   :`<div class="empty-res">${IC.grid}<div>${S.searchError?escapeHtml(S.searchError):'No backend results match the active filters.'}</div></div>`}`;
 const grid=document.getElementById('rgrid');
 if(!grid)return;
 shown.forEach(r=>{
  const i=r._i,sel=S.compare.includes(i);
  const card=document.createElement('div');card.className='rcard'+(sel?' sel':'');
  card.innerHTML=`
   <div class="rthumb">${r._api?`<img class="api-thumbnail" src="${r.thumbnail_url}" alt="Local satellite tile preview" onerror="this.alt='Preview unavailable';this.removeAttribute('src')">`:'<canvas width="320" height="200"></canvas>'}
    <span class="rsen" style="color:${r.sensor.col}">${r.sensor.tag}</span>
    <span class="rsim">${(r.sim*100).toFixed(1)}%</span>
    <span class="cmp-check" title="Add to compare" onclick="toggleCompare(${i})">${sel?'✓':'⊕'}</span></div>
   <div class="rbody">
    <div class="rtitle">${r.region}</div>
    <div class="rmeta mono">${escapeHtml(r.id)}<br>${r.date&&!Number.isNaN(r.date.getTime())?r.date.toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):'Date unavailable'} · ${Number.isFinite(r.lat)&&Number.isFinite(r.lng)?Math.abs(r.lat).toFixed(3)+'°'+(r.lat>=0?'N':'S')+' '+Math.abs(r.lng).toFixed(3)+'°'+(r.lng>=0?'E':'W'):'Location unavailable'} · cloud ${Number.isFinite(r.cloud)?r.cloud+'%':'unknown'}</div>
    <div class="simbar"><i style="width:${(r.sim*100).toFixed(1)}%"></i></div>
    <div class="rbtns">
     <span class="rbtn pri" onclick="viewRes(${i})">View</span>
     <span class="rbtn" onclick="sendToAnalysis(${i})">Analyze →</span>
    </div>
   </div>`;
  if(!r._api)drawThumb(card.querySelector('canvas'),r.seed,r.feature);
  grid.appendChild(card)})}

function exportCSV(){
 const rows=shownResults();
 if(!rows.length){toast('Nothing to export — no results match the current filters');return}
 const csv=[['rank','tile_id','region','latitude','longitude','acquired','sensor','similarity','cloud_pct']]
  .concat(rows.map((r,i)=>[i+1,r.id,r.region,Number.isFinite(r.lat)?r.lat.toFixed(5):'',Number.isFinite(r.lng)?r.lng.toFixed(5):'',r.date&&!Number.isNaN(r.date.getTime())?r.date.toISOString().slice(0,10):'',r.sensor.name,r.sim,Number.isFinite(r.cloud)?r.cloud:'']))
  .map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\r\n');
 const fname='avlokan_results_'+new Date().toISOString().slice(0,10)+'_'+Date.now().toString().slice(-5)+'.csv';
 const a=document.createElement('a');
 a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
 a.download=fname;document.body.appendChild(a);a.click();a.remove();
 addFeed('<span class="tag c">EXPORT</span><b>Analyst 01</b> exported '+rows.length+' results to CSV — '+fname);
 toast(rows.length+' rows exported — '+fname,'success')}

/* ---- compare modal ---- */
function injectCompareModal(){
 if(document.getElementById('cmpOverlay'))return;
 const o=document.createElement('div');
 o.className='overlay hidden';o.id='cmpOverlay';
 o.onclick=e=>{if(e.target===o)closeCompare()};
 o.innerHTML=`
 <div class="modal" style="width:860px">
  <div class="modal-h">
   <div><div class="inv-t">Pairwise Compare</div><div class="inv-s">Swipe viewer · pixel-level Δ · provenance attached</div></div>
   <span class="badge lo" id="cmpBadge">—</span>
   <button class="icon-btn" style="margin-left:auto" onclick="closeCompare()">✕</button>
  </div>
  <div class="modal-b">
   <div class="cmp-pair">
    <div class="cmp-pv"><div class="k">TILE A</div><div class="v mono" id="cmpNameA">—</div></div>
    <div class="cmp-vs">VS</div>
    <div class="cmp-pv"><div class="k">TILE B</div><div class="v mono" id="cmpNameB">—</div></div>
   </div>
   <div class="swipe" id="cmpSwipe">
    <canvas id="cmpA" width="640" height="360"></canvas>
    <canvas id="cmpB" width="640" height="360" style="clip-path:inset(0 0 0 50%)"></canvas>
    <div class="sw-handle" id="cmpHandle" style="left:50%"><span>⇄</span></div>
    <span class="sw-tag l mono" id="cmpTagA">A</span>
    <span class="sw-tag r mono" id="cmpTagB">B</span>
   </div>
   <div class="inv-tip">DRAG THE HANDLE · TILE A LEFT ↔ TILE B RIGHT</div>
   <div class="metrics" id="cmpMetrics"></div>
   <div class="inv-sec">PIXEL-LEVEL Δ — RAW RGB DISTANCE HEAT</div>
   <canvas id="cmpD"></canvas>
   <div class="diff-note" id="cmpDiffNote">—</div>
  </div>
  <div class="modal-f">
   <button class="btn btn-primary" style="width:auto" onclick="sendPairToAnalysis()">Send Pair → Change Analysis</button>
   <button class="btn btn-ghost" style="width:auto" onclick="toast('Pair dossier exported — archived to local store (demo build)')">Export Pair Dossier</button>
   <button class="btn btn-ghost" style="width:auto;margin-left:auto" onclick="closeCompare()">Close</button>
  </div>
 </div>`;
 document.body.appendChild(o);
 const sw=document.getElementById('cmpSwipe');
 const move=e=>{const r=sw.getBoundingClientRect();setCmpSwipe(clamp((e.clientX-r.left)/r.width*100,3,97))};
 sw.addEventListener('pointerdown',e=>{sw.setPointerCapture(e.pointerId);sw._d=true;move(e)});
 sw.addEventListener('pointermove',e=>{if(sw._d)move(e)});
 sw.addEventListener('pointerup',()=>sw._d=false);
 sw.addEventListener('pointercancel',()=>sw._d=false)}

function setCmpSwipe(p){
 document.getElementById('cmpB').style.clipPath=`inset(0 0 0 ${p}%)`;
 document.getElementById('cmpHandle').style.left=p+'%'}

function openCompare(){
 if(S.compare.length<2){toast('Pick two tiles — click ⊕ on any two result cards');return}
 const A=S.results[S.compare[0]],B=S.results[S.compare[1]];
 document.getElementById('cmpNameA').textContent=A.region+' · '+A.id;
 document.getElementById('cmpNameB').textContent=B.region+' · '+B.id;
 document.getElementById('cmpTagA').textContent='A · '+A.sensor.tag+' · '+A.date.toISOString().slice(0,10);
 document.getElementById('cmpTagB').textContent='B · '+B.sensor.tag+' · '+B.date.toISOString().slice(0,10);
 drawThumb(document.getElementById('cmpA'),A.seed,A.feature);
 drawThumb(document.getElementById('cmpB'),B.seed,B.feature);
 const same=A.sensor.id===B.sensor.id;
 const badge=document.getElementById('cmpBadge');
 badge.textContent=same?'SAME SENSOR · '+A.sensor.tag:'CROSS-SENSOR · '+A.sensor.tag+' ↔ '+B.sensor.tag;
 badge.className='badge '+(same?'lo':'violet');
 const st=computePairDiff(A,B);
 document.getElementById('cmpMetrics').innerHTML=`
  <div class="metric"><div class="mk">VISUAL Δ</div><div class="mv a">${st.delta}%</div></div>
  <div class="metric"><div class="mk">VISUAL SIMILARITY</div><div class="mv ${st.visSim>=70?'g':'c'}">${st.visSim}%</div></div>
  <div class="metric"><div class="mk">DATE GAP</div><div class="mv sm">${st.days} days</div></div>
  <div class="metric"><div class="mk">CHANGED REGIONS</div><div class="mv c">${st.regions}</div></div>`;
 document.getElementById('cmpDiffNote').innerHTML=
  '<b>Δ method:</b> raw RGB channel distance on rendered pixels · threshold 12% · '+st.regions+
  ' changed-region clusters boxed above. Demo-grade verifier — BIT pixel verification ships with Phase 5 (Change Detection).';
 setCmpSwipe(50);
 document.getElementById('cmpOverlay').classList.remove('hidden')}

function closeCompare(){document.getElementById('cmpOverlay').classList.add('hidden')}

function computePairDiff(A,B){
 const w=320,h=180;
 const ca=document.createElement('canvas');ca.width=w;ca.height=h;
 const cb=document.createElement('canvas');cb.width=w;cb.height=h;
 drawThumb(ca,A.seed,A.feature);drawThumb(cb,B.seed,B.feature);
 const da=ca.getContext('2d').getImageData(0,0,w,h).data;
 const db=cb.getContext('2d').getImageData(0,0,w,h).data;
 const out=document.getElementById('cmpD');
 out.width=w;out.height=h;
 const ox=out.getContext('2d');
 const img=ox.createImageData(w,h);
 const mask=new Uint8Array(w*h);
 let changed=0,sumDist=0;
 for(let p=0;p<w*h;p++){
  const i4=p*4;
  const dist=(Math.abs(da[i4]-db[i4])+Math.abs(da[i4+1]-db[i4+1])+Math.abs(da[i4+2]-db[i4+2]))/3;
  sumDist+=dist;
  let r=239,g=233,b=216;
  if(dist>30){changed++;mask[p]=1;
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
 clusters.sort((a,b)=>b.size-a.size);
 const top=clusters.slice(0,5);
 top.forEach((c,i)=>{
  const x=c.minx*BS-3,y=c.miny*BS-3,w2=(c.maxx-c.minx+1)*BS+6,h2=(c.maxy-c.miny+1)*BS+6;
  ox.strokeStyle='#4e6b4f';ox.setLineDash([5,4]);ox.lineWidth=1.5;
  ox.strokeRect(x,y,w2,h2);ox.setLineDash([]);
  ox.fillStyle='#4e6b4f';ox.font='800 10px ui-monospace,monospace';
  ox.fillText('Δ'+(i+1),x,y-3)});
 return{delta:(changed/(w*h)*100).toFixed(1),
  visSim:(100-sumDist/(w*h)/255*100).toFixed(1),
  days:Math.abs(Math.round((B.date-A.date)/864e5)),
  regions:top.length}}

function compareFromLightbox(){
 const i=curTile;if(i==null)return;
 closeTile();
 let best=-1,bs=-1;
 S.results.forEach((r,j)=>{if(j!==i&&r.sim>bs){bs=r.sim;best=j}});
 if(best<0){toast('Need at least two results to compare');return}
 S.compare=[i,best];
 renderResults(S.lastLabel);
 openCompare()}

function sendPairToAnalysis(){
 const A=S.results[S.compare[0]],B=S.results[S.compare[1]];
 App.stagedPair=[A,B];
 addFeed('<span class="tag c">STAGE</span><b>Analyst 01</b> staged pair '+A.id+' ↔ '+B.id+' for change detection');
 toast('Pair staged — Phase 5 wires the full detection pipeline');
 closeCompare();go('analysis')}

function injectTileLightbox(){ /* override: Compare button now live */
 if(document.getElementById('tileOverlay'))return;
 const o=document.createElement('div');
 o.className='overlay hidden';o.id='tileOverlay';
 o.onclick=e=>{if(e.target===o)closeTile()};
 o.innerHTML=`
 <div class="modal" style="width:760px">
  <div class="modal-h">
   <div><div class="inv-t" id="tileBigTitle">—</div><div class="inv-s">Scene detail · decoded tile · provenance attached</div></div>
   <button class="icon-btn" style="margin-left:auto" onclick="closeTile()">✕</button>
  </div>
  <div class="modal-b">
   <canvas id="tileBigCv" width="640" height="400"></canvas>
   <div class="tile-meta" id="tileBigMeta"></div>
  </div>
  <div class="modal-f">
   <button class="btn btn-primary" style="width:auto" onclick="sendToAnalysisFromTile()">Analyze → Multi-Temporal</button>
   <button class="btn btn-ghost" style="width:auto" onclick="compareFromLightbox()">Compare</button>
   <button class="btn btn-ghost" style="width:auto;margin-left:auto" onclick="closeTile()">Close</button>
  </div>
 </div>`;
 document.body.appendChild(o)}

injectCompareModal();
