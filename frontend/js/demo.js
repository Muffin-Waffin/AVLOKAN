/* Optional SIH demo adapter. Prepared records are served by the local API. */
(function(){
 const D={enabled:false,ready:null,scene:null,investigation:null,timeline:null};
 D.syncControls=()=>{['demoQueryChip','demoImageChip'].forEach(id=>{const n=document.getElementById(id);if(n)n.hidden=!D.enabled})};
 D.ready=apiRequest('/api/demo/status').then(x=>{D.enabled=!!x.enabled;document.documentElement.dataset.demoMode=D.enabled?'on':'off';
  D.syncControls();
  return D.enabled}).catch(()=>false);
 D.search=async(mode,body)=>{await D.ready;return apiJson('/api/demo/search/'+mode,body)};
 D.showSimilar=async sceneId=>{if(!D.enabled)return;try{const result=await apiRequest('/api/demo/similar-sites?scene_id='+encodeURIComponent(sceneId));
  window.AvlokanMaps?.scene?.setSimilarSites(result.sites||[]);
  let box=document.getElementById('demoSimilar');if(!box){box=document.createElement('div');box.id='demoSimilar';box.className='overlay';document.body.appendChild(box)}
  box.innerHTML='<div class="modal" style="width:760px"><div class="modal-h"><div><div class="inv-t">Similar Sites</div><div class="inv-s">'+result.label+'</div></div><button class="icon-btn" style="margin-left:auto" onclick="document.getElementById(\'demoSimilar\').remove()">×</button></div><div class="modal-b"><div class="rgrid">'+result.sites.map(s=>'<article class="rcard"><div class="rthumb"><img class="api-thumbnail" src="'+apiAsset(s.thumbnail)+'" alt="Real local Sentinel-2 preview"></div><div class="rbody"><div class="rtitle">'+s.location+'</div><div class="rmeta mono">'+s.scene_id+' · '+s.date+' · '+s.sensor+' · demo score '+s.similarity+'</div></div></article>').join('')+'</div></div></div>';
  box.classList.remove('hidden');}catch(e){toast(apiError(e),'error')}};
 D.openInvestigation=async scene=>{if(!D.enabled)return;D.scene=scene;try{[D.investigation,D.timeline,D.evidence,D.provenance]=await Promise.all([apiRequest('/api/demo/investigation'),apiRequest('/api/demo/timeline'),apiRequest('/api/demo/evidence'),apiRequest('/api/demo/provenance')]);
  const make=(role,date,id,path)=>({id,record_type:'prototype_analysis_ready',observation_role:role,pair_id:'avlokan-s2-20250324__20250329',
   date:new Date(date+'T00:00:00Z'),sensor:{id:'s2',name:'Sentinel-2',tag:'S2',col:'#5b8c89',gsd:'10 m'},localPath:path,available_locally:true,lat:D.investigation.location.lat,lng:D.investigation.location.lng});
  App.pair={a:make('T1','2025-03-24',D.timeline.observations[0].scene_id,D.timeline.observations[0].path),b:make('T2','2025-03-29',D.timeline.observations[1].scene_id,D.timeline.observations[1].path),
   pin:D.investigation.location,rad:2.5,name:D.investigation.title};
  App.demoInvestigation=D.investigation;App.demoTimeline=D.timeline;App.demoEvidence=D.evidence;App.demoProvenance=D.provenance;App.demoSelected={T1:false,T2:false};D.selected={T1:false,T2:false};
  const map=window.AvlokanMaps?.scene;
  map?.setAOIGeometry({type:'bbox',coordinates:D.investigation.aoi.coordinates});
  map?.setScenes(D.timeline.observations.map(o=>({id:o.scene_id,record_type:'prototype_analysis_ready',observation_role:o.role, bbox:o.bbox||D.investigation.aoi.coordinates})));
  map?.setPin({...D.investigation.location,rad:2.5,name:D.investigation.title});
  toast('Investigation loaded from local demo data; select both timeline observations','success');go('analysis');}catch(e){toast(apiError(e),'error')}};
 D.timelineHtml=()=>!D.timeline?'':`<div class="panel" style="margin:14px 0"><div class="panel-h">Temporal timeline · choose both observations</div><div class="panel-b" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">${D.timeline.observations.map(o=>`<button class="btn btn-ghost" style="height:auto;text-align:left;padding:12px" onclick="DemoMode.selectObservation('${o.role.startsWith('T1')?'T1':'T2'}')"><img src="${apiAsset(o.preview)}" alt="Real Sentinel-2 preview" style="display:block;width:100%;max-height:150px;object-fit:contain;margin-bottom:8px"><b>${o.date} · ${o.role}</b><br><small>${o.scene_id} · ${o.sensor} · REAL</small></button>`).join('')}</div><div class="tip">Selected: T1 ${D.selected?.T1?'✓':'—'} · T2 ${D.selected?.T2?'✓':'—'}</div></div>`;
 D.selectObservation=role=>{if(!D.selected)D.selected={T1:false,T2:false};D.selected[role]=true;App.demoSelected=D.selected;if(App.route==='analysis')renderAnalysis()};
 D.export=async()=>{const data=await apiRequest('/api/demo/export');const save=(name,body,type)=>{const u=URL.createObjectURL(new Blob([body],{type}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
  save('avlokan-demo-investigation.json',JSON.stringify(data,null,2),'application/json');
  const r=data.review.decision;const report=['AVLOKAN SIH DEMO INVESTIGATION','Investigation: '+data.investigation.title,'Pair: Sentinel-2 2025-03-29 / 2025-03-24','Analysis: '+data.analysis.analysis_id,'Saved BIT changed pixels: '+data.analysis.statistics.changed_pixels,'Threshold: '+data.analysis.threshold,'Candidate count: '+data.analysis.candidate_count,'Change interpretation: DEMO-SIMULATED construction','SAR fallback: Real Sentinel-1A dual-pol (VV/VH) terrain-corrected evidence (2025-03-27)','Sensor agreement: HIGH AGREEMENT','Evidence Score: 84.7% (uncalibrated fusion)','Analyst decision: '+(r?r.decision+' by '+r.analyst+' at '+r.timestamp:'not recorded'),'', 'Source metadata: '+data.provenance.metadata_path].join('\n');
  save('avlokan-demo-report.txt',report,'text/plain;charset=utf-8')};
 D.review=async(decision,candidateId)=>apiJson('/api/demo/review',{decision,candidate_id:candidateId,analyst:'Demo Analyst'});
 D.audit=async()=>apiRequest('/api/demo/audit');
 D.reset=async()=>apiRequest('/api/demo/reset',{});
 D.getSarFallback=async()=>apiRequest('/api/demo/sar-fallback');
 D.getSensorAgreement=async()=>apiRequest('/api/demo/sensor-agreement');
 D.getIndexingStatus=async()=>apiRequest('/api/demo/indexing/status');
 D.incrementalIngest=async()=>apiJson('/api/demo/indexing/incremental-ingest',{});
 D.resetIndexing=async()=>apiJson('/api/demo/indexing/reset',{});
 window.DemoMode=D;
})();
