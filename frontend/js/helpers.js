/* ==========================================================================
   AVLOKAN - General Helpers & Formatters
   ========================================================================== */

/* ================= HELPERS ================= */
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
function hexA(hex,a){const n=parseInt(hex.slice(1),16);return `rgba(${n>>16},${(n>>8)&255},${n&255},${a})`}
function flowStrip(active){return FLOW.map((f,i)=>
 `<span class="fs-chip${f.id===active?' on':''}"><span class="n">${i+1}</span>${f.name}</span>`+
 (i<FLOW.length-1?'<span class="fs-arrow">→</span>':'')).join('')}
function istTime(){return new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:false})}
function addFeed(html){const f=document.getElementById('feed');const d=document.createElement('div');d.className='feed';
 d.innerHTML=`<span class="ft mono">${istTime()}</span><span class="fb">${html}</span>`;f.prepend(d)}
function toast(msg,type='info'){
 const ok='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4 12 14.01l-3-3"/></svg>';
 const inf='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/></svg>';
 const t=document.createElement('div');t.className='toast '+type;
 t.innerHTML=type==='success'?ok:inf;
 const message=document.createElement('span');message.textContent=String(msg);t.appendChild(message);
 document.getElementById('toasts').appendChild(t);
 setTimeout(()=>{t.style.transition='.4s';t.style.opacity=0;setTimeout(()=>t.remove(),400)},3400)}
