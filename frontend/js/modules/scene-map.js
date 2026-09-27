/* ==========================================================================
   AVLOKAN - Phase 4: AOI/Scene Selection & Map Explorer
   ========================================================================== */

/* ================= PHASE 4 · AOI / SCENE SELECT + MAP EXPLORER ================= */
delete STUBS.scene; delete STUBS.map;

const S4={scenes:[],t1:null,t2:null,pin:null,rad:3,name:'—',pre:null};
const EXP={cur:null};
const INSTS=[];
var SMAP=null,EMAP=null;
const ARCH_BTN='⌕ Query Local Catalog';

const DENSITY_BLOBS=[
 {lat:18.95,lng:72.84,n:41000},{lat:28.61,lng:77.21,n:38000},{lat:13.08,lng:80.27,n:29000},
 {lat:34.15,lng:77.58,n:19000},{lat:27.54,lng:71.90,n:15000},{lat:23.35,lng:85.30,n:22000},
 {lat:22.80,lng:79.60,n:26000},{lat:19.07,lng:73.86,n:17000},{lat:26.91,lng:75.79,n:12000},
 {lat:30.73,lng:76.78,n:9800},{lat:12.97,lng:77.59,n:14000},{lat:17.38,lng:78.49,n:11000}];

/* ---- reusable map factory (independent state + terrain cache per page) ---- */
function makeMap(cfg){
 const geographic=createAvlokanMap({container:cfg.body,center:[cfg.lat,cfg.lng],zoom:cfg.z,coordsEl:cfg.coordsEl,onPick:cfg.onPick,onPinHit:cfg.onPinHit,onSceneHit:cfg.onSceneHit});
 if(geographic){ geographic.setAOIs(window.BackendAOIs||[]); return geographic; }
 const view=document.getElementById('view-'+cfg.view);
 const body=document.getElementById(cfg.body);
 const cv=document.createElement('canvas');
 cv.style.cssText='position:absolute;inset:0;width:100%;height:100%;cursor:grab;touch-action:none';
 body.insertBefore(cv,body.firstChild);
 const cx=cv.getContext('2d');
 const st={lat:cfg.lat,lng:cfg.lng,z:cfg.z,
  layers:Object.assign({optical:true,sar:false,registry:true,labels:true,density:false},cfg.layers),
  drag:null,hits:[],ox:0,oy:0,w:0,h:0,need:true,userPin:null,pins:cfg.pins||[],blobs:cfg.blobs||null};
 let tcv=document.createElement('canvas'),tcx=tcv.getContext('2d'),tox=-1,toy=-1,tw=0,th=0;
 const WS=()=>512*Math.pow(2,st.z);
 const pX=lng=>(lng+180)/360*WS();
 const pY=lat=>(90-lat)/180*WS();
 const uLng=x=>x/WS()*360-180;
 const uLat=y=>90-y/WS()*180;
 const coordsEl=cfg.coordsEl?document.getElementById(cfg.coordsEl):null;
 const gsdEl=cfg.gsdEl?document.getElementById(cfg.gsdEl):null;
 const kmPx=lat=>360/WS()*111.32*Math.cos(lat*Math.PI/180);

 function renderTerrain(){
  tcv.width=st.w+PAD*2;tcv.height=st.h+PAD*2;
  const x=tcx,cell=8,sar=st.layers.sar;
  for(let py=0;py<tcv.height;py+=cell)for(let px=0;px<tcv.width;px+=cell){
   const wx=px+tox,wy=py+toy;
   const t=terrainAt(wx,wy);
   x.fillStyle=classify(t);x.fillRect(px,py,cell,cell);
   if(sar){x.fillStyle='rgba(168,148,173,.30)';x.fillRect(px,py,cell,cell);
    if(hash((wx>>2)+900,(wy>>2)+700)>.87){x.fillStyle='rgba(111,90,119,.45)';x.fillRect(px,py,cell,cell)}}}}

 function grat(x,w,h){
  const W=WS(),degPx=360/W;
  const steps=[30,15,10,5,2,1,.5,.25,.125];
  const stp=steps.find(s=>s/degPx>=90)||steps[steps.length-1];
  const fmt=(v,p,n)=>(stp<1?Math.abs(v).toFixed(1):Math.round(Math.abs(v)))+'°'+(v>=0?p:n);
  x.strokeStyle='rgba(64,58,44,.13)';x.fillStyle='rgba(64,58,44,.5)';x.font='9px ui-monospace,monospace';x.lineWidth=1;
  const l0=Math.floor(uLng(st.ox)/stp)*stp;
  for(let i=0;i<400;i++){const lng=l0+i*stp,sx=pX(lng)-st.ox;
   if(sx>w)break;if(sx<0)continue;
   x.beginPath();x.moveTo(sx+.5,0);x.lineTo(sx+.5,h);x.stroke();x.fillText(fmt(lng,'E','W'),sx+3,12)}
  const a0=Math.floor(uLat(st.oy)/stp)*stp;
  for(let i=0;i<400;i++){const lat=a0-i*stp,sy=pY(lat)-st.oy;
   if(sy>h)break;if(sy<0)continue;
   x.beginPath();x.moveTo(0,sy+.5);x.lineTo(w,sy+.5);x.stroke();x.fillText(fmt(lat,'N','S'),4,sy-3)}}

 function drawReg(a){
  const sx=pX(a.lng)-st.ox,sy=pY(a.lat)-st.oy;
  const r=Math.max(16,a.rad/kmPx(a.lat));
  if(sx<-r-100||sy<-r-100||sx>st.w+r+100||sy>st.h+r+100)return;
  const col='#5b8c89';
  cx.strokeStyle=col;cx.lineWidth=1.6;cx.setLineDash([6,5]);
  cx.beginPath();cx.arc(sx,sy,r,0,7);cx.stroke();cx.setLineDash([]);
  cx.fillStyle='#fbf8ef';cx.strokeStyle=col;cx.lineWidth=2.5;
  cx.beginPath();cx.arc(sx,sy,7,0,7);cx.fill();cx.stroke();
  cx.fillStyle=col;cx.beginPath();cx.arc(sx,sy,3.2,0,7);cx.fill();
  if(st.layers.labels){
   const lbl=a.name.split('—')[0].trim();
   cx.font='700 10.5px Segoe UI,sans-serif';
   const tw=cx.measureText(lbl).width+16;
   const lx=clamp(sx-tw/2,4,st.w-tw-4),ly=sy-r-30<8?sy+13:sy-r-30;
   cx.fillStyle='rgba(251,248,239,.94)';cx.strokeStyle='rgba(211,202,176,.9)';cx.lineWidth=1;
   rrect(cx,lx,ly,tw,20,7);cx.fill();cx.stroke();
   cx.fillStyle='#403a2c';cx.fillText(lbl,lx+8,ly+13.5);
   cx.fillStyle=col;cx.beginPath();cx.arc(lx+tw-8,ly+10,3,0,7);cx.fill()}
  st.hits.push({x:sx,y:sy,r:Math.max(r,16),a})}

 function drawUserPin(){
  const p=st.userPin;if(!p)return;
  const sx=pX(p.lng)-st.ox,sy=pY(p.lat)-st.oy;
  const r=Math.max(14,p.rad/kmPx(p.lat));
  cx.strokeStyle='#5b8c89';cx.lineWidth=2;cx.setLineDash([7,5]);
  cx.beginPath();cx.arc(sx,sy,r,0,7);cx.stroke();cx.setLineDash([]);
  cx.strokeStyle='#5b8c89';cx.lineWidth=2;
  cx.beginPath();cx.moveTo(sx-12,sy);cx.lineTo(sx+12,sy);cx.moveTo(sx,sy-12);cx.lineTo(sx,sy+12);cx.stroke();
  cx.fillStyle='#fbf8ef';cx.beginPath();cx.arc(sx,sy,5.5,0,7);cx.fill();
  cx.strokeStyle='#5b8c89';cx.lineWidth=2.5;cx.stroke();
  if(st.layers.labels){
   const lbl='AOI · r='+(+p.rad).toFixed(1)+' km';
   cx.font='800 10px ui-monospace,monospace';
   const tw=cx.measureText(lbl).width+14;
   const lx=clamp(sx-tw/2,4,st.w-tw-4),ly=sy+r+8>st.h-26?sy-r-26:sy+r+8;
   cx.fillStyle='rgba(123,166,163,.16)';cx.strokeStyle='rgba(123,166,163,.55)';cx.lineWidth=1;
   rrect(cx,lx,ly,tw,19,6);cx.fill();cx.stroke();
   cx.fillStyle='#41706d';cx.fillText(lbl,lx+7,ly+13)}}

 function drawBlobs(){
  if(!st.layers.density||!st.blobs)return;
  st.blobs.forEach(b=>{
   const sx=pX(b.lng)-st.ox,sy=pY(b.lat)-st.oy;
   const r=Math.max(16,(30+b.n/700)/kmPx(b.lat));
   if(sx<-r||sy<-r||sx>st.w+r||sy>st.h+r)return;
   const g=cx.createRadialGradient(sx,sy,2,sx,sy,r);
   g.addColorStop(0,'rgba(123,166,163,.32)');g.addColorStop(1,'rgba(123,166,163,0)');
   cx.fillStyle=g;cx.beginPath();cx.arc(sx,sy,r,0,7);cx.fill();
   if(st.layers.labels){
    cx.fillStyle='rgba(65,112,109,.9)';cx.font='700 9.5px ui-monospace,monospace';cx.textAlign='center';
    cx.fillText((b.n/1000).toFixed(1)+'k',sx,sy+3);cx.textAlign='left'}})}

 function render(){
  const w=body.clientWidth,h=body.clientHeight;
  if(!w||!h)return;
  st.w=w;st.h=h;
  if(cv.width!==w||cv.height!==h){cv.width=w;cv.height=h}
  const W=WS();
  st.ox=clamp(pX(st.lng)-w/2,0,Math.max(0,W-w));
  st.oy=clamp(pY(st.lat)-h/2,0,Math.max(0,W-h));
  if(tox<0||tw!==w||th!==h||Math.abs(st.ox-PAD-tox)>PAD||Math.abs(st.oy-PAD-toy)>PAD){
   tox=st.ox-PAD;toy=st.oy-PAD;tw=w;th=h;renderTerrain()}
  cx.clearRect(0,0,w,h);
  cx.drawImage(tcv,Math.round(tox-st.ox),Math.round(toy-st.oy));
  grat(cx,w,h);
  st.hits=[];
  drawBlobs();
  if(st.layers.registry)(window.BackendAOIs||[]).forEach(a=>drawReg({...a,rad:a.radius_km}));
  drawUserPin();
  if(gsdEl){const gsd=360*111320/W*Math.cos(st.lat*Math.PI/180);
   gsdEl.textContent='GSD ≈ '+(gsd>=1000?(gsd/1000).toFixed(2)+' km/px':Math.round(gsd)+' m/px')}
  st.need=false}

 cv.addEventListener('pointerdown',e=>{cv.setPointerCapture(e.pointerId);
  st.drag={sx:e.clientX,sy:e.clientY,ox:st.ox,oy:st.oy,moved:0};cv.style.cursor='grabbing'});
 cv.addEventListener('pointermove',e=>{
  const r=cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  if(st.drag){
   const dx=e.clientX-st.drag.sx,dy=e.clientY-st.drag.sy;
   st.drag.moved=Math.max(st.drag.moved,Math.abs(dx)+Math.abs(dy));
   const W=WS();
   const nox=clamp(st.drag.ox-dx,0,Math.max(0,W-st.w));
   const noy=clamp(st.drag.oy-dy,0,Math.max(0,W-st.h));
   st.lng=uLng(nox+st.w/2);st.lat=clamp(uLat(noy+st.h/2),-78,78);
   st.need=true}
  else if(coordsEl){
   const lat=uLat(st.oy+my),lng=uLng(st.ox+mx);
   coordsEl.textContent=Math.abs(lat).toFixed(4)+'°'+(lat>=0?'N':'S')+'  '+Math.abs(lng).toFixed(4)+'°'+(lng>=0?'E':'W')}});
 cv.addEventListener('pointerup',e=>{
  const wasClick=st.drag&&st.drag.moved<6;
  st.drag=null;cv.style.cursor='grab';
  if(!wasClick)return;
  const r=cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  let best=null,bd=1e9;
  st.hits.forEach(hh=>{const d=Math.hypot(hh.x-mx,hh.y-my);if(d<hh.r&&d<bd){bd=d;best=hh.a}});
  if(best&&cfg.onPinHit){cfg.onPinHit(best);return}
  if(cfg.onPick)cfg.onPick(uLng(st.ox+mx),clamp(uLat(st.oy+my),-78,78))});
 cv.addEventListener('wheel',e=>{
  e.preventDefault();
  const r=cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  const gx=uLng(st.ox+mx),gy=uLat(st.oy+my);
  st.z=clamp(st.z+(e.deltaY<0?.5:-.5),3,9);
  const nx=pX(gx)-mx,ny=pY(gy)-my;
  st.lng=uLng(nx+st.w/2);st.lat=clamp(uLat(ny+st.h/2),-78,78);
  tox=-1;st.need=true},{passive:false});
 window.addEventListener('resize',()=>{tox=-1;st.need=true});

 (function pump(){
  if(st.need&&view.classList.contains('active'))render();
  requestAnimationFrame(pump)})();

 const api={st,
  setPin(p){st.userPin=p;st.need=true},
  clearPin(){st.userPin=null;st.need=true},
  flyTo(lat,lng,z){st.lat=lat;st.lng=lng;if(z)st.z=z;tox=-1;st.need=true},
  zoom(d){st.z=clamp(st.z+d,3,9);tox=-1;st.need=true},
  home(){st.lat=cfg.lat;st.lng=cfg.lng;st.z=cfg.z;tox=-1;st.need=true},
  toggle(k){st.layers[k]=!st.layers[k];if(k==='sar')tox=-1;st.need=true;return st.layers[k]},
  invalidate(){tox=-1;st.need=true}};
 INSTS.push(api);
 return api}

