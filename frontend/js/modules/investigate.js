/* ==========================================================================
   AVLOKAN - AOI Investigation Modal & Synthetic Tile Renderer
   ========================================================================== */

/* ================= SYNTHETIC TILE RENDERER (investigate modal) ================= */
function drawTile(cv,seed,mode){
 const x=cv.getContext('2d'),w=cv.width,h=cv.height;
 const R=n=>hash(seed*131+n*17,seed*57+n*29);
 const cell=4;
 for(let py=0;py<h;py+=cell)for(let px=0;px<w;px+=cell){
  const e=fbm(px/34+seed*9,py/34+seed*4);
  const m=fbm(px/19+seed*2+50,py/19+seed*6);
  let col;
  if(mode==='delta')col='#efe9d8';
  else if(e<.33)col=TER.deep;else if(e<.395)col=TER.water;else if(e<.43)col=TER.sand;
  else if(m>.62)col=TER.forest;else if(m>.46)col=TER.grass;else col=TER.arid;
  x.fillStyle=col;x.fillRect(px,py,cell,cell)}
 // river
 x.strokeStyle=mode==='delta'?'rgba(123,166,163,.25)':TER.water;
 x.lineWidth=Math.max(3,w*.012);x.beginPath();
 for(let px=0;px<=w;px+=8){const py=h*.62+Math.sin(px/w*6.3+seed)*h*.13;px===0?x.moveTo(px,py):x.lineTo(px,py)}
 x.stroke();
 // road
 x.strokeStyle=mode==='delta'?'rgba(64,58,44,.18)':'#d8cdb2';
 x.lineWidth=Math.max(2,w*.008);
 if(mode==='after')x.setLineDash([10,6]);
 x.beginPath();
 for(let px=0;px<=w;px+=8){const py=h*.3+Math.sin(px/w*4.2+seed*2)*h*.1;px===0?x.moveTo(px,py):x.lineTo(px,py)}
 x.stroke();x.setLineDash([]);
 // change regions
 const nb=3+Math.floor(R(1)*3),blobs=[];
 for(let i=0;i<nb;i++)blobs.push({x:w*.16+R(i+2)*w*.68,y:h*.22+R(i+9)*h*.56,r:12+R(i+5)*22});
 if(mode==='before')blobs.forEach(b=>{
  x.fillStyle='rgba(221,203,166,.5)';x.beginPath();x.arc(b.x,b.y,b.r*.8,0,7);x.fill()});
 if(mode==='after')blobs.forEach(b=>{
  x.fillStyle='rgba(221,203,166,.65)';x.beginPath();x.arc(b.x,b.y,b.r,0,7);x.fill();
  const n=2+Math.floor(R(Math.abs(b.x)|0)*3);
  for(let i=0;i<n;i++){
   const sw=b.r*(.32+R(i+20)*.3),sh=b.r*(.28+R(i+30)*.3);
   const sxp=b.x-b.r/2+R(i+40)*b.r*.7,syp=b.y-b.r/2+R(i+50)*b.r*.7;
   x.fillStyle='rgba(64,58,44,.25)';x.fillRect(sxp+2,syp+2,sw,sh);
   x.fillStyle='#cfc3ae';x.fillRect(sxp,syp,sw,sh);
   x.strokeStyle='rgba(64,58,44,.4)';x.lineWidth=1;x.strokeRect(sxp,syp,sw,sh)}});
 if(mode==='delta')blobs.forEach((b,i)=>{
  const g=x.createRadialGradient(b.x,b.y,2,b.x,b.y,b.r*1.5);
  g.addColorStop(0,i%2?'rgba(124,154,120,.85)':'rgba(123,166,163,.85)');
  g.addColorStop(1,'rgba(124,154,120,0)');
  x.fillStyle=g;x.beginPath();x.arc(b.x,b.y,b.r*1.5,0,7);x.fill();
  x.strokeStyle='#4e6b4f';x.setLineDash([5,4]);x.lineWidth=1.5;
  x.strokeRect(b.x-b.r*1.15,b.y-b.r*1.15,b.r*2.3,b.r*2.3);x.setLineDash([]);
  x.fillStyle='#4e6b4f';x.font='700 10px ui-monospace,monospace';
  x.fillText('Δ'+(i+1),b.x-b.r*1.15,b.y-b.r*1.15-4)});
 x.fillStyle='rgba(64,58,44,.55)';x.fillRect(10,h-16,40,3);
 x.font='700 9px ui-monospace,monospace';x.fillText('1 km',10,h-20)}

