/* ==========================================================================
   AVLOKAN - Phase 2: Semantic Search Console & Tile Lightbox
   ========================================================================== */

/* ================= PHASE 2 · SEARCH CONSOLE ================= */
const IC={
 search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
 type:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/></svg>',
 img:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>',
 up:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg>',
 filter:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></svg>',
 cpu:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3m6-3v3M9 20v3m6-3v3M1 9h3m-3 6h3m16-6h3m-3 6h3"/></svg>',
 db:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
 clock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
 bulb:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.4 1 2.3h6c0-.9.4-1.8 1-2.3A7 7 0 0 0 12 2z"/></svg>'};

const REGIONS=[
 {id:'all',name:'All India — archive-wide',lat:22.8,lng:79.6,jit:9},
 {id:'mumbai',name:'Mumbai — Docks & Coast',lat:18.955,lng:72.842,jit:.35},
 {id:'delhi',name:'Delhi NCR',lat:28.61,lng:77.21,jit:.35},
 {id:'chennai',name:'Chennai — Industrial Belt',lat:13.082,lng:80.27,jit:.35},
 {id:'ladakh',name:'Ladakh — Forward Sector',lat:34.15,lng:77.58,jit:.6},
 {id:'indore',name:'Indore — AVLOKAN Prototype AOI',lat:22.77736,lng:75.82474,jit:.04},
 {id:'bhadla',name:'Bhadla — Solar Park',lat:27.541,lng:71.905,jit:.4},
 {id:'ranchi',name:'Ranchi — Jharkhand',lat:23.35,lng:85.3,jit:.4}];

const SENSORS=[
 {id:'s2',name:'Sentinel-2',tag:'S2',cls:'s2',col:'#5b8c89',prefix:'S2B',gsd:'10 m'},
 {id:'s1',name:'Sentinel-1 SAR',tag:'S1',cls:'s1',col:'#6f5a77',prefix:'S1A',gsd:'10 m'},
 {id:'l8',name:'Landsat C2',tag:'L8',cls:'l8',col:'#96701d',prefix:'LC08',gsd:'30 m'},
 {id:'bh',name:'Bhuvan / ISRO',tag:'BH',cls:'bh',col:'#9c6244',prefix:'BHV',gsd:'—'}];

const EXQ=[
 ['new port construction near Mumbai docks','port construction'],
 ['deforestation clearing in Western Ghats','deforestation'],
 ['flooded agricultural fields Punjab','flooded fields'],
 ['infrastructure buildup along LAC high altitude','LAC buildup'],
 ['expanding industrial sheds Chennai outskirts','industrial expansion']];

const S={mode:'text',img:null,file:null,demoScene:null,region:'all',sensors:{s2:true,s1:true,l8:true,bh:false},
 from:'',to:'',cloud:40,minSim:.0,topK:24,running:false,recent:[],results:[]};

function injectSearch(){
 S.from='';
 S.to='';
 const regionOpts=REGIONS.map(r=>`<option value="${r.id}"${r.id==='all'?' selected':''}>${r.name}</option>`).join('');
 const sensorChips=SENSORS.map(s=>`<span class="schip ${s.cls}${S.sensors[s.id]?' on':''}" id="sc-${s.id}" onclick="toggleSensor('${s.id}')"><span class="sdot"></span>${s.name}</span>`).join('');
 const exChips=EXQ.map(e=>`<span class="qchip" onclick="fillQ('${e[0]}')">${e[1]}</span>`).join('');
 document.getElementById('view-search').innerHTML=`
 <div class="flowstrip">${flowStrip('search')}</div>
 <div class="search-layout">
  <div>
   <div class="panel" style="margin-bottom:16px">
    <div class="panel-h">${IC.search} Semantic Query <span class="mh-sub">RemoteCLIP ViT-B/32 · shared 512-d embedding space</span></div>
    <div class="panel-b">
     <div class="mode-tabs">
      <span class="mode-tab on" id="mt-text" onclick="setQMode('text')">${IC.type} Text Query</span>
      <span class="mode-tab" id="mt-image" onclick="setQMode('image')">${IC.img} Image Query</span>
     </div>
     <div id="qm-text">
      <div class="field"><label>Free-text query <span>text → image · zero-shot</span></label>
       <textarea id="qText" class="search-input" placeholder="Search the archive by meaning… e.g. new construction near Mumbai docks"></textarea></div>
      <div style="font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:var(--faint);font-weight:800;margin-bottom:8px">Try an example</div>
      <div class="ex-queries">${exChips}</div>
      <div class="ex-queries"><span id="demoQueryChip" class="qchip" onclick="fillQ('Newly constructed buildings and infrastructure development')">Newly constructed buildings and infrastructure development</span></div>
     </div>
     <div id="qm-image" class="hidden">
      <div style="font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--text);margin-bottom:12px">IMAGE-TO-IMAGE RETRIEVAL</div>
      <div class="field">
       <label>Upload Satellite Image <span>.tif, .tiff, .png, .jpg, .jpeg</span></label>
       <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
        <label for="fileIn" class="btn btn-ghost" style="width:auto;cursor:pointer;display:inline-flex;align-items:center;gap:8px">
         ${IC.up} Choose File
        </label>
        <input type="file" id="fileIn" accept=".tif,.tiff,.png,.jpg,.jpeg,image/tiff,image/png,image/jpeg" style="display:none" onchange="if(this.files[0])onQFile(this.files[0])">
        <button type="button" class="btn btn-ghost" id="btnClearImage" style="width:auto;font-size:11px" onclick="clearQImage()" disabled>Clear</button>
       </div>
       <div id="imgPreviewWrapper" style="display:none">
        <img id="imgPreview" alt="query satellite tile preview" style="display:none">
       </div>
       <div id="imgSelectedBox" style="margin:10px 0;font-size:12px;color:var(--muted);display:none">
        <div style="font-size:10px;letter-spacing:1.2px;text-transform:uppercase;color:var(--faint);font-weight:800;margin-bottom:3px">Selected:</div>
        <div id="imgSelectedName" class="mono" style="font-size:13px;font-weight:700;color:var(--text)">None</div>
       </div>
       <div style="margin-top:14px">
        </button>
       </div>
      </div>
     </div>
    </div>
   </div>
   <div class="panel" style="margin-bottom:16px">
    <div class="panel-h">${IC.filter} Filters <span class="mh-sub">post-FAISS metadata filtering</span></div>
    <div class="panel-b">
     <div class="fgrid">
      <div class="field"><label>Location</label><select class="fsel" id="fRegion" onchange="S.region=this.value">${regionOpts}</select></div>
      <div class="field"><label>Top-K results</label><select class="fsel" id="fTopK" onchange="S.topK=+this.value"><option value="12">12</option><option value="24" selected>24</option><option value="48">48</option></select></div>
      <div class="field"><label>Date from</label><input type="date" class="finput" id="fFrom" value="${S.from}" onchange="S.from=this.value"></div>
      <div class="field"><label>Date to</label><input type="date" class="finput" id="fTo" value="${S.to}" onchange="S.to=this.value"></div>
     </div>
     <div class="preset-row">
      <span class="qchip" onclick="setDatePreset(0.5)">Last 6 months</span>
      <span class="qchip" onclick="setDatePreset(1)">1 year</span>
      <span class="qchip" onclick="setDatePreset(3)">3 years</span>
      <span class="qchip" onclick="setDatePreset(5)">5 years</span>
     </div>
     <div class="field" style="margin-top:14px"><label>Sensors</label><div class="sensor-row">${sensorChips}</div></div>
     <div class="fgrid" style="margin-top:4px">
      <div class="field"><label>Max cloud cover · <span class="fval" id="cloudVal">40%</span></label>
       <input type="range" class="frange" id="fCloud" min="0" max="100" value="40" oninput="S.cloud=+this.value;document.getElementById('cloudVal').textContent=this.value+'%'"></div>
      <div class="field"><label>Min similarity · <span class="fval" id="simVal">0</span></label>
       <input type="range" class="frange" id="fSim" min="30" max="95" value="0" oninput="S.minSim=this.value/100;document.getElementById('simVal').textContent=(this.value/100).toFixed(2)"></div>
     </div>
    </div>
   </div>
   <div class="runbar">
    <button class="btn btn-primary" style="width:auto" id="runBtn" onclick="runSearch()">${IC.search} Run Semantic Search</button>
    <button class="btn btn-ghost" style="width:auto" onclick="resetSearch()">Reset</button>
    <span style="font-size:11px;color:var(--faint)">Retrieval runs server-side over the configured local index.</span>
   </div>
   <div class="panel progress-panel hidden" id="progPanel">
    <div class="panel-h">${IC.cpu} Retrieval Pipeline</div>
    <div class="panel-b" id="progSteps"></div>
   </div>
  </div>
  <div>
   <div class="panel" style="margin-bottom:16px" id="incrementalIndexPanel">
    <div class="panel-h" style="display:flex;justify-content:space-between;align-items:center">
     <span>${IC.db} Incremental Index (FAISS)</span>
     <span class="sensor-badge available" id="idxBadge">READY</span>
    </div>
    <div class="panel-b">
     <div class="srow"><span class="sk">Index Architecture</span><span class="sv c">FAISS IndexIDMap2 · 512-d</span></div>
     <div class="srow"><span class="sk">Indexed Scenes</span><span class="sv g mono" id="idxCountDisplay">4 scenes</span></div>
     <div class="srow"><span class="sk">Staged Scene</span><span class="sv mono" style="font-size:10px" id="stagedSceneDisplay">s2_20250324__tile_000000</span></div>
     <div class="srow"><span class="sk">Index Strategy</span><span class="sv a">In-place vector append (No full rebuild)</span></div>
     <div id="idxResultNotice" style="margin-top:8px;font-size:11px;color:var(--muted);line-height:1.4">Staged Sentinel-2 L2A tile ready for incremental embedding and ingestion.</div>
     <div style="display:flex;gap:6px;margin-top:12px;flex-wrap:wrap">
      <button type="button" class="btn btn-primary" id="btnIngestScene" style="flex:1;min-width:110px;padding:6px 10px;font-size:11px" onclick="triggerIncrementalIngest()">+ Add Scene to Index</button>
      <button type="button" class="btn btn-ghost" id="btnSearchIngested" style="padding:6px 10px;font-size:11px" onclick="searchIngestedScene()" title="Search for the newly ingested scene">🔍 Find Ingested</button>
      <button type="button" class="btn btn-ghost" style="padding:6px 10px;font-size:11px" onclick="triggerIndexReset()" title="Reset index to baseline 4 scenes">↺ Reset</button>
     </div>
    </div>
   </div>
   <div class="panel" style="margin-bottom:16px">
    <div class="panel-h">${IC.clock} Recent Queries</div>
    <div class="panel-b recent-q" id="recentQ"><div class="tip">No queries this session yet — your searches will appear here.</div></div>
   </div>
   <div class="panel">
    <div class="panel-h">${IC.bulb} Search Tips</div>
    <div class="panel-b">
     <div class="tip"><b>Be spatial.</b> "quarry near a river bend" outperforms "mining".</div>
     <div class="tip"><b>Name the season.</b> "post-monsoon flooded fields" disambiguates terrain states.</div>
     <div class="tip"><b>Image queries</b> surface lookalike tiles — one confirmed site finds similar sites archive-wide.</div>
     <div class="tip"><b>SAR tiles</b> match structure, not color — pair S1 with optical for sensor agreement.</div>
    </div>
   </div>
  </div>
 </div>`;if(window.DemoMode)DemoMode.syncControls();refreshIndexingStatus()}

function setQMode(m){S.mode=m;
 document.getElementById('mt-text')?.classList.toggle('on',m==='text');
 document.getElementById('mt-image')?.classList.toggle('on',m==='image');
 document.getElementById('qm-text')?.classList.toggle('hidden',m!=='text');
 document.getElementById('qm-image')?.classList.toggle('hidden',m!=='image');
 updateRunButtonState()}

function updateImageQueryState(){
 const btn=document.getElementById('btnSearchByImage');
 if(btn)btn.disabled=!S.file;
 const clr=document.getElementById('btnClearImage');
 if(clr)clr.disabled=!S.file;
 updateRunButtonState()}

function updateRunButtonState(){
 const runBtn=document.getElementById('runBtn');
 if(!runBtn)return;
 if(S.mode==='image'){
  runBtn.innerHTML=IC.search+' Search by Image';
  runBtn.disabled=!S.file;
 }else{
  runBtn.innerHTML=RUN_HTML;
  runBtn.disabled=false;
 }}

function fillQ(q){document.getElementById('qText').value=q}

async function onQFile(f){
 if(!f)return;
 const allowed=/\.(png|jpe?g|webp|tiff?)$/i.test(f.name||'');
 if(!allowed){toast('Choose a PNG, JPEG, WebP, or GeoTIFF file (.png, .jpg, .jpeg, .tif, .tiff)','error');return}
 if(f.size<1||f.size>20*1024*1024){toast('Image file must be no larger than 20 MiB','error');return}
 clearQImage();
 S.file=f;
 const p=document.getElementById('imgPreview');
 const pw=document.getElementById('imgPreviewWrapper');
 const sb=document.getElementById('imgSelectedBox');
 const sn=document.getElementById('imgSelectedName');
 if(sn)sn.textContent=f.name;
 if(sb)sb.style.display='block';

 if(/\.tiff?$/i.test(f.name||'')){
  try{
   const form=new FormData();
   form.append('file',f,f.name);
   const res=await apiRequest('/api/preview/upload',{method:'POST',body:form});
   const blob=await res.blob();
   if(S.img&&S.img.startsWith('blob:'))URL.revokeObjectURL(S.img);
   S.img=URL.createObjectURL(blob);
   if(p){p.src=S.img;p.style.display='block'}
   if(pw)pw.style.display='block';
   toast('GeoTIFF preview rendered locally','success');
  }catch(err){
   if(p)p.style.display='none';
   if(pw)pw.style.display='none';
   toast('GeoTIFF preview unavailable; file will still be processed by backend','info');
  }
 }else{
  if(S.img&&S.img.startsWith('blob:'))URL.revokeObjectURL(S.img);
  S.img=URL.createObjectURL(f);
  if(p){p.src=S.img;p.style.display='block'}
  if(pw)pw.style.display='block';
  toast('Image selected: '+f.name,'success');
 }
 updateImageQueryState();
}

function useSampleTile(){
 toast('Image search requires a real image file; generated demo tiles are not sent to the backend','error')}

function clearQImage(){
 if(S.img&&S.img.startsWith('blob:'))URL.revokeObjectURL(S.img);
 S.img=null;S.file=null;S.demoScene=null;
 const p=document.getElementById('imgPreview');if(p){p.style.display='none';p.src=''}
 const pw=document.getElementById('imgPreviewWrapper');if(pw)pw.style.display='none';
 const sb=document.getElementById('imgSelectedBox');if(sb)sb.style.display='none';
 const sn=document.getElementById('imgSelectedName');if(sn)sn.textContent='None';
 const input=document.getElementById('fileIn');if(input)input.value='';
 updateImageQueryState();
}

function selectDemoImage(){}

function setDatePreset(y){
 S.from=new Date(Date.now()-y*365*864e5).toISOString().slice(0,10);
 S.to=new Date().toISOString().slice(0,10);
 document.getElementById('fFrom').value=S.from;
 document.getElementById('fTo').value=S.to}

function toggleSensor(id){
 S.sensors[id]=!S.sensors[id];
 document.getElementById('sc-'+id).classList.toggle('on',S.sensors[id])}

function resetSearch(){
 document.getElementById('qText').value='';clearQImage();
 S.region='all';document.getElementById('fRegion').value='all';
 S.sensors={s2:true,s1:true,l8:true,bh:false};
 SENSORS.forEach(s=>document.getElementById('sc-'+s.id).classList.toggle('on',S.sensors[s.id]));
 S.from='';S.to='';
 const fFrom=document.getElementById('fFrom'),fTo=document.getElementById('fTo');
 if(fFrom)fFrom.value='';if(fTo)fTo.value='';
 S.cloud=40;document.getElementById('fCloud').value=40;document.getElementById('cloudVal').textContent='40%';
 S.minSim=0;document.getElementById('fSim').value=0;document.getElementById('simVal').textContent='0.00';
 S.topK=24;document.getElementById('fTopK').value='24';
 S.qf={s2:true,s1:true,l8:true,bh:true};
 toast('Filters reset to defaults')}

function normalizeSensor(raw){
 if(!raw)return SENSORS[0];
 const rawStr=(typeof raw==='object'?(raw.id||raw.tag||raw.name||''):String(raw)).trim().toLowerCase();
 const rawTag=(typeof raw==='object'&&raw.tag?String(raw.tag):'').trim().toLowerCase();
 const rawName=(typeof raw==='object'&&raw.name?String(raw.name):'').trim().toLowerCase();
 const def=SENSORS.find(s=>
  s.id===rawStr||s.tag.toLowerCase()===rawStr||s.tag.toLowerCase()===rawTag||
  s.name.toLowerCase()===rawStr||s.name.toLowerCase()===rawName||
  (s.id==='s2'&&(rawStr.includes('sentinel-2')||rawStr==='s2'||rawName.includes('sentinel-2')))||
  (s.id==='s1'&&(rawStr.includes('sentinel-1')||rawStr==='s1'||rawName.includes('sentinel-1')))||
  (s.id==='l8'&&(rawStr.includes('landsat')||rawStr==='l8'||rawName.includes('landsat')))||
  (s.id==='bh'&&(rawStr.includes('bhuvan')||rawStr==='bh'||rawName.includes('bhuvan')))
 )||SENSORS[0];
 return {...def,...(typeof raw==='object'?raw:{}),id:def.id,tag:def.tag,name:def.name,col:def.col,cls:def.cls};
}

const RUN_HTML=IC.search+' Run Semantic Search';
async function runSearch(){
 if(S.running)return;
 const q=document.getElementById('qText').value.trim();
 if(S.mode==='text'&&q.length<3){toast('Enter a query of at least 3 characters');return}
 if(S.mode==='image'&&!S.file){toast('Choose a satellite image file first (.png, .jpg, .tif)','error');return}
 if(!Object.values(S.sensors).some(v=>v)){toast('Select at least one sensor');return}
 S.running=true;
 const btn=document.getElementById('runBtn');
 const imgBtn=document.getElementById('btnSearchByImage');
 if(btn){btn.disabled=true;btn.innerHTML='<span class="spinner"></span> Searching archive…'}
 if(imgBtn){imgBtn.disabled=true;imgBtn.innerHTML='<span class="spinner"></span> Searching archive…'}
 const label=S.mode==='text'?'“'+q+'”':'image: '+(S.file?S.file.name:'uploaded image');
 document.getElementById('progPanel').classList.remove('hidden');
 document.getElementById('progSteps').innerHTML='<div class="pstep run"><span class="pnum"><span class="spinner"></span></span><span>Searching the local AVLOKAN index…</span><span class="pms"></span></div>';
 try{
  const payload={sensors:SENSORS.filter(s=>S.sensors[s.id]).map(s=>s.id),top_k:S.topK,
   date_from:S.from||null,date_to:S.to||null,max_cloud:S.cloud,min_similarity:S.minSim};
  let response;
  if(S.mode==='image'){
   const form=new FormData();form.append('file',S.file,S.file.name);
   Object.entries(payload).forEach(([k,v])=>{if(v!==null)form.append(k,Array.isArray(v)?v.join(','):String(v))});
   response=await apiRequest('/api/search/image',{method:'POST',body:form});
  }else if(window.DemoMode&&DemoMode.enabled){
   const demoBody={sensors:SENSORS.filter(s=>S.sensors[s.id]).map(s=>s.id),top_k:S.topK,date_from:S.from||null,date_to:S.to||null,
    region:S.region,max_cloud:S.cloud,min_similarity:S.minSim,query:q};
   response=await DemoMode.search('text',demoBody);
  }else{
   response=await apiJson('/api/search/text',{...payload,query:q});
  }
  S.results=(response.results||[]).map((r,i)=>{
   return {...r,_api:true,_rank:r.rank||i+1,date:r.date?new Date(r.date):null,
    sensor:normalizeSensor(r.sensor),thumbnail_url:apiAsset(r.thumbnail_url),_demo:response.query_type==='demo-prepared',
    region:r.region||'Local archive'};
  });
  S.searchWarnings=response.warnings||[];S.searchTimings=response.timings||{};
  if(window.BackendHealth)renderSearchIndexStatus(window.BackendHealth,S.searchTimings);
  S.searchError=null;
  if(S.region!=='all')S.searchWarnings.push('The selected named region is a demo UI filter; the API has no corresponding named-region boundary, so it was not applied.');
  const total=S.searchTimings.total_ms;
  renderResults(label);
  addFeed('<span class="tag c">SEARCH</span>Backend '+response.query_type+' search returned '+S.results.length+' local results');
  pushRecent(label);go('results');
  toast(S.results.length+' backend results'+(total!=null?' · '+total+' ms':''),S.results.length?'success':'info');
 }catch(error){
  S.searchError=apiError(error);S.results=[];renderResults(label);
  document.getElementById('progSteps').innerHTML='<div class="tip" role="alert">'+escapeHtml(S.searchError)+'</div>';
  toast(S.searchError,'error');
 }finally{
  S.running=false;
  if(btn){btn.disabled=false;updateRunButtonState()}
  if(imgBtn)imgBtn.disabled=!S.file;
 }
}

function escapeHtml(value){const node=document.createElement('span');node.textContent=String(value??'');return node.innerHTML}

function detectFeature(q){
 const s=(q||'').toLowerCase();
 if(/port|dock|berth|construct|build|infra|road/.test(s))return['urban','mixed'];
 if(/forest|deforest|clear|timber/.test(s))return['forest','forest'];
 if(/flood|water|inund|river|lake/.test(s))return['water','mixed'];
 if(/solar|industr|panel|plant|shed/.test(s))return['industrial','mixed'];
 return['mixed','urban']}

function genResults(label){
 const q=document.getElementById('qText').value.trim();
 const seedBase=[...label].reduce((a,c)=>a+c.charCodeAt(0)*7,13);
 const active=SENSORS.filter(s=>S.sensors[s.id]);
 let t0=Date.parse(S.from)||Date.parse('2025-01-01');
 let t1=Date.parse(S.to)||Date.now();
 if(t1<t0){const tmp=t0;t0=t1;t1=tmp}
 const feats=detectFeature(S.mode==='text'?q:'construction site');
 const reg=REGIONS.find(r=>r.id===S.region)||REGIONS[0];
 const n=Math.min(S.topK,48);
 S.results=[];
 for(let i=0;i<n;i++){
  const rr=reg.id==='all'?REGIONS[1+Math.floor(hash(seedBase+i*7,i*13)*(REGIONS.length-1))]:reg;
  const lat=rr.lat+(hash(seedBase+i*3,i*11)-.5)*2*rr.jit;
  const lng=rr.lng+(hash(seedBase+i*5,i*13)-.5)*2*rr.jit;
  const dt=new Date(t0+hash(seedBase+i,i*17)*(t1-t0));
  const sen=active[Math.floor(hash(seedBase+i*9,i*19)*active.length)];
  const sim=.94-i*(.36/n)-hash(seedBase+i,i*23)*.05;
  if(sim<S.minSim)continue;
  S.results.push({
   id:sen.prefix+'_'+dt.toISOString().slice(0,10).replace(/-/g,'')+'_T'+(10000+Math.floor(hash(i,seedBase)*89999)),
   lat,lng,region:rr.name,date:dt,sensor:sen,sim,
   cloud:Math.round(hash(seedBase+i*2,i*29)*S.cloud),
   seed:Math.floor(hash(seedBase+i*31,i*37)*1e6),
   feature:feats[Math.floor(hash(seedBase+i*11,i*41)*feats.length)]})}
 renderResults(label)}

function drawThumb(cv,seed,feature){
 const x=cv.getContext('2d'),w=cv.width,h=cv.height;
 const cell=Math.max(3,Math.round(w/90));
 for(let py=0;py<h;py+=cell)for(let px=0;px<w;px+=cell){
  const e=fbm(px/(w/9)+seed%97,py/(h/7)+seed%53);
  const m=fbm(px/(w/5)+seed%31+50,py/(h/4)+seed%17);
  let col;
  if(feature==='water')col=e<.52?TER.deep:e<.60?TER.water:e<.64?TER.grass:TER.arid;
  else if(feature==='forest')col=e<.40?TER.water:e<.44?TER.sand:(m>.40?TER.forest:TER.grass);
  else col=e<.33?TER.deep:e<.395?TER.water:e<.43?TER.sand:(m>.62?TER.forest:m>.46?TER.grass:TER.arid);
  x.fillStyle=col;x.fillRect(px,py,cell,cell)}
 x.strokeStyle=TER.water;x.lineWidth=Math.max(2,w*.01);x.beginPath();
 for(let px=0;px<=w;px+=6){const py=h*.6+Math.sin(px/w*5.1+seed%10)*h*.14;px===0?x.moveTo(px,py):x.lineTo(px,py)}
 x.stroke();
 x.strokeStyle='#d8cdb2';x.lineWidth=Math.max(1.5,w*.006);x.beginPath();
 for(let px=0;px<=w;px+=6){const py=h*.28+Math.sin(px/w*3.7+seed%7)*h*.09;px===0?x.moveTo(px,py):x.lineTo(px,py)}
 x.stroke();
 const R=k=>hash(seed+k*13,seed+k*7);
 if(feature==='urban'||feature==='mixed'){
  const n=feature==='urban'?14:6;
  for(let i=0;i<n;i++){
   const bw=w*.05+R(i)*w*.09,bh=h*.05+R(i+40)*h*.08;
   const bx=w*.1+R(i+80)*w*.7,by=h*.15+R(i+120)*h*.55;
   x.fillStyle='rgba(64,58,44,.18)';x.fillRect(bx+2,by+2,bw,bh);
   x.fillStyle='#cfc3ae';x.fillRect(bx,by,bw,bh);
   x.strokeStyle='rgba(64,58,44,.35)';x.lineWidth=1;x.strokeRect(bx,by,bw,bh)}}
 if(feature==='forest'){
  for(let i=0;i<5;i++){
   const cw=w*.08+R(i)*w*.1,ch=h*.1+R(i+60)*h*.12;
   const cx=w*.08+R(i+90)*w*.75,cy=h*.12+R(i+130)*h*.6;
   x.fillStyle='rgba(163,132,90,.55)';x.fillRect(cx,cy,cw,ch);
   x.strokeStyle='rgba(78,107,79,.7)';x.lineWidth=1.5;x.strokeRect(cx,cy,cw,ch)}}
 if(feature==='industrial'||feature==='mixed'){
  const n=feature==='industrial'?3:1;
  for(let i=0;i<n;i++){
   const sw=w*.16+R(i)*w*.12,sh=h*.1+R(i+70)*h*.06;
   const sx=w*.12+R(i+100)*w*.5,sy=h*.2+R(i+140)*h*.5;
   x.fillStyle='rgba(64,58,44,.15)';x.fillRect(sx+2,sy+2,sw,sh);
   x.fillStyle='#d9d0bb';x.fillRect(sx,sy,sw,sh);
   x.strokeStyle='rgba(64,58,44,.3)';x.strokeRect(sx,sy,sw,sh);
   x.strokeStyle='rgba(123,166,163,.5)';
   for(let yy=sy+4;yy<sy+sh-3;yy+=5){x.beginPath();x.moveTo(sx+3,yy);x.lineTo(sx+sw-3,yy);x.stroke()}}}
 if(feature==='water'){
  x.fillStyle='rgba(123,166,163,.35)';
  for(let i=0;i<6;i++){const fx=w*.1+R(i)*w*.7,fy=h*.45+R(i+50)*h*.4,fr=w*.04+R(i+90)*w*.05;
   x.beginPath();x.arc(fx,fy,fr,0,7);x.fill()}}
 x.fillStyle='rgba(64,58,44,.55)';x.fillRect(8,h-14,Math.round(w*.14),3);
 x.fillStyle='rgba(64,58,44,.75)';x.font='700 '+Math.round(w*.028)+'px ui-monospace,monospace';
 x.fillText('1 km',8,h-18)}

function renderResults(label){
 const active=SENSORS.filter(s=>S.sensors[s.id]).map(s=>s.tag).join(' · ');
 const el=document.getElementById('view-results');
 el.innerHTML=`
  <div class="flowstrip">${flowStrip('results')}</div>
  <div class="res-head">
   <div>
    <div class="res-q">Results — ${label}</div>
    <div class="res-meta mono">${S.results.length} tiles · sensors ${active} · ${S.from} → ${S.to} · cloud ≤ ${S.cloud}% · sim ≥ ${S.minSim.toFixed(2)} · ${REGIONS.find(r=>r.id===S.region).name}</div>
   </div>
   <button class="btn btn-ghost" style="width:auto" onclick="go('search')">← Refine Search</button>
  </div>
  <div class="rgrid" id="rgrid"></div>`;
 const grid=document.getElementById('rgrid');
 S.results.forEach((r,i)=>{
  const card=document.createElement('div');card.className='rcard';
  card.innerHTML=`
   <div class="rthumb"><canvas width="320" height="200"></canvas>
    <span class="rsen" style="color:${r.sensor.col}">${r.sensor.tag}</span>
    <span class="rsim">${(r.sim*100).toFixed(1)}%</span></div>
   <div class="rbody">
    <div class="rtitle">${r.region}</div>
    <div class="rmeta mono">${r.id}<br>${r.date.toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})} · ${Math.abs(r.lat).toFixed(3)}°${r.lat>=0?'N':'S'} ${Math.abs(r.lng).toFixed(3)}°${r.lng>=0?'E':'W'} · cloud ${r.cloud}%</div>
    <div class="simbar"><i style="width:${(r.sim*100).toFixed(1)}%"></i></div>
    <div class="rbtns">
     <span class="rbtn pri" onclick="viewRes(${i})">View</span>
     <span class="rbtn" onclick="toast('Compare mode ships in Phase 3 — Search Results')">Compare</span>
     <span class="rbtn" onclick="sendToAnalysis(${i})">Analyze →</span>
    </div>
   </div>`;
  drawThumb(card.querySelector('canvas'),r.seed,r.feature);
  grid.appendChild(card)})}

/* ================= TILE LIGHTBOX ================= */
let curTile=null;

function viewRes(i){
 const r=S.results[i];if(!r)return;
 curTile=i;
 document.getElementById('tileBigTitle').textContent=r.region+' — '+r.id;
 const canvas=document.getElementById('tileBigCv');
 if(r._api){const image=new Image();image.onload=()=>{const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height)};image.onerror=()=>canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);image.src=r.thumbnail_url}
 else drawThumb(canvas,r.seed,r.feature);
 document.getElementById('tileBigMeta').innerHTML=
  '<div><div class="tk">Scene ID</div><div class="tv mono">'+r.id+'</div></div>'+
  '<div><div class="tk">Sensor</div><div class="tv" style="color:'+r.sensor.col+'">'+r.sensor.name+' · '+r.sensor.gsd+'</div></div>'+
  '<div><div class="tk">Acquired</div><div class="tv">'+(r.date&&!Number.isNaN(r.date.getTime())?r.date.toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):'Unavailable')+'</div></div>'+
  '<div><div class="tk">Location</div><div class="tv">'+(Number.isFinite(r.lat)&&Number.isFinite(r.lng)?Math.abs(r.lat).toFixed(4)+'°'+(r.lat>=0?'N':'S')+' '+Math.abs(r.lng).toFixed(4)+'°'+(r.lng>=0?'E':'W'):'Unavailable')+'</div></div>'+
  '<div><div class="tk">'+(r._demo?'Prepared demo rank':'Similarity')+'</div><div class="tv" style="color:var(--cyan-d)">'+(r._demo?'DEMO SIMULATED · not RemoteCLIP score':r.sim+' · retrieval similarity, not confidence')+'</div></div>'+
  '<div><div class="tk">Cloud Cover</div><div class="tv">'+(Number.isFinite(r.cloud)?r.cloud+'%':'Unknown')+'</div></div>';
 document.getElementById('tileOverlay').classList.remove('hidden')}