function chipToggle(mapVar,chipId,key){
 const m=window[mapVar];if(!m)return;
 const on=m.toggle(key);
 document.getElementById(chipId).classList.toggle('on',on)}

function nearestRegion(lat,lng){
 let best=null,bd=1e9;
 REGIONS.slice(1).forEach(r=>{
  const d=Math.hypot(r.lat-lat,(r.lng-lng)*Math.cos(lat*Math.PI/180));
  if(d<bd){bd=d;best=r}});
 return{r:best,d:bd}}

/* ---- SCENE SELECTOR ---- */
function injectScene(){
 document.getElementById('view-scene').innerHTML=`
  <div class="flowstrip">${flowStrip('scene')}</div>
  <div class="staged-banner hidden" id="stagedBanner"></div>
  <div class="scene-layout">
   <div class="panel map-panel">
    <div class="panel-h">${IC.map} Select Area / Scene <span class="mh-sub">offline geographic basemap · click to query local catalog</span> <span class="mh-live"><span class="dot"></span>LOCAL</span></div>
    <div class="map-body" id="sceneMapBody" style="min-height:560px">
     <div class="map-chips">
      <span class="mchip on" id="scL-opt">LOCAL BASEMAP</span>
      <span class="mchip on" id="scL-reg" onclick="chipToggle('SMAP','scL-reg','registry')">AOI REGISTRY</span>
      <span class="mchip on" id="scL-lbl" onclick="chipToggle('SMAP','scL-lbl','labels')">LABELS</span>
     </div>
     <div class="map-zoom">
      <button class="zbtn" onclick="SMAP.zoom(1)">+</button>
      <button class="zbtn" onclick="SMAP.zoom(-1)">−</button>
      <button class="zbtn" onclick="SMAP.home()">⌂</button>
     </div>
     <div class="map-coords mono" id="scCoords">—</div>
     <div class="map-legend">
      <span class="legend-item"><span class="lg" style="background:#5b8c89"></span>REGISTERED AOI</span>
     </div>
    </div>
        <div class="map-foot"><span>CLICK TO PLACE AOI · CLICK A REGISTRY PIN TO SNAP · SCROLL TO ZOOM</span><span class="mono" id="scGsd">GSD —</span></div>
   </div>

   <div class="dash-right">
    <div class="panel">
     <div class="panel-h">${IC.map} AOI Parameters</div>
     <div class="panel-b">
      <div class="srow"><span class="sk">Center</span><span class="sv c mono" id="aoiCoords">—</span></div>
      <div class="srow"><span class="sk">Designation</span><span class="sv" id="aoiName" style="font-size:11px">—</span></div>
      <div class="field" style="margin:10px 0 4px"><label>Observation radius · <span class="fval" id="radVal">3.0 km</span></label>
       <input type="range" class="frange" id="radSlider" min="5" max="200" value="30" oninput="setRad(this.value/10)">
      </div>
      <button class="btn btn-ghost" style="width:auto" onclick="clearAOI()">Clear AOI</button>
      <button class="btn btn-ghost" style="width:auto;margin-left:6px" onclick="queryPrototypeFootprint()">Find Prototype Pair Footprint</button>
     </div>
    </div>
    <div class="panel">
     <div class="panel-h">${IC.db} Archive Query</div>
     <div class="panel-b">
      <button class="btn btn-primary" style="width:auto" id="queryBtn" onclick="queryArchive()">${ARCH_BTN}</button>
      <div class="pair-hint" id="qCount" style="margin-top:8px">Search the local scene catalog; no external archive is queried.</div>
      <div id="qProg"></div>
     </div>
    </div>
    <div class="panel">
     <div class="panel-h">${IC.clock} Acquisition Timeline</div>
     <div class="panel-b">
      <div class="tlwrap"><div class="axis"></div><div id="tlDots"></div></div>
      <div class="tl-labels"><span class="mono" id="tlMin">—</span><span class="mono" id="tlMax">—</span></div>
      <div class="tl-legend">
       <span><span class="sw" style="background:#7c9a78"></span>Clean ≤25%</span>
       <span><span class="sw" style="background:#d3a656"></span>Marginal ≤45%</span>
       <span><span class="sw" style="background:#c98b8b"></span>Hazy</span>
       <span><span class="sw" style="background:#a39a86"></span>Blocked</span>
       <span><span class="sw" style="background:#5b8c89;box-shadow:0 0 0 2px rgba(123,166,163,.35)"></span>T1</span>
       <span><span class="sw" style="background:#4e6b4f;box-shadow:0 0 0 2px rgba(124,154,120,.35)"></span>T2</span>
      </div>
      <div class="pair-hint" id="tlHint">Place an AOI and query the archive to assemble the acquisition timeline.</div>
     </div>
    </div>
    <div class="panel">
     <div class="panel-h">${IC.layers} Scene Pair — T1 / T2</div>
     <div class="panel-b">
      <div id="pairBox"><div class="pair-hint">Select a baseline scene (T1) and a current scene (T2) on the timeline.</div></div>
      <button class="btn btn-primary" id="runAnaBtn" style="width:auto;margin-top:10px" disabled onclick="runAna()">Run Change Analysis →</button>
     </div>
    </div>
   </div>
  </div>`;
 }

