/* ==========================================================================
   AVLOKAN - Application Bootstrap & Event Wiring
   ========================================================================== */

/* ================= INIT ================= */
renderStubs();
renderAoiList();
injectSearch();
injectTileLightbox();
document.getElementById('flowDash').innerHTML=flowStrip('dashboard');
document.getElementById('sysStatus').innerHTML=SYS.map(r=>
 `<div class="srow"><span class="sk">${r[0]}</span><span class="sv ${r[2]}">${r[1]}</span></div>`).join('');
document.getElementById('feed').innerHTML=FEED.map(f=>
 `<div class="feed"><span class="ft mono">${f[0]}</span><span class="fb">${f[1]}</span></div>`).join('');
document.querySelectorAll('.snav').forEach(n=>n.onclick=()=>go(n.dataset.go));
const hr=new Date().getHours();
document.getElementById('greet').textContent=(hr<12?'Good morning':hr<17?'Good afternoon':'Good evening')+', Analyst 01';
document.getElementById('dashDate').textContent=new Date()
 .toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Asia/Kolkata'})
 +' · All systems nominal';
tickClock();setInterval(tickClock,1000);
drawTopo();
window.addEventListener('resize',()=>{drawTopo();if(dashboardMap)dashboardMap.invalidate();needRender=true});
loadApiDashboard();