function closeTile(){document.getElementById('tileOverlay').classList.add('hidden')}

function sendToAnalysis(i){
 const r=S.results[i];if(!r)return;
 if(r._demo&&window.DemoMode&&DemoMode.enabled){DemoMode.openInvestigation(r);return}
 App.staged=r;
 addFeed('<span class="tag c">STAGE</span><b>Analyst 01</b> staged scene '+r.id+' · '+r.region+' for multi-temporal analysis');
 if(!Number.isFinite(r.lat)||!Number.isFinite(r.lng)){toast('This tile has no geographic coordinates; it cannot seed an AOI query','error');return}
 toast('Tile location staged. Query the local scene catalog for real observations.');
 go('scene')}

function showDemoOnMap(i){const r=S.results[i];if(!r)return;App.staged=r;window.AvlokanMaps?.scene?.setSelectedResult?.(r);go('scene')}

function sendToAnalysisFromTile(){const i=curTile;closeTile();if(i!=null)sendToAnalysis(i)}

function pushRecent(label){
 S.recent.unshift({
  q:S.mode==='text'?document.getElementById('qText').value.trim():label,
  mode:S.mode,n:S.results.length,t:istTime(),
  img:S.mode==='image'?S.img:null,scene:S.mode==='image'?S.demoScene:null});
 if(S.recent.length>6)S.recent.pop();
 renderRecent()}