IC.map=ICONS.map; IC.globe=ICONS.globe;

/* ---- MAP EXPLORER ---- */
function injectExplore(){
 document.getElementById('view-map').innerHTML=`
  <div class="flowstrip">${flowStrip('scene')}</div>
  <div class="panel map-panel">
   <div class="panel-h">${IC.globe} Map Explorer <span class="mh-sub">offline geographic basemap · click for local catalog records</span> <span class="mh-live"><span class="dot"></span>LOCAL</span></div>
   <div class="map-body" id="exploreMapBody" style="min-height:640px">
    <div class="map-chips">
     <span class="mchip on" id="exL-opt">LOCAL BASEMAP</span>
     <span class="mchip on" id="exL-reg" onclick="chipToggle('EMAP','exL-reg','registry')">AOI REGISTRY</span>
     <span class="mchip on" id="exL-lbl" onclick="chipToggle('EMAP','exL-lbl','labels')">LABELS</span>
     <span class="mchip" id="exL-den" onclick="chipToggle('EMAP','exL-den','density')">DEMO COVERAGE</span>
    </div>
    <div class="map-zoom">
     <button class="zbtn" onclick="EMAP.zoom(1)">+</button>
     <button class="zbtn" onclick="EMAP.zoom(-1)">−</button>
     <button class="zbtn" onclick="EMAP.home()">⌂</button>
    </div>
    <div class="map-coords mono" id="exCoords">—</div>
    <div class="map-legend">
     <span class="legend-item"><span class="lg" style="background:#5b8c89"></span>REGISTERED AOI</span>
    </div>
    <div class="explore-info" id="exploreInfo">
     <div class="ei-t" id="eiT">—</div>
     <div class="ei-m" id="eiM">—</div>
     <div id="eiRows"></div>
     <div class="ei-btns">
      <button class="rt-btn" onclick="exploreToSearch()">Search This Area →</button>
      <button class="rt-btn" onclick="exploreToAnalysis()">Analyze This Area →</button>
      <button class="rt-btn pri" onclick="registerAOI()">Register AOI</button>
     </div>
    </div>
   </div>
   <div class="map-foot"><span>CLICK TERRAIN FOR LOCATION INTEL · CLICK REGISTRY PINS TO INVESTIGATE</span><span class="mono" id="exGsd">GSD —</span></div>
  </div>
  <div class="panel" style="margin-top:16px">
   <div class="panel-h">${IC.map} Quick Jump</div>
   <div class="panel-b"><div class="ex-queries">${REGIONS.slice(1).map(r=>`<span class="qchip" onclick="EMAP.flyTo(${r.lat},${r.lng},6)">${r.name.split('—')[0].trim()}</span>`).join('')}</div></div>
  </div>`}

