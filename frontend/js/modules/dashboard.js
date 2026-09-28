/* ==========================================================================
   AVLOKAN - Mission Dashboard & AOI Registry
   ========================================================================== */

/* ================= DASHBOARD ================= */
function animCounters(){
 document.querySelectorAll('[data-count]').forEach(el=>{
  const target=+el.dataset.count,dur=1000,t0=performance.now();
  (function step(now){
   const p=Math.min(1,(now-t0)/dur);
   el.textContent=Math.round(target*(1-Math.pow(1-p,3))).toLocaleString('en-IN');
   if(p<1)requestAnimationFrame(step)})(t0)})}
function tickClock(){
 document.getElementById('clock').textContent=
  new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour12:false})+' IST'}

/* ================= AOI LIST ================= */
function renderAoiList(){
 const list=window.BackendAOIs||[];
 if(!list.length){document.getElementById('aoiList').innerHTML='<div class="tip">No AOIs have been registered in the backend.</div>';return}
 document.getElementById('aoiList').innerHTML=list.map(a=>`
  <div class="aoi-row" role="button" tabindex="0" onclick="stageBackendAOI('${escapeHtml(a.id)}')">
   <span class="aoi-dot" style="background:var(--cyan)"></span>
   <div><div class="aoi-n">${escapeHtml(a.name)}</div>
   <div class="aoi-m mono">${Number(a.lat).toFixed(3)}°, ${Number(a.lng).toFixed(3)}° · radius ${a.radius_km} km</div></div>
   <span class="aoi-go">→</span>
  </div>`).join('')}

async function loadApiDashboard(){
 const status=document.getElementById('sysStatus');
 try{
  const [dash,health,aois]=await Promise.all([
   apiRequest('/api/dashboard'),apiRequest('/api/health'),apiRequest('/api/aois')]);
  window.BackendAOIs=aois.items||[];
  if(window.dashboardMap)window.dashboardMap.setAOIs(window.BackendAOIs);
  window.BackendHealth=health;
  const cards=document.querySelectorAll('#view-dashboard .stats .stat');
  const stats=dash.statistics||{};
  const values=[stats.tiles_indexed,stats.local_scenes,stats.pending_review,null];
  const labels=['Tiles in local index','Scenes in local catalog','Pending analyst review','Query latency not provided by API'];
  cards.forEach((card,i)=>{
   const value=card.querySelector('.sn');if(value)value.textContent=values[i]==null?'—':Number(values[i]).toLocaleString('en-IN');
   const desc=card.querySelector('.sd');if(desc)desc.textContent=labels[i];
  });
  const indexPill=document.querySelector('.topbar .pills .pill');
  if(indexPill)indexPill.innerHTML='<span class="dot '+(health.retrieval.available?'g':'v')+'"></span>'+
   (health.retrieval.available?Number(health.retrieval.indexed_tiles).toLocaleString('en-IN')+' INDEXED':'INDEX UNAVAILABLE');
  const apiPill=document.getElementById('apiStatusPill');if(apiPill)apiPill.innerHTML='<span class="dot '+(health.retrieval.available?'g':'v')+'"></span>'+(health.retrieval.available?'API CONNECTED':'API PARTIAL');
  const badge=document.getElementById('revBadge');if(badge)badge.textContent=String(stats.pending_review??0);
  const moduleBadge=document.querySelector('.mod.alert .mbadge');if(moduleBadge)moduleBadge.textContent=String(stats.pending_review??0)+' pending';
  const sys=[
   ['Semantic retrieval',health.retrieval.available?'Available':'Unavailable',health.retrieval.available?'g':'a'],
   ['Local tiles',health.retrieval.catalog_tiles??'Unavailable','c'],
   ['Scene catalog',health.scene_catalog_records+' records','c'],
   ['Change checkpoint',health.change_checkpoint&&health.change_checkpoint.exists?'Configured':'Unavailable',health.change_checkpoint&&health.change_checkpoint.exists?'g':'a'],
   ['API database',health.database&&health.database.available?'Available':'Unavailable',health.database&&health.database.available?'g':'a']
  ];
  status.innerHTML=sys.map(r=>`<div class="srow"><span class="sk">${escapeHtml(r[0])}</span><span class="sv ${r[2]}">${escapeHtml(r[1])}</span></div>`).join('');
  renderSearchIndexStatus(health);
  const activity=(dash.recent_activity||[]).map(event=>{const detail=String(event.detail||''),id=detail.match(/\b[a-f0-9]{32}\b/i)?.[0];const description=id?detail.replace(id,'').replace(/\s{2,}/g,' ').trim():detail;return `<div class="feed"><div class="feed-head"><span class="ft mono">${escapeHtml(event.timestamp||'')}</span><span class="tag c">${escapeHtml(event.action||'EVENT')}</span></div><div class="fb">${escapeHtml(description||detail)}</div>${id?`<div class="feed-id mono" title="${escapeHtml(id)}">${escapeHtml(id)}</div>`:''}</div>`}).join('');
  const feed=document.getElementById('feed');if(feed)feed.innerHTML=activity||'<div class="tip">No backend activity recorded yet.</div>';
  renderAoiList();
  needRender=true;if(window.EMAP)EMAP.invalidate();
 }catch(error){
  status.innerHTML=`<div class="tip" role="alert">Backend status unavailable: ${escapeHtml(apiError(error))}</div>`;
  const apiPill=document.getElementById('apiStatusPill');if(apiPill)apiPill.innerHTML='<span class="dot v"></span>API UNAVAILABLE';
  const indexPill=document.querySelector('.topbar .pills .pill');if(indexPill)indexPill.innerHTML='<span class="dot v"></span>INDEX UNAVAILABLE';
  renderSearchIndexStatus({retrieval:{available:false,indexed_tiles:null,catalog_tiles:null}});
  document.querySelectorAll('#view-dashboard .stats .sn').forEach(value=>value.textContent='—');
  const feed=document.getElementById('feed');if(feed)feed.innerHTML='<div class="tip">Backend activity unavailable.</div>';
  window.BackendAOIs=[];renderAoiList();
 }
}

