"""Apply normalization and filter fixes to frontend/js/modules/search.js and frontend/js/modules/results.js."""
from pathlib import Path

ROOT = Path("D:/sih/AVLOKAN")

# 1. Update frontend/js/modules/search.js
search_path = ROOT / "frontend/js/modules/search.js"
code = search_path.read_text(encoding="utf-8")

# Fix selectDemoImage to ensure mode is set to 'image'
old_select = "function selectDemoImage(){S.demoScene='s2_demo__tile_000000';S.file=null;S.img=null;const p=document.getElementById('imgPreview');p.src=apiAsset('/api/tiles/s2_demo__tile_000000/preview');p.style.display='block';document.getElementById('dz').classList.add('hidden');toast('Official real local Sentinel-2 demo tile selected','success')}"
new_select = "function selectDemoImage(){if(S.mode!=='image')setQMode('image');S.demoScene='s2_demo__tile_000000';S.file=null;S.img=null;const p=document.getElementById('imgPreview');p.src=apiAsset('/api/tiles/s2_demo__tile_000000/preview');p.style.display='block';document.getElementById('dz').classList.add('hidden');toast('Official real local Sentinel-2 demo tile selected','success')}"
assert old_select in code, "old_select not found"
code = code.replace(old_select, new_select)

# Fix resetSearch to properly clear date filters and restore defaults
old_reset = """function resetSearch(){
 document.getElementById('qText').value='';clearQImage();
 S.region='all';document.getElementById('fRegion').value='all';
 S.sensors={s2:true,s1:true,l8:true,bh:false};
 SENSORS.forEach(s=>document.getElementById('sc-'+s.id).classList.toggle('on',S.sensors[s.id]));
 setDatePreset(1);
 S.cloud=40;document.getElementById('fCloud').value=40;document.getElementById('cloudVal').textContent='40%';
S.minSim=0;document.getElementById('fSim').value=0;document.getElementById('simVal').textContent='0.00';
 S.topK=24;document.getElementById('fTopK').value='24';
 toast('Filters reset to defaults')}"""

new_reset = """function resetSearch(){
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
 toast('Filters reset to defaults')}"""
assert old_reset in code, "old_reset not found"
code = code.replace(old_reset, new_reset)

# Add normalizeSensor helper and use it in runSearch
normalize_helper = """function normalizeSensor(raw){
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
"""

old_mapping = """  S.results=(response.results||[]).map((r,i)=>{
   const sensorValue=typeof r.sensor==='string'?r.sensor:(r.sensor&&r.sensor.id)||'';
   const sensorTag=typeof r.sensor==='object'&&r.sensor?r.sensor.tag:'';
   const sensor=SENSORS.find(s=>s.id===String(sensorValue).toLowerCase())||
    SENSORS.find(s=>s.tag===String(sensorTag).toLowerCase())||{};
   return {...r,_api:true,_rank:r.rank||i+1,date:r.date?new Date(r.date):null,
    sensor:{...sensor,...(typeof r.sensor==='object'?r.sensor:{id:r.sensor,tag:sensor.tag,name:sensor.name})},thumbnail_url:apiAsset(r.thumbnail_url),_demo:response.query_type==='demo-prepared',
    region:r.region||'Local archive'};
  });"""

new_mapping = """  S.results=(response.results||[]).map((r,i)=>{
   return {...r,_api:true,_rank:r.rank||i+1,date:r.date?new Date(r.date):null,
    sensor:normalizeSensor(r.sensor),thumbnail_url:apiAsset(r.thumbnail_url),_demo:response.query_type==='demo-prepared',
    region:r.region||'Local archive'};
  });"""
assert old_mapping in code, "old_mapping not found"
code = code.replace(old_mapping, new_mapping)

if "function normalizeSensor(" not in code:
    code = code.replace("const RUN_HTML=", normalize_helper + "\nconst RUN_HTML=")

search_path.write_text(code, encoding="utf-8")
print("Updated frontend/js/modules/search.js")

# 2. Update frontend/js/modules/results.js
results_path = ROOT / "frontend/js/modules/results.js"
rcode = results_path.read_text(encoding="utf-8")

old_shown = "function shownResults(){return sortResults(S.results.filter(r=>S.qf[r.sensor.id]))}"
new_shown = """function shownResults(){
 return sortResults(S.results.filter(r=>{
  if(!r.sensor)return false;
  const sid=(r.sensor.id||(typeof r.sensor==='string'?r.sensor:'')).toLowerCase();
  const normId=(sid==='sentinel-2'?'s2':(sid==='sentinel-1'?'s1':(sid==='landsat'?'l8':(sid==='bhuvan'?'bh':sid))));
  return S.qf[normId]!==false;
 }));
}"""
assert old_shown in rcode, "old_shown not found"
rcode = rcode.replace(old_shown, new_shown)
results_path.write_text(rcode, encoding="utf-8")
print("Updated frontend/js/modules/results.js")