/* ---- SCENE SELECTOR LOGIC ---- */
function scenePick(lat,lng,name){
 S4.pin={lat,lng};
 if(!S4.rad)S4.rad=3;
 const nr=nearestRegion(lat,lng);
 S4.name=name||((nr.r&&nr.d<1.5)?nr.r.name:'Custom AOI · '+(nr.r?nr.r.name.split('—')[0].trim()+' sector':'open terrain'));
 SMAP.setPin({lat,lng,rad:S4.rad});
 S4.scenes=[];S4.t1=null;S4.t2=null;
 renderTimeline();renderPair();
 document.getElementById('qCount').textContent='Search the local scene catalog; no external archive is queried.';
 updateScenePanel()}

function queryPrototypeFootprint(){
 const center={lat:22.7773596805,lng:75.8247378015};
 S4.rad=4;
 SMAP.flyTo(center.lat,center.lng,8);
 scenePick(center.lat,center.lng,'Existing prototype raster footprint');
 document.getElementById('radSlider').value=40;
 document.getElementById('radVal').textContent='4.0 km';
 queryArchive();
}

function snapPin(a){
 scenePick(a.lat,a.lng,a.name);
 S4.rad=a.rad;
 SMAP.setPin({lat:a.lat,lng:a.lng,rad:a.rad});
 document.getElementById('radSlider').value=a.rad*10;
 document.getElementById('radVal').textContent=(+a.rad).toFixed(1)+' km';
 toast('Snapped to '+a.name+' — radius '+a.rad+' km')}

function setRad(v){
 S4.rad=+v;
 document.getElementById('radVal').textContent=(+v).toFixed(1)+' km';
 if(S4.pin)SMAP.setPin({lat:S4.pin.lat,lng:S4.pin.lng,rad:S4.rad})}

function clearAOI(){
 S4.pin=null;S4.scenes=[];S4.t1=null;S4.t2=null;
 SMAP.clearPin();renderTimeline();renderPair();updateScenePanel();
 document.getElementById('qCount').textContent='Search the local scene catalog; no external archive is queried.'}

function updateScenePanel(){
 document.getElementById('aoiCoords').textContent=S4.pin?Math.abs(S4.pin.lat).toFixed(4)+'°'+(S4.pin.lat>=0?'N':'S')+' · '+Math.abs(S4.pin.lng).toFixed(4)+'°'+(S4.pin.lng>=0?'E':'W'):'—';
 document.getElementById('aoiName').textContent=S4.name;
 document.getElementById('radVal').textContent=(+S4.rad).toFixed(1)+' km';
 document.getElementById('radSlider').value=S4.rad*10}