function renderSearchIndexStatus(health,timings){
 const panel=Array.from(document.querySelectorAll('#view-search .panel')).find(node=>node.querySelector('.panel-h')?.textContent.includes('Index Status'));
 if(!panel)return;
 const values=[
  ['Indexed tiles',health.retrieval.indexed_tiles??'Unavailable'],
  ['Catalog tiles',health.retrieval.catalog_tiles??'Unavailable'],
  ['Retrieval service',health.retrieval.available?'Available':'Unavailable'],
  ['Last query time',timings&&timings.total_ms!=null?timings.total_ms+' ms':'Not reported'],
  ['Last sync','Not provided by API']
 ];
 panel.querySelector('.panel-b').innerHTML=values.map((row,index)=>`<div class="srow"><span class="sk">${escapeHtml(row[0])}</span><span class="sv ${index===2?(health.retrieval.available?'g':'a'):'c'}">${escapeHtml(row[1])}</span></div>`).join('');
}

function stageBackendAOI(id){
 const a=(window.BackendAOIs||[]).find(item=>item.id===id);if(!a)return;
 App.stagedAOI=a;go('scene');
}

/* ================= STUBS ================= */
function renderStubs(){
 Object.entries(STUBS).forEach(([id,s])=>{
  const el=document.getElementById('view-'+id);if(!el)return;
  el.innerHTML=`<div class="panel stub">
   <div class="si">${ICONS[s.icon]}</div>
   <h2>${s.title}</h2>
   <p>${s.desc}</p>
   <div class="ph">Scheduled — Build Phase ${s.phase}</div>
   <div class="flowstrip">${flowStrip(s.flow)}</div>
   <button class="btn btn-ghost" onclick="go('dashboard')">← Back to Dashboard</button>
  </div>`})}
