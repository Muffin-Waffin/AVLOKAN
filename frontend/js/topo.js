/* ==========================================================================
   AVLOKAN - Login Screen Topographic Canvas Backdrop
   ========================================================================== */

/* ================= LOGIN TOPO BACKDROP ================= */
function drawTopo(){
 const c=document.getElementById('topo'),x=c.getContext('2d');
 c.width=innerWidth;c.height=innerHeight;
 const g=x.createLinearGradient(0,0,0,c.height);
 g.addColorStop(0,'#f7f3ea');g.addColorStop(1,'#ebe5d3');
 x.fillStyle=g;x.fillRect(0,0,c.width,c.height);
 const cols=['#7c9a78','#7ba6a3','#c98d68'];
 for(let i=0;i<16;i++){
  const base=i*(c.height/14)-40;
  const amp=18+Math.random()*26,f=.006+Math.random()*.004,ph=Math.random()*9;
  const amp2=8+Math.random()*14,f2=.013+Math.random()*.01,p2=Math.random()*9;
  x.strokeStyle=cols[i%3];x.globalAlpha=.14+(i%3)*.05;x.lineWidth=1.1;
  x.beginPath();
  for(let px=0;px<=c.width;px+=6){
   const py=base+Math.sin(px*f+ph)*amp+Math.sin(px*f2+p2)*amp2;
   px===0?x.moveTo(px,py):x.lineTo(px,py)}
  x.stroke()}
 x.globalAlpha=.35;
 for(let i=0;i<7;i++){
  const tx=60+Math.random()*(c.width-120),ty=60+Math.random()*(c.height-120),s=5+Math.random()*4;
  x.strokeStyle='#9c6244';x.lineWidth=1.2;
  x.beginPath();x.moveTo(tx,ty-s);x.lineTo(tx+s,ty+s*.8);x.lineTo(tx-s,ty+s*.8);x.closePath();x.stroke()}
 x.globalAlpha=1}