function queryArchive(){
 if(!S4.pin){toast('Place an AOI first — click anywhere on the map');return}
 if(S4.querying)return;S4.querying=true;
 const btn=document.getElementById('queryBtn');
 btn.disabled=true;btn.innerHTML='<span class="spinner"></span> Querying…';
 const steps=[
  ['STAC search · bbox ±'+S4.rad+' km · 2020→2026',420],
  ['Quality gate · cloud & nodata masking',340],
  ['Co-registration · phase correlation',380],
  ['Timeline assembly',200]];
 const total=steps.reduce((a,s)=>a+s[1],0);
 document.getElementById('qProg').innerHTML=
  steps.map((s,i)=>`<div class="pstep" id="qs${i}"><span class="pnum">${i+1}</span><span>${s[0]}</span><span class="pms" id="qm${i}"></span></div>`).join('')+
  `<div class="pbar"><i id="qbarI" style="width:0%"></i></div>`;
 let i=0,done=0;
 (function next(){
  if(i>0){const p=document.getElementById('qs'+(i-1));p.className='pstep done';
   p.querySelector('.pnum').textContent='✓';
   document.getElementById('qm'+(i-1)).textContent=steps[i-1][1]+' ms'}
  if(i>=steps.length){
   document.getElementById('qbarI').style.width='100%';
   genScenes();renderTimeline();renderPair();
   S4.querying=false;btn.disabled=false;btn.innerHTML=ARCH_BTN;
   const ok=S4.scenes.filter(s=>!s.blocked).length;
   document.getElementById('qCount').textContent=S4.scenes.length+' scenes · '+ok+' passed quality gate';
   addFeed('<span class="tag c">STAC</span>Archive query at '+S4.pin.lat.toFixed(3)+', '+S4.pin.lng.toFixed(3)+' — '+S4.scenes.length+' scenes · '+ok+' usable');
   toast(ok+' usable scenes on timeline — pick T1 and T2','success');
   return}
  document.getElementById('qs'+i).className='pstep run';
  done+=steps[i][1];
  document.getElementById('qbarI').style.width=Math.round(done/total*100)+'%';
  setTimeout(next,steps[i][1]);i++})()}

function genScenes(){
 const seed=Math.round(S4.pin.lat*1e4)+Math.round(S4.pin.lng*1e4)*7;
 const n=9+Math.floor(hash(seed,3)*6);
 const t0=Date.parse('2020-01-01'),t1=Date.now();
 const sensors=[SENSORS[0],SENSORS[2]];
 S4.scenes=[];
 for(let i=0;i<n;i++){
  const dt=new Date(t0+(i/(n-1))*(t1-t0)+(hash(seed+i,i*3)-.5)*120*864e5);
  const cloud=Math.round(hash(seed+i*7,i)*95);
  const blocked=cloud>70;
  const sen=sensors[Math.floor(hash(seed+i*11,i*5)*2)];
  S4.scenes.push({
   id:sen.prefix+'_'+dt.toISOString().slice(0,10).replace(/-/g,'')+'_T'+(10000+Math.floor(hash(seed+i,i*9)*89999)),
   date:dt,cloud,blocked,sensor:sen,
   quality:blocked?0:+(.62+(100-cloud)/100*.35).toFixed(2),
   seed:Math.floor(hash(seed+i*13,i*17)*1e6)})}
 S4.scenes.sort((a,b)=>a.date-b.date);
 S4.t1=null;S4.t2=null}

function renderTimeline(){
 const box=document.getElementById('tlDots'),hint=document.getElementById('tlHint');
 const min=document.getElementById('tlMin'),max=document.getElementById('tlMax');
 if(!S4.scenes.length){box.innerHTML='';min.textContent='—';max.textContent='—';
  hint.textContent='Place an AOI and query the archive to assemble the acquisition timeline.';return}
 const t0=S4.scenes[0].date.getTime(),t1=S4.scenes[S4.scenes.length-1].date.getTime();
 min.textContent=S4.scenes[0].date.toLocaleDateString('en-IN',{month:'short',year:'numeric'});
 max.textContent=S4.scenes[S4.scenes.length-1].date.toLocaleDateString('en-IN',{month:'short',year:'numeric'});
 const ok=S4.scenes.filter(s=>!s.blocked).length;
 hint.textContent=S4.scenes.length+' scenes · '+ok+' passed the quality gate — click two to lock T1 / T2';
 box.innerHTML=S4.scenes.map((s,i)=>{
  const f=t1>t0?(s.date.getTime()-t0)/(t1-t0):.5;
  const cls=s.blocked?'dis':(i===S4.t1?'t1':i===S4.t2?'t2':(s.cloud>45?'c2':s.cloud>25?'c1':'c0'));
  return `<span class="pdot ${cls}" style="left:calc(10px + (100% - 20px)*${f.toFixed(3)})" title="${s.date.toISOString().slice(0,10)} · ${s.sensor.tag} · cloud ${s.cloud}%${s.blocked?' · BLOCKED':''}" onclick="pickScene(${i})"></span>`}).join('')}

function pickScene(i){
 const sc=S4.scenes[i];if(!sc)return;
 if(SMAP&&SMAP.selectScene)SMAP.selectScene(i);
 if(sc.blocked){toast('Scene cloud-blocked ('+sc.cloud+'%) — excluded by the quality gate');return}
 if(sc.record_type==='prototype_analysis_ready'){
  if(S4.t1!=null&&S4.scenes[S4.t1]?.record_type!=='prototype_analysis_ready')S4.t1=null;
  if(S4.t2!=null&&S4.scenes[S4.t2]?.record_type!=='prototype_analysis_ready')S4.t2=null;
  if(S4.t1===i)S4.t1=null;
  else if(S4.t2===i)S4.t2=null;
  else if(sc.observation_role==='T1')S4.t1=i;
  else if(sc.observation_role==='T2')S4.t2=i;
 }else{
  if(S4.t1!=null&&S4.scenes[S4.t1]?.record_type==='prototype_analysis_ready')S4.t1=null;
  if(S4.t2!=null&&S4.scenes[S4.t2]?.record_type==='prototype_analysis_ready')S4.t2=null;
  if(S4.t1===i)S4.t1=null;
  else if(S4.t2===i)S4.t2=null;
  else if(S4.t1==null)S4.t1=i;
  else if(S4.t2==null)S4.t2=i;
  else S4.t2=i;
 }
 if(S4.t1!=null&&S4.t2!=null&&S4.scenes[S4.t1]?.record_type!=='prototype_analysis_ready'){
  if(S4.scenes[S4.t1].date>S4.scenes[S4.t2].date){const t=S4.t1;S4.t1=S4.t2;S4.t2=t}}
 renderTimeline();renderPair()}

