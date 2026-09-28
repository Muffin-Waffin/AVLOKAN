/* AVLOKAN dashboard map rendered by the shared MapLibre adapter. */
let dashboardMap = null;
let mapInitialized = false;

function initMap() {
  if (mapInitialized) { if (dashboardMap) dashboardMap.invalidate(); return; }
  const body = document.getElementById('mapBody');
  if (!body || !window.maplibregl || !window.createAvlokanMap) return;
  dashboardMap = createAvlokanMap({
    container: body, center: [22.7774, 75.8247], zoom: 9, coordsEl: 'mapCoords',
    onPinHit: a => openInv(a.id),
    onTileError: () => { const el = document.getElementById('mapGsd'); if (el) el.textContent = 'BASEMAP RESOURCE ERROR'; }
  });
  mapInitialized = !!dashboardMap;
  window.dashboardMap = dashboardMap;
  if (dashboardMap) dashboardMap.setAOIs(window.BackendAOIs || []);
}
function renderMap() { if (dashboardMap) dashboardMap.invalidate(); }
function zoomStep(delta) { if (dashboardMap) dashboardMap.zoom(delta); }
function mapHome() { if (dashboardMap) dashboardMap.home(); }
function toggleLayer(el) {
  if (dashboardMap) {
    if (el.dataset.l === 'optical') dashboardMap.toggleSatellite();
    else if (el.dataset.l === 'labels') dashboardMap.toggle('labels');
    else if (el.dataset.l === 'radius') dashboardMap.toggle('registry');
  }
  el.classList.toggle('on');
}