/* ================= INVESTIGATE MODAL ================= */
function setSwipe(pct){
 document.getElementById('cvA').style.clipPath=`inset(0 0 0 ${pct}%)`;
 document.getElementById('swHandle').style.left=pct+'%'}

function openInv(id){
 const a=AOIS.find(o=>o.id===id);
 if(!a){const backend=(window.BackendAOIs||[]).find(o=>o.id===id);if(backend){openBackendAoi(backend);return}return}
 curAoi=a;
 document.getElementById('invDot').style.background=colOf(a.status);
 document.getElementById('invName').textContent=a.name;
 document.getElementById('invSub').textContent=
  a.lat.toFixed(4)+'°N, '+a.lng.toFixed(4)+'°E · radius '+a.rad+' km · '+a.passes.length+' passes';
 const b=document.getElementById('invBadge');
 b.className='badge '+(a.status==='high'?'h':a.status==='mid'?'m':'lo');
 b.textContent=a.status==='high'?'HIGH PRIORITY':a.status==='mid'?'UNDER REVIEW':'ROUTINE MONITOR';
 document.getElementById('invSar').classList.toggle('hidden',!a.sar);
 drawTile(document.getElementById('cvB'),a.seed,'before');
 drawTile(document.getElementById('cvA'),a.seed,'after');
 drawTile(document.getElementById('cvD'),a.seed,'delta');
 document.getElementById('tagT1').textContent='T1 · '+a.t1;
 document.getElementById('tagT2').textContent='T2 · '+a.t2;
 document.getElementById('invMetrics').innerHTML=`
  <div class="metric"><div class="mk">CHANGE RATIO</div><div class="mv a">${a.change}%</div></div>
  <div class="metric"><div class="mk">CONFIDENCE</div><div class="mv ${a.conf>=90?'g':'c'}">${a.conf}%</div></div>
  <div class="metric"><div class="mk">SENSOR AGREEMENT</div><div class="mv sm">${a.agree}</div></div>
  <div class="metric"><div class="mk">QUALITY SCORE</div><div class="mv ${a.quality>=.9?'g':'c'}">${a.quality.toFixed(2)}</div></div>`;
 const mid=Math.floor(a.passes.length/2);
 document.getElementById('invTl').innerHTML=a.passes.map((p,i)=>{
  const showLbl=(i===0||i===mid||i===a.passes.length-1);
  return `<div class="tl-item"><span class="tl-dot ${i===0?'t1':i===a.passes.length-1?'t2':''}"></span>`+
   (showLbl?`<div class="tl-l mono">${p.slice(5).replace('-','/')}</div>`:'<div class="tl-l">&nbsp;</div>')+'</div>'}).join('');
 document.getElementById('invCat').innerHTML=
  '<b>Δ Category:</b> '+a.cat+' · <b>Evidence:</b> '+(3+Math.floor(hash(a.seed*131+17,a.seed*57+29)*3))+
  ' localized regions · <b>Window:</b> '+a.t1+' → '+a.t2+' (earliest supported observation). '+
  'Synthetic demo imagery — deterministic procedural render, honestly labeled.';
 setSwipe(50);
 document.getElementById('invOverlay').classList.remove('hidden')}