function renderPair(){
 const box=document.getElementById('pairBox'),btn=document.getElementById('runAnaBtn');
 if(S4.t1==null||S4.t2==null){
  box.innerHTML='<div class="pair-hint">Select a baseline scene (T1) and a current scene (T2) on the timeline above.'+(S4.t1!=null?' <b style="color:var(--cyan-d)">T1 locked — now pick T2.</b>':'')+'</div>';
  btn.disabled=true;return}
 const a=S4.scenes[S4.t1],b=S4.scenes[S4.t2];
 const gap=Math.round((b.date-a.date)/864e5);
 const same=a.date.getMonth()===b.date.getMonth();
 box.innerHTML=`
  <div class="pairrow"><div><div class="rtitle">T1 · ${a.id}</div><div class="pair-m mono">${a.date.toISOString().slice(0,10)} · ${a.sensor.tag} · cloud ${a.cloud}% · Q ${a.quality}</div></div></div>
  <div class="pairrow"><div><div class="rtitle">T2 · ${b.id}</div><div class="pair-m mono">${b.date.toISOString().slice(0,10)} · ${b.sensor.tag} · cloud ${b.cloud}% · Q ${b.quality}</div></div></div>
  <div class="pairrow" style="border:none"><span class="badge ${same?'lo':'m'}">${same?'SAME-SEASON PAIR ✓':'CROSS-SEASON — FALSE-ALARM RISK'}</span><span class="pair-gap" style="margin-left:auto">${gap} day gap</span></div>`;
 btn.disabled=false}

renderPair=function(){
 const box=document.getElementById('pairBox'),btn=document.getElementById('runAnaBtn');
 if(S4.t1==null||S4.t2==null){box.innerHTML='<div class="pair-hint">Select two dated observations on the timeline above.</div>';btn.disabled=true;return}
 const a=S4.scenes[S4.t1],b=S4.scenes[S4.t2];
 if(!a||!b||!a.date||!b.date){btn.disabled=true;return}
 const gap=Math.abs(Math.round((b.date-a.date)/864e5));
 const prototypePair=a.record_type==='prototype_analysis_ready'&&b.record_type==='prototype_analysis_ready'&&a.pair_id===b.pair_id&&a.observation_role==='T1'&&b.observation_role==='T2';
 const row=(role,s)=>`<div class="pairrow"><div><div class="rtitle">${role} · ${escapeHtml(s.id)}</div><div class="pair-m mono">${s.date.toISOString().slice(0,10)} · ${escapeHtml(s.sensor.name)} · ${s.record_type==='prototype_analysis_ready'?escapeHtml(s.source):'Archive catalog record'} · ${s.available_locally?'local raster available':'metadata only'}</div></div></div>`;
 box.innerHTML=row('T1',a)+row('T2',b)+`<div class="pairrow" style="border:none"><span class="badge ${prototypePair?'lo':'m'}">${prototypePair?'CONFIGURED PROTOTYPE ROLES · ORDER PRESERVED':'ARCHIVE OBSERVATIONS'}</span><span class="pair-gap" style="margin-left:auto">${gap} day gap</span></div>`+
  (prototypePair?'<div class="tip">These are existing analysis-ready prototype assets, not archive scene downloads. Supplied T1/T2 roles are preserved and may not be chronological.</div>':'');
 btn.disabled=!(prototypePair||(a.record_type!=='prototype_analysis_ready'&&b.record_type!=='prototype_analysis_ready'&&a.sensor.id==='s2'&&b.sensor.id==='s2'&&a.available_locally&&b.available_locally&&a.localPath&&b.localPath));
};

function runAna(){
 if(S4.t1==null||S4.t2==null||!S4.pin)return;
 const a=S4.scenes[S4.t1],b=S4.scenes[S4.t2];
 App.pair={a,b,pin:{lat:S4.pin.lat,lng:S4.pin.lng,rad:S4.rad},name:S4.name};
 addFeed('<span class="tag c">STAGE</span><b>Analyst 01</b> locked pair '+a.id+' ↔ '+b.id+' · '+S4.name);
 toast('Pair locked — handing off to Change Analysis');
 go('analysis')}

/* ---- EXPLORER LOGIC ---- */
function explorePick(lat,lng){
 EXP.cur={lat,lng};
 const nr=nearestRegion(lat,lng);
 const h1=hash(Math.round(lat*500)+13,Math.round(lng*500)+29);
 const scenes=812+Math.floor(h1*4300);
 const tiles=Math.floor(scenes*(41+h1*23));
 const cloud=Math.round(9+h1*38);
 const days=2+Math.floor(h1*18);
 const row=(k,v)=>'<div class="ei-row"><span>'+k+'</span><b>'+v+'</b></div>';
 document.getElementById('eiT').textContent=Math.abs(lat).toFixed(4)+'°'+(lat>=0?'N':'S')+' · '+Math.abs(lng).toFixed(4)+'°'+(lng>=0?'E':'W');
 document.getElementById('eiM').textContent='nearest sector: '+(nr.r?nr.r.name:'open terrain')+' · '+nr.d.toFixed(1)+' km';
 document.getElementById('eiRows').innerHTML=
  row('Scenes in archive',scenes.toLocaleString('en-IN'))+
  row('Tiles indexed',tiles.toLocaleString('en-IN'))+
  row('Mean cloud cover',cloud+'%')+
  row('Last pass',days+' days ago');
 document.getElementById('exploreInfo').classList.add('on')}

function hideExploreInfo(){const c=document.getElementById('exploreInfo');if(c)c.classList.remove('on')}

function exploreToSearch(){
 if(!EXP.cur)return;
 const nr=nearestRegion(EXP.cur.lat,EXP.cur.lng);
 const sel=document.getElementById('fRegion');
 if(sel&&nr.r){sel.value=nr.r.id;S.region=nr.r.id}
 fillQ('recent activity near '+(nr.r?nr.r.name.split('—')[0].trim().toLowerCase():'this location'));
 hideExploreInfo();go('search');
 toast('Location prefilled — adjust filters and Run Semantic Search')}

function exploreToAnalysis(){
 if(!EXP.cur)return;
 scenePick(EXP.cur.lat,EXP.cur.lng);
 hideExploreInfo();go('scene');
 toast('AOI placed — query the archive to build the timeline')}

function registerAOI(){
 if(!EXP.cur){toast('Click the map to pick a location first');return}
 const lat=EXP.cur.lat,lng=EXP.cur.lng;
 const nr=nearestRegion(lat,lng);
 const base=nr.r?nr.r.name.split('—')[0].trim():'Sector';
 const id='aoi-'+String(AOIS.length+1).padStart(2,'0');
 const seed=1000+Math.floor(hash(Math.round(lat*1000),Math.round(lng*1000))*9000);
 const a={id,name:base+' — Watch '+(AOIS.length-4),lat:+lat.toFixed(3),lng:+lng.toFixed(3),rad:4,status:'low',seed,
  conf:70+Math.floor(hash(seed,7)*20),change:+(2+hash(seed,11)*8).toFixed(1),agree:'S2 ✓ · S1 ✓',
  quality:+(0.82+hash(seed,13)*.12).toFixed(2),cat:'Newly registered watch area — baseline building',
  t1:'2026-01-05',t2:'2026-09-10',passes:['2026-01-05','2026-03-01','2026-05-04','2026-07-06','2026-09-10']};
 AOIS.push(a);
 renderAoiList();
 needRender=true;
 EMAP.invalidate();
 addFeed('<span class="tag a">AOI</span><b>Analyst 01</b> registered <b>'+a.name+'</b> — r=4 km · '+a.lat+'°N '+a.lng+'°E');
 toast('AOI registered — live on Dashboard, Explorer & Scene maps','success');
 hideExploreInfo()}