function renderRecent(){
 const el=document.getElementById('recentQ');if(!el)return;
 if(!S.recent.length){el.innerHTML='<div class="tip">No queries this session yet — your searches will appear here.</div>';return}
 el.innerHTML=S.recent.map((r,i)=>`
  <div class="rq-row" onclick="rerunRecent(${i})">
   <div class="rq-t"><span class="tag ${r.mode==='text'?'c':'a'}" style="margin-right:6px">${r.mode==='text'?'TXT':'IMG'}</span>${r.q}</div>
   <div class="rq-m mono">${r.t} · ${r.n} results · ${r.mode==='text'?'text → image':'image → image'}</div>
  </div>`).join('')}

function rerunRecent(i){
 const r=S.recent[i];if(!r)return;
 setQMode(r.mode);
 if(r.mode==='text')fillQ(r.q);
 else if(window.DemoMode&&DemoMode.enabled&&r.scene){selectDemoImage()}
 else {toast('Select the image file again to repeat image search');return}
 runSearch()}

function injectTileLightbox(){
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
   <button class="btn btn-ghost" style="width:auto" onclick="toast('Compare mode ships in Phase 3 — Search Results')">Compare</button>
   <button class="btn btn-ghost" style="width:auto;margin-left:auto" onclick="closeTile()">Close</button>
  </div>
 </div>`;
 document.body.appendChild(o)}


async function refreshIndexingStatus() {
 try {
  const res = window.DemoMode?.getIndexingStatus ? await DemoMode.getIndexingStatus() : await apiRequest('/api/demo/indexing/status');
  const countEl = document.getElementById('idxCountDisplay');
  const noticeEl = document.getElementById('idxResultNotice');
  const btn = document.getElementById('btnIngestScene');
  const badge = document.getElementById('idxBadge');
  if (countEl) countEl.textContent = `${res.indexed_count} scenes (${res.catalog_count} catalog tiles)`;
  if (res.staged_scene && res.staged_scene.is_indexed) {
   if (badge) { badge.textContent = 'INGESTED'; badge.className = 'sensor-badge available'; }
   if (noticeEl) noticeEl.innerHTML = `<span style="color:var(--green-d)">✓ Scene <b>${res.staged_scene.tile_id}</b> is indexed and searchable in FAISS.</span>`;
   if (btn) btn.disabled = true;
  } else {
   if (badge) { badge.textContent = 'READY'; badge.className = 'sensor-badge fused'; }
   if (noticeEl) noticeEl.innerHTML = `<span>Staged tile ready for incremental embedding &amp; ingestion.</span>`;
   if (btn) btn.disabled = false;
  }
 } catch (e) {
  console.warn('Index status refresh failed:', e);
 }
}

async function triggerIncrementalIngest() {
 const btn = document.getElementById('btnIngestScene');
 if (btn) { btn.disabled = true; btn.textContent = 'Ingesting...'; }
 try {
  const res = window.DemoMode?.incrementalIngest ? await DemoMode.incrementalIngest() : await apiJson('/api/demo/indexing/incremental-ingest', {});
  toast(`Ingested scene ${res.tile_id} in ${res.duration_seconds}s (Index count: ${res.indexed_count_before} → ${res.indexed_count_after})`, 'success');
  const noticeEl = document.getElementById('idxResultNotice');
  if (noticeEl) {
   noticeEl.innerHTML = `<div style="background:rgba(124,154,120,.15);border:1px solid var(--green-d);padding:6px 8px;border-radius:6px;margin-top:6px">
    <b>Incremental Ingest Complete (No Rebuild)</b><br>
    • Before: Indexed scenes: <b>${res.indexed_count_before}</b><br>
    • Ingested: <b>${res.tile_id}</b> (${res.embedding_dim}-d)<br>
    • After: Indexed scenes: <b>${res.indexed_count_after}</b><br>
    • Latency: <b>${res.duration_seconds}s</b> · FAISS IndexIDMap2 vector appended
   </div>`;
  }
  await refreshIndexingStatus();
 } catch (e) {
  toast(apiError(e), 'error');
  if (btn) { btn.disabled = false; btn.textContent = '+ Add Scene to Index'; }
 }
}

async function triggerIndexReset() {
 try {
  const res = window.DemoMode?.resetIndexing ? await DemoMode.resetIndexing() : await apiJson('/api/demo/indexing/reset', {});
  toast(`Index reset to baseline (${res.indexed_count} scenes)`, 'info');
  const noticeEl = document.getElementById('idxResultNotice');
  if (noticeEl) noticeEl.innerHTML = 'Index restored to baseline 4 scenes.';
  await refreshIndexingStatus();
 } catch (e) {
  toast(apiError(e), 'error');
 }
}

function searchIngestedScene() {
 const qInput = document.getElementById('qText');
 if (qInput) {
  qInput.value = 'quarry excavation river bend';
 }
 setQMode('text');
 runSearch();
}