async function openBackendAoi(a){
 curAoi=a;
 document.getElementById('invName').textContent=a.name;
 document.getElementById('invSub').textContent=`${Number(a.lat).toFixed(4)}°, ${Number(a.lng).toFixed(4)}° · radius ${a.radius_km} km · registered ${a.created_at}`;
 document.getElementById('invBadge').classList.add('hidden');document.getElementById('invSar').classList.add('hidden');
 ['cvB','cvA','cvD'].forEach(id=>{const cv=document.getElementById(id);cv.getContext('2d').clearRect(0,0,cv.width,cv.height)});
 document.getElementById('tagT1').textContent='T1 · unavailable';document.getElementById('tagT2').textContent='T2 · unavailable';
 document.getElementById('invMetrics').innerHTML=`<div class="metric"><div class="mk">AOI ID</div><div class="mv">${escapeHtml(a.id)}</div></div><div class="metric"><div class="mk">LATITUDE</div><div class="mv">${Number(a.lat).toFixed(4)}°</div></div><div class="metric"><div class="mk">LONGITUDE</div><div class="mv">${Number(a.lng).toFixed(4)}°</div></div><div class="metric"><div class="mk">RADIUS</div><div class="mv">${a.radius_km} km</div></div>`;
 document.getElementById('invTl').innerHTML='<div class="tip">Querying local scene catalog…</div>';
 document.getElementById('invCat').textContent='Registered AOI metadata from the AVLOKAN backend. No change result or image evidence is associated with this AOI yet.';
 const actions=document.querySelector('#invOverlay .modal-f button');
 actions.textContent='Query Local Scenes';actions.disabled=false;actions.onclick=()=>queryBackendAoiFromModal();
 const exportButton=document.querySelector('#invOverlay .modal-f button:nth-child(2)');exportButton.disabled=true;exportButton.title='No backend evidence dossier exists for this AOI';
 setSwipe(50);document.getElementById('invOverlay').classList.remove('hidden');
 try{
  const response=await apiJson('/api/scenes/search',{lat:a.lat,lng:a.lng,radius_km:a.radius_km,sensors:['sentinel-2','landsat']});
  document.getElementById('invTl').innerHTML=response.items.length?response.items.map(scene=>`<div class="tl-item"><span class="tl-dot"></span><div class="tl-l mono">${escapeHtml(scene.date)} · ${escapeHtml(scene.sensor)} · ${scene.available_locally?'local raster available':'metadata only'}</div></div>`).join(''):'<div class="tip">No local scene records overlap this AOI.</div>';
  document.getElementById('invCat').textContent=`${response.count} local scene catalog records. External catalog queried: no. Scene quality is not supplied by the catalog.`;
 }catch(error){document.getElementById('invTl').innerHTML=`<div class="tip" role="alert">${escapeHtml(apiError(error))}</div>`}
}

function queryBackendAoiFromModal(){
 if(!curAoi||!curAoi.radius_km)return;
 App.stagedAOI=curAoi;closeInv();go('scene');
}

function closeInv(){document.getElementById('invOverlay').classList.add('hidden')}

function queueAOI(){
 if(!curAoi)return;
 pendingCount++;
 document.getElementById('revBadge').textContent=pendingCount;
 document.getElementById('statPending').textContent=pendingCount.toLocaleString('en-IN');
 addFeed('<span class="tag a">QUEUE</span><b>Analyst 01</b> added <b>'+curAoi.name+'</b> to review queue — '+curAoi.conf+'% confidence');
 toast(curAoi.name+' added to Review Queue','success');
 closeInv()}

function exportDossier(){
 toast('Dossier exported — evidence pack archived to local store (demo build)')}

/* swipe viewer drag */
(function(){
 const sw=document.getElementById('swipe');
 const move=e=>{const r=sw.getBoundingClientRect();
  setSwipe(clamp((e.clientX-r.left)/r.width*100,3,97))};
 sw.addEventListener('pointerdown',e=>{sw.setPointerCapture(e.pointerId);sw._d=true;move(e)});
 sw.addEventListener('pointermove',e=>{if(sw._d)move(e)});
 sw.addEventListener('pointerup',()=>sw._d=false);
 sw.addEventListener('pointercancel',()=>sw._d=false)})();
