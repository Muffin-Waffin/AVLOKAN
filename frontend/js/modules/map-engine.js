/* AVLOKAN dashboard map. The map is geographic Leaflet with local XYZ tiles. */
let dashboardMap = null;
let mapInitialized = false;

function initMap() {
  if (mapInitialized) { if (dashboardMap) dashboardMap.invalidate(); return; }
  const body = document.getElementById('mapBody');
  if (!body || !window.L || !window.createAvlokanMap) return;
  dashboardMap = createAvlokanMap({
    container: body, center: [22.7774, 75.8247], zoom: 9, coordsEl: 'mapCoords',
    onPinHit: a => openInv(a.id),
    onTileError: () => { const el = document.getElementById('mapGsd'); if (el) el.textContent = 'LOCAL BASEMAP · partial coverage'; }
  });
  mapInitialized = !!dashboardMap;
  window.dashboardMap = dashboardMap;
  if (dashboardMap) dashboardMap.setAOIs(window.BackendAOIs || []);
}
function renderMap() { if (dashboardMap) dashboardMap.invalidate(); }
function zoomStep(delta) { if (dashboardMap) dashboardMap.zoom(delta); }
function mapHome() { if (dashboardMap) dashboardMap.home(); }
function toggleLayer(el) { el.classList.toggle('on'); }
function pump() { requestAnimationFrame(pump); }
requestAnimationFrame(pump);
