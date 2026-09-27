/* AVLOKAN offline-first geographic map helper. Leaflet and XYZ tiles are local. */
(function () {
  const TILE_URL = 'assets/map-tiles/{z}/{x}/{y}.png';
  const TILE_BOUNDS = [[22.2, 74.7], [23.8, 76.4]];

  function validPoint(lat, lng) {
    return Number.isFinite(Number(lat)) && Number.isFinite(Number(lng)) &&
      Number(lat) >= -90 && Number(lat) <= 90 && Number(lng) >= -180 && Number(lng) <= 180;
  }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function bboxPolygon(bbox) {
    if (!Array.isArray(bbox) || bbox.length < 4 || !bbox.every(Number.isFinite)) return null;
    const [west, south, east, north] = bbox;
    return [[south, west], [south, east], [north, east], [north, west], [south, west]];
  }
  function geometryLatLng(geometry, bbox) {
    if (geometry && geometry.type === 'Polygon' && Array.isArray(geometry.coordinates)) {
      return geometry.coordinates.map(ring => ring.map(pair => [pair[1], pair[0]]));
    }
    const poly = bboxPolygon(bbox);
    return poly ? [poly] : null;
  }

  window.createAvlokanMap = function (options) {
    const container = typeof options.container === 'string' ? document.getElementById(options.container) : options.container;
    if (!container || !window.L) return null;
    if (container._avlokanMap) return container._avlokanMap;
    const map = L.map(container, { zoomControl: false, minZoom: 7, maxZoom: 14 });
    L.control.zoom({ position: 'topright' }).addTo(map);
    map.setView(options.center || [22.78, 75.82], options.zoom || 8);
    const tiles = L.tileLayer(TILE_URL, {
      minZoom: 7, maxZoom: 14, bounds: TILE_BOUNDS, tileSize: 256,
      attribution: 'AVLOKAN local Sentinel-2 prototype raster · Copernicus Sentinel data', crossOrigin: false
    }).addTo(map);
    tiles.on('tileerror', e => { if (options.onTileError) options.onTileError(e); });
    const aoiLayer = L.layerGroup().addTo(map);
    const sceneLayer = L.layerGroup().addTo(map);
    let analysisOverlay = null;
    let selectedScene = null;
    let lastScenes = [];

    function popupFor(item) {
      const name = item.name || item.id || 'AOI';
      const coord = validPoint(item.lat, item.lng) ? `${Number(item.lat).toFixed(5)}, ${Number(item.lng).toFixed(5)}` : 'Unavailable';
      return `<b>${esc(name)}</b><br><span class="mono">${esc(coord)}</span><br>Radius: ${esc(item.radius_km ?? item.rad ?? '—')} km`;
    }
    function renderAOIs(items) {
      aoiLayer.clearLayers();
      (items || []).forEach(item => {
        const lat = Number(item.lat), lng = Number(item.lng), radius = Number(item.radius_km ?? item.rad);
        if (!validPoint(lat, lng) || !Number.isFinite(radius) || radius <= 0) return;
        const circle = L.circle([lat, lng], { radius: radius * 1000, color: '#5b8c89', weight: 2, dashArray: '7 5', fillColor: '#7ba6a3', fillOpacity: .10 });
        const marker = L.circleMarker([lat, lng], { radius: 7, color: '#5b8c89', weight: 2, fillColor: '#fbf8ef', fillOpacity: 1 });
        circle.bindPopup(popupFor(item)); marker.bindPopup(popupFor(item));
        [circle, marker].forEach(layer => layer.on('click', () => options.onPinHit && options.onPinHit(item)));
        aoiLayer.addLayer(circle); aoiLayer.addLayer(marker);
      });
    }
    function renderScenes(items) {
      sceneLayer.clearLayers(); lastScenes = items || [];
      lastScenes.forEach((scene, index) => {
        if (!scene) return;
        const latlngs = geometryLatLng(scene.footprint, scene.bbox);
        if (!latlngs) return;
        const prototype = scene.record_type === 'prototype_analysis_ready';
        const layer = L.polygon(latlngs, { color: index === selectedScene ? '#c98b8b' : (prototype ? '#7c9a78' : '#6d7f9b'), weight: index === selectedScene ? 3 : 1.5, fillOpacity: index === selectedScene ? .20 : .06, dashArray: prototype ? '4 3' : null });
        const label = `${prototype ? 'Prototype ' + (scene.observation_role || '') : 'Scene'} · ${scene.id || 'unnamed'}${scene.footprint ? '' : ' · bbox-derived display geometry'}`;
        layer.bindTooltip(esc(label)); layer.bindPopup(`<b>${esc(scene.id || 'Scene')}</b><br>${esc(scene.acquisition_datetime || scene.date || '')}<br>${esc(scene.sensor || '')}${scene.footprint ? '<br>Footprint geometry' : '<br>Bbox-derived display geometry'}`);
        layer.on('click', () => options.onSceneHit && options.onSceneHit(scene, index));
        sceneLayer.addLayer(layer);
      });
    }
    const api = {
      map, tileLayer: tiles,
      setAOIs(items) { renderAOIs(items); },
      setScenes(items) { selectedScene = null; renderScenes(items); },
      setAnalysisOverlay(url, bbox, opacity = .55) {
        if (analysisOverlay) map.removeLayer(analysisOverlay);
        if (!url || !Array.isArray(bbox) || bbox.length < 4) return false;
        const [west, south, east, north] = bbox.map(Number);
        if (![west, south, east, north].every(Number.isFinite)) return false;
        analysisOverlay = L.imageOverlay(url, [[south, west], [north, east]], { opacity, interactive: false });
        analysisOverlay.addTo(map); return true;
      },
      clearAnalysisOverlay() { if (analysisOverlay) { map.removeLayer(analysisOverlay); analysisOverlay = null; } },
      selectScene(index) { selectedScene = index; renderScenes(lastScenes); const scene = lastScenes[index]; if (scene) { const ll = geometryLatLng(scene.footprint, scene.bbox); if (ll) map.fitBounds(ll, { padding: [24, 24], maxZoom: 9 }); } },
      setPin(point) {
        if (!point || !validPoint(point.lat, point.lng)) return;
        if (api.pinLayer) map.removeLayer(api.pinLayer);
        const radius = Number(point.rad || point.radius_km || 3);
        api.pinLayer = L.circle([point.lat, point.lng], { radius: radius * 1000, color: '#5b8c89', weight: 2, dashArray: '6 4', fillOpacity: .04 }).addTo(map);
      },
      clearPin() { if (api.pinLayer) { map.removeLayer(api.pinLayer); api.pinLayer = null; } },
      flyTo(lat, lng, zoom) { if (validPoint(lat, lng)) map.flyTo([lat, lng], zoom || map.getZoom()); },
      zoom(delta) { map.setZoom(Math.max(7, Math.min(10, map.getZoom() + delta))); },
      home() { map.fitBounds(TILE_BOUNDS, { padding: [18, 18] }); },
      toggle() { return true; },
      invalidate() { setTimeout(() => map.invalidateSize(), 0); renderAOIs(window.BackendAOIs || []); },
      getBounds() { return TILE_BOUNDS; }
    };
    map.on('mousemove', e => { if (options.coordsEl) document.getElementById(options.coordsEl).textContent = `${Math.abs(e.latlng.lat).toFixed(4)}°${e.latlng.lat >= 0 ? 'N' : 'S'}  ${Math.abs(e.latlng.lng).toFixed(4)}°${e.latlng.lng >= 0 ? 'E' : 'W'}`; });
    map.on('click', e => options.onPick && options.onPick(e.latlng.lat, e.latlng.lng));
    container._avlokanMap = api;
    renderAOIs(window.BackendAOIs || []);
    setTimeout(() => map.invalidateSize(), 50);
    return api;
  };
  window.AVLOKAN_MAP_TILE_BOUNDS = TILE_BOUNDS;
})();