/* ---- STAGING HOOKS ---- */
function applyStaged(){
 const b=document.getElementById('stagedBanner');if(!b)return;
 if(App.staged){
  const r=App.staged;
  b.innerHTML='⤵ Staged from Search — <b>'+r.id+'</b> · '+r.region+' · AOI pinned, archive query queued';
  b.classList.remove('hidden');
  scenePick(r.lat,r.lng,r.region);
  App.staged=null;
  setTimeout(queryArchive,400)}
 else if(App.stagedPair){
  const A=App.stagedPair[0],B=App.stagedPair[1];
  b.innerHTML='⤵ Pair staged from Compare — <b>'+A.id+'</b> ↔ <b>'+B.id+'</b> · pin at midpoint · pair reserved for detection';
  b.classList.remove('hidden');
  scenePick((A.lat+B.lat)/2,(A.lng+B.lng)/2,'Staged pair · '+(A.region||B.region))}
 else b.classList.add('hidden')}

const _goBase=go;
go=function(id){
 _goBase(id);
 if(id==='scene')applyStaged();
 if(id==='map')hideExploreInfo()};

function sendToAnalysis(i){
 const r=S.results[i];if(!r)return;
 if(!Number.isFinite(r.lat)||!Number.isFinite(r.lng)){toast('This result has no geographic coordinates; it cannot seed a scene query','error');return}
 App.staged=r;
 addFeed('<span class="tag c">STAGE</span><b>Analyst 01</b> staged scene '+r.id+' · '+r.region+' for multi-temporal analysis');
 toast('Tile location staged; querying the local scene catalog');
 go('scene')}

/* Phase 9: replace generated timeline/results with the actual local scene API. */
queryArchive=async function(){
 if(!S4.pin){toast('Place an AOI first by selecting a point on the map','error');return}
 if(S4.querying)return;
 S4.querying=true;
 const btn=document.getElementById('queryBtn');btn.disabled=true;
 btn.innerHTML='<span class="spinner"></span> Querying local catalog…';
 const progress=document.getElementById('qProg');
 progress.innerHTML='<div class="pstep run"><span class="pnum"><span class="spinner"></span></span><span>Searching local scene catalog…</span></div>';
 try{
  const response=await apiJson('/api/scenes/search',{lat:S4.pin.lat,lng:S4.pin.lng,
   radius_km:S4.rad,sensors:['sentinel-2','landsat']});
  S4.scenes=(response.items||[]).map(item=>{
   const sen=SENSORS.find(s=>s.id===(item.sensor==='sentinel-2'?'s2':'l8'))||{id:item.sensor,name:item.sensor,tag:item.sensor};
   return {...item,sceneId:item.id,date:item.date?new Date(item.date):null,cloud:item.cloud_percent,
    sensor:sen,localPath:item.local_path};
  }).sort((a,b)=>(a.date||0)-(b.date||0));
  if(SMAP&&SMAP.setScenes)SMAP.setScenes(S4.scenes);
  S4.t1=null;S4.t2=null;renderTimeline();renderPair();
  const nLocal=S4.scenes.filter(s=>s.available_locally&&s.localPath).length;
  const nPrototype=S4.scenes.filter(s=>s.record_type==='prototype_analysis_ready').length;
  const nArchive=response.count-nPrototype;
  document.getElementById('qCount').textContent=`${nArchive} archive records · ${nPrototype} prototype analysis-ready assets · ${nLocal} local rasters`;
  progress.innerHTML=response.count?'<div class="tip">Archive records and explicitly labeled local prototype assets are shown separately. No remote archive was queried.</div>':'<div class="tip">No scene records or prototype assets match this location.</div>';
  toast(`${response.count} local scene records found`,response.count?'success':'info');
 }catch(error){
  S4.scenes=[];renderTimeline();renderPair();
  progress.innerHTML=`<div class="tip" role="alert">${escapeHtml(apiError(error))}</div>`;
  document.getElementById('qCount').textContent='Local scene query failed';toast(apiError(error),'error');
 }finally{S4.querying=false;btn.disabled=false;btn.innerHTML=ARCH_BTN}
};

renderTimeline=function(){
 const box=document.getElementById('tlDots'),hint=document.getElementById('tlHint');
 const min=document.getElementById('tlMin'),max=document.getElementById('tlMax');
 const scenes=S4.scenes;
 if(!scenes.length){box.innerHTML='';min.textContent='—';max.textContent='—';
  hint.textContent=S4.pin?'No matching local scene records.':'Place an AOI and query the local scene catalog.';return}
 const dated=scenes.filter(s=>s.date&&!Number.isNaN(s.date.getTime()));
 if(!dated.length){box.innerHTML='';min.textContent='—';max.textContent='—';hint.textContent='Catalog records lack usable dates.';return}
 const t0=dated[0].date.getTime(),t1=dated[dated.length-1].date.getTime();
 min.textContent=dated[0].date.toLocaleDateString('en-IN',{month:'short',year:'numeric'});
 max.textContent=dated[dated.length-1].date.toLocaleDateString('en-IN',{month:'short',year:'numeric'});
 hint.textContent=`Select two observations. Violet offset markers are local prototype assets; others are archive records.`;
 box.innerHTML=scenes.map((s,i)=>{
  if(!s.date||Number.isNaN(s.date.getTime()))return '';
  const f=t1>t0?(s.date.getTime()-t0)/(t1-t0):.5;
  const cls=s.blocked?'dis':i===S4.t1?'t1':i===S4.t2?'t2':Number.isFinite(s.cloud)&&s.cloud>45?'c2':'c0';
  const prototype=s.record_type==='prototype_analysis_ready';
  const marker=prototype?'prototype':'';
  const title=prototype?`Prototype ${s.observation_role} · ${s.id}`:`Archive · ${s.id||s.sensor.tag}`;
  return `<span class="pdot ${cls} ${marker}" style="left:calc(10px + (100% - 20px)*${f.toFixed(3)})" title="${escapeHtml(title)} · ${s.date.toISOString().slice(0,10)} · ${escapeHtml(s.sensor.tag)} · ${s.available_locally?'local raster':'metadata only'}" onclick="pickScene(${i})"></span>`;
 }).join('');
};

