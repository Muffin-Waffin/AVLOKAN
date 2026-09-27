/* ==========================================================================
   AVLOKAN - Global State, Dictionaries & Static Data
   ========================================================================== */

/* ================= STATE & DATA ================= */
const App={user:null,route:'dashboard'};
let pendingCount=14,curAoi=null,mapReady=false,needRender=true;

const FLOW=[
 {id:'login',name:'Login / Home'},{id:'dashboard',name:'Dashboard'},
 {id:'search',name:'Search / Retrieval'},{id:'results',name:'Search Results'},
 {id:'scene',name:'Select Area / Scene'},{id:'analysis',name:'Multi-Temporal Analysis'},
 {id:'detection',name:'Change Detection'},{id:'verified',name:'Verified Change'},
 {id:'review',name:'Analyst Review'},{id:'audit',name:'Provenance / Audit'}];

const TITLES={dashboard:'Mission Dashboard',search:'Search / Retrieval',results:'Search Results',
 scene:'Select Area / Scene',map:'Map Explorer',analysis:'Multi-Temporal Analysis',
 detection:'Change Detection',verified:'Verified Change',review:'Analyst Review Queue',audit:'Provenance / Audit'};

const ICONS={
 search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
 grid:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
 map:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
 globe:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
 layers:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
 cpu:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3m6-3v3M9 20v3m6-3v3M1 9h3m-3 6h3m16-6h3m-3 6h3"/></svg>',
 check:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4 12 14.01l-3-3"/></svg>',
 clipboard:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>',
 file:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8m8 4H8"/></svg>'};

const STUBS={
 scene:{phase:4,flow:'scene',icon:'map',title:'Select Area / Scene',desc:'Interactive map with AOI selection and acquisition timeline — pick any scene for multi-temporal analysis.'},
 map:{phase:4,flow:'scene',icon:'globe',title:'Map Explorer',desc:'Archive-wide map browsing. Pan, zoom, and send any location straight to search or change analysis.'},
 analysis:{phase:5,flow:'analysis',icon:'layers',title:'Multi-Temporal Analysis',desc:'Before ↔ After comparison across T1 / T2 with optical / SAR toggle and timeline scrubbing.'},
 detection:{phase:5,flow:'detection',icon:'cpu',title:'Change Detection Pipeline',desc:'Embedding Gate → Pixel-Level BIT Verification → SAR Fallback when optical is cloud-obscured.'},
 verified:{phase:5,flow:'verified',icon:'check',title:'Verified Change',desc:'Change region, confidence, sensor agreement and before/after evidence — every verdict provable.'},
 review:{phase:6,flow:'review',icon:'clipboard',title:'Analyst Review Queue',desc:'Confirm · Reject · Need Review — decisions on AI-prioritized candidates with full evidence attached.'},
 audit:{phase:6,flow:'audit',icon:'file',title:'Provenance & Audit Trail',desc:'Source scene, sensor, timestamp, confidence and analyst decision — logged immutably.'}};

const SYS=[
 ['FAISS Vector Index','1.28M · HNSW/SQ8','g'],
 ['PostgreSQL + PostGIS','Connected · 8,412 scenes','g'],
 ['SAR Fallback — S1 VV/VH','ARMED','v'],
 ['Ingestion Worker','Idle · last sync 14m ago','a'],
 ['Network Interface','AIR-GAPPED','g'],
 ['Docker Services','6 / 6 healthy','g']];

const FEED=[
 ['09:41','<span class="tag g">CONFIRMED</span><b>Analyst 01</b> confirmed change at Mumbai docks — 96% confidence'],
 ['09:12','<span class="tag c">INDEX</span>Incremental index: 3,204 new Sentinel-2 tiles, Western sector'],
 ['08:55','<span class="tag a">REVIEW</span>Change flagged near Delhi — optical cloud-obscured, <b>SAR fallback verified</b>'],
 ['08:30','<span class="tag r">REJECTED</span><b>Analyst 02</b> rejected candidate — seasonal crop rotation'],
 ['07:58','<span class="tag c">SYSTEM</span>Nightly false-alarm suppression pass complete — 41 candidates suppressed']];

/* AOI registry — synthetic demo data */
const AOIS=[
 {id:'aoi-01',name:'Mumbai Docks — Berth 7',lat:18.955,lng:72.842,rad:3.2,status:'high',seed:11,conf:96,change:8.4,agree:'S2 ✓ · S1 ✓',quality:0.94,cat:'New berth construction + container yard',t1:'2026-03-14',t2:'2026-09-08',passes:['2026-03-02','2026-03-14','2026-04-08','2026-05-02','2026-06-20','2026-07-15','2026-08-09','2026-09-08']},
 {id:'aoi-02',name:'Delhi NE — Peripheral Depot',lat:28.612,lng:77.208,rad:2.5,status:'mid',seed:23,conf:89,change:5.1,agree:'S2 ✓ · S1 ✓',quality:0.88,cat:'Warehouse complex + access road cut',t1:'2026-02-11',t2:'2026-09-02',passes:['2026-02-11','2026-03-02','2026-04-05','2026-05-13','2026-06-18','2026-07-27','2026-08-21','2026-09-02']},
 {id:'aoi-03',name:'Chennai — Industrial Outskirts',lat:13.082,lng:80.270,rad:4.0,status:'mid',seed:37,conf:82,change:6.7,agree:'S2 ✓ · S1 ◐',quality:0.81,cat:'Shed cluster expansion + land clearing',t1:'2026-01-20',t2:'2026-08-30',passes:['2026-01-20','2026-02-18','2026-03-24','2026-04-27','2026-06-01','2026-07-06','2026-08-30']},
 {id:'aoi-04',name:'Ladakh — Forward Sector K2',lat:34.152,lng:77.580,rad:6.5,status:'high',seed:53,conf:91,change:3.9,agree:'S1 ✓ · optical ✗',quality:0.86,sar:true,cat:'Structure cluster + track widening',t1:'2026-04-02',t2:'2026-09-12',passes:['2026-04-02','2026-04-16','2026-05-04','2026-06-11','2026-07-19','2026-08-14','2026-09-12']},
 {id:'aoi-05',name:'Bhadla — Solar Phase IV',lat:27.541,lng:71.905,rad:5.0,status:'low',seed:71,conf:78,change:11.2,agree:'S2 ✓ · L9 ✓',quality:0.90,cat:'Panel array expansion — civil activity',t1:'2026-02-08',t2:'2026-09-05',passes:['2026-02-08','2026-03-01','2026-04-04','2026-05-07','2026-06-10','2026-07-13','2026-08-16','2026-09-05']}];

const TER={deep:'#8fb6c2',water:'#a9cbd3',sand:'#e9dfc3',urban:'#cfc3ae',forest:'#a3b98f',grass:'#c6d2ac',arid:'#ddcba6'};
const colOf=s=>({high:'#c98d68',mid:'#d3a656',low:'#7ba6a3'})[s];