explorePick=async function(lat,lng){
 EXP.cur={lat,lng};
 const title=document.getElementById('eiT');
 title.textContent=Math.abs(lat).toFixed(4)+'°'+(lat>=0?'N':'S')+' · '+Math.abs(lng).toFixed(4)+'°'+(lng>=0?'E':'W');
 document.getElementById('eiM').textContent='Selected coordinates · local offline basemap';
 const rows=document.getElementById('eiRows');rows.innerHTML='<div class="ei-row"><span>Local scene catalog</span><b>Querying…</b></div>';
 document.getElementById('exploreInfo').classList.add('on');
 try{
  const response=await apiJson('/api/scenes/search',{lat,lng,radius_km:4,sensors:['sentinel-2','landsat']});
  const dated=(response.items||[]).map(scene=>scene.date).filter(Boolean).sort();
  rows.innerHTML='<div class="ei-row"><span>Matching local scene records</span><b>'+response.count+'</b></div>'+ 
   '<div class="ei-row"><span>External catalog queried</span><b>No</b></div>'+ 
   '<div class="ei-row"><span>Latest catalog date</span><b>'+(dated.at(-1)||'Unavailable')+'</b></div>';
 }catch(error){rows.innerHTML='<div class="ei-row"><span>Catalog query</span><b>'+escapeHtml(apiError(error))+'</b></div>'}
};

exploreToSearch=function(){
 if(!EXP.cur)return;
 const {lat,lng}=EXP.cur;
 fillQ(`satellite imagery near ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
 S.region='all';const sel=document.getElementById('fRegion');if(sel)sel.value='all';
 hideExploreInfo();go('search');
 toast('Coordinate-based text prefill only; search endpoint has no region bbox from this canvas.');
};

renderPair=function(){
 const box=document.getElementById('pairBox'),btn=document.getElementById('runAnaBtn');
 if(S4.t1==null||S4.t2==null){box.innerHTML='<div class="pair-hint">Select two dated observations to inspect availability.</div>';btn.disabled=true;return}
 const a=S4.scenes[S4.t1],b=S4.scenes[S4.t2];
 if(a.record_type==='prototype_analysis_ready'||b.record_type==='prototype_analysis_ready'){
  if(a.record_type!=='prototype_analysis_ready'||b.record_type!=='prototype_analysis_ready'||a.observation_role!=='T1'||b.observation_role!=='T2'||a.pair_id!==b.pair_id){toast('Select the configured prototype T1 and T2 observations','error');return}
 }else if(a.date>b.date){toast('Archive observations must be supplied in chronological order','error');return}
 if(!a||!b||!a.date||!b.date){btn.disabled=true;return}
 const gap=Math.round((b.date-a.date)/864e5);
 const sameSensor=a.sensor.id===b.sensor.id;
 const ready=sameSensor&&a.sensor.id==='s2'&&a.available_locally&&b.available_locally&&a.localPath&&b.localPath;
 box.innerHTML=`<div class="pairrow"><div><div class="rtitle">T1 · ${escapeHtml(a.id||'Scene')}</div><div class="pair-m mono">${a.date.toISOString().slice(0,10)} · ${escapeHtml(a.sensor.name)} · ${a.available_locally?'local raster available':'no local raster'}</div></div></div>
  <div class="pairrow"><div><div class="rtitle">T2 · ${escapeHtml(b.id||'Scene')}</div><div class="pair-m mono">${b.date.toISOString().slice(0,10)} · ${escapeHtml(b.sensor.name)} · ${b.available_locally?'local raster available':'no local raster'}</div></div></div>
  <div class="pairrow" style="border:none"><span class="badge ${ready?'lo':'m'}">${ready?'READY FOR BIT ANALYSIS':'NOT ANALYZABLE WITH LOCAL INPUTS'}</span><span class="pair-gap" style="margin-left:auto">${gap} day gap</span></div>
  ${ready?'':'<div class="tip">The API requires two local Sentinel-2 raster paths. These selected catalog entries do not provide them.</div>'}`;
 btn.disabled=!ready;
};

runAna=function(){
 if(S4.t1==null||S4.t2==null)return;
 const a=S4.scenes[S4.t1],b=S4.scenes[S4.t2];
 if(!a.localPath||!b.localPath||a.sensor.id!=='s2'||b.sensor.id!=='s2')return;
 App.pair={a,b,pin:{lat:S4.pin.lat,lng:S4.pin.lng,rad:S4.rad},name:S4.name,aoiId:S4.aoiId||null};
 go('analysis');
};

registerAOI=async function(){
 if(!EXP.cur){toast('Select a location on the map first','error');return}
 const name=window.prompt('Name this AOI');if(!name||!name.trim())return;
 try{await apiJson('/api/aois',{name:name.trim(),lat:EXP.cur.lat,lng:EXP.cur.lng,radius_km:4});
  await loadApiDashboard();toast('AOI registered in the backend','success');hideExploreInfo();}
 catch(error){toast(apiError(error),'error')}
};

const _sceneGoPhase9=go;
go=function(id){_sceneGoPhase9(id);
 if(id==='scene'&&App.stagedAOI){const a=App.stagedAOI;scenePick(a.lat,a.lng,a.name);S4.rad=a.radius_km;S4.aoiId=a.id;
  SMAP.setPin({lat:a.lat,lng:a.lng,rad:a.radius_km});updateScenePanel();App.stagedAOI=null;}
};

/* ---- BOOT ---- */
injectScene();
injectExplore();
SMAP=makeMap({view:'scene',body:'sceneMapBody',lat:22.7774,lng:75.8247,z:9,pins:[],onPick:scenePick,onPinHit:snapPin,coordsEl:'scCoords',gsdEl:'scGsd'});
EMAP=makeMap({view:'map',body:'exploreMapBody',lat:22.7774,lng:75.8247,z:9,layers:{density:false},pins:[],blobs:[],onPick:explorePick,onPinHit:a=>{openInv(a.id)},coordsEl:'exCoords',gsdEl:'exGsd'});
window.AvlokanMaps={scene:SMAP,explorer:EMAP};
