/* AVLOKAN maps rendered by MapLibre GL JS. OpenFreeMap is the development
 * style; ?map=offline selects the local, India-PBF-derived demo-region data. */


(function () {
  const OPENFREEMAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty';
  const LOCAL_BOUNDS = [[74.7, 22.2], [76.4, 23.8]];
  const START = [75.8247, 22.7774];
  const EMPTY = { type: 'FeatureCollection', features: [] };
  const OSM_FILES = {
    majorRoads: 'roads-major.geojson', water: 'water.geojson',
    boundaries: 'boundaries.geojson', context: 'context.geojson',
    majorPlaces: 'places-major.geojson', localRoads: 'roads-local.geojson',
    localPlaces: 'places-local.geojson'
  };
  const geometryCache = new Map();

  function fileUrl(path) { return new URL(path, document.baseURI).href; }
  function loadGeoJSON(filename) {
    if (!geometryCache.has(filename)) {
      geometryCache.set(filename, fetch(fileUrl(`assets/osm/${filename}`)).then(response => {
        if (!response.ok) throw new Error(`${response.status} while loading ${filename}`);
        return response.json();
      }).catch(error => { geometryCache.delete(filename); throw error; }));
    }
    return geometryCache.get(filename);
  }
  function offlineStyle() {
    const data = name => fileUrl(`assets/osm/${name}`);
    return {
      version: 8,
      name: 'AVLOKAN local light map',
      sources: {
        'avlo-roads-major': { type: 'geojson', data: data(OSM_FILES.majorRoads), maxzoom: 14 },
        'avlo-water': { type: 'geojson', data: data(OSM_FILES.water), maxzoom: 14 },
        'avlo-boundaries': { type: 'geojson', data: data(OSM_FILES.boundaries), maxzoom: 14 },
        'avlo-context': { type: 'geojson', data: data(OSM_FILES.context), maxzoom: 14 },
        'avlo-satellite': { type: 'raster', tiles: [fileUrl('assets/map-tiles/{z}/{x}/{y}.png')],
          tileSize: 256, minzoom: 7, maxzoom: 14, bounds: [74.7, 22.2, 76.4, 23.8],
          attribution: 'Local Sentinel-2 imagery · Copernicus Sentinel data' }
      },
      layers: [
        { id: 'avlo-background', type: 'background', paint: { 'background-color': '#f5f7f6' } },
        { id: 'avlo-context-fill', type: 'fill', source: 'avlo-context',
          paint: { 'fill-color': ['match', ['coalesce', ['get', 'landuse'], ['get', 'natural']],
            'forest', '#e3ede4', 'wood', '#e3ede4', 'park', '#e6efe5', 'grass', '#eaf0e6', '#eef0ed'],
            'fill-outline-color': '#dce3df', 'fill-opacity': 0.58 } },
        { id: 'avlo-water-fill', type: 'fill', source: 'avlo-water', filter: ['==', ['geometry-type'], 'Polygon'],
          paint: { 'fill-color': '#d9e8f1', 'fill-outline-color': '#b8d0df', 'fill-opacity': 0.88 } },
        { id: 'avlo-water-lines', type: 'line', source: 'avlo-water', filter: ['!=', ['geometry-type'], 'Polygon'],
          paint: { 'line-color': '#a9c7d9', 'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.7, 12, 1.5, 14, 2] } },
        { id: 'avlo-boundary-lines', type: 'line', source: 'avlo-boundaries',
          paint: { 'line-color': '#9daeb5', 'line-width': 0.85, 'line-opacity': 0.62, 'line-dasharray': [2, 2] } },
        { id: 'avlo-roads-major', type: 'line', source: 'avlo-roads-major',
          paint: { 'line-color': ['match', ['get', 'highway'], ['motorway', 'motorway_link'], '#d8a76f',
            ['trunk', 'trunk_link'], '#d1aa7c', ['primary', 'primary_link'], '#c3cbd0',
            ['secondary', 'secondary_link'], '#d0d5d8', '#d7dcde'],
            'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.45, 9, 0.9, 12, 1.55, 14, 2.1],
            'line-opacity': 0.92 } },
        { id: 'avlo-satellite-layer', type: 'raster', source: 'avlo-satellite',
          layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.78, 'raster-fade-duration': 0 } }
      ],
      // MapLibre's built-in attribution control displays these local credits.
      metadata: { attribution: '© OpenStreetMap contributors' }
    };
  }
  function pointFeature(point, kind, index) {
    let coordinates = point.geometry?.type === 'Point' ? point.geometry.coordinates : null;
    if (!coordinates && Number.isFinite(Number(point.lng)) && Number.isFinite(Number(point.lat)))
      coordinates = [Number(point.lng), Number(point.lat)];
    if (!coordinates || !coordinates.every(Number.isFinite)) return null;
    return { type: 'Feature', id: index, geometry: { type: 'Point', coordinates }, properties: {
      kind, label: point.name || point.location || point.region || point.id || '',
      id: point.id || point.scene_id || '', date: point.date || '',
      lat: coordinates[1], lng: coordinates[0]
    } };
  }
  function bboxFeature(bbox, properties = {}) {
    if (!Array.isArray(bbox) || bbox.length < 4) return null;
    const [w, s, e, n] = bbox.map(Number);
    if (![w, s, e, n].every(Number.isFinite) || w >= e || s >= n) return null;
    return { type: 'Feature', properties, geometry: { type: 'Polygon', coordinates: [[[w,s],[e,s],[e,n],[w,n],[w,s]]] } };
  }
  function geometryFeature(item, properties = {}) {
    if (item?.type === 'Feature') return { ...item, properties: { ...(item.properties || {}), ...properties } };
    if (item?.type && item?.coordinates) return { type: 'Feature', properties, geometry: item };
    if (item?.geometry?.type) return { type: 'Feature', properties: { ...(item.properties || {}), ...properties }, geometry: item.geometry };
    return null;
  }
  function circlePolygon(lng, lat, radiusKm, steps = 48) {
    const coordinates = [];
    for (let i = 0; i <= steps; i++) {
      const bearing = 2 * Math.PI * i / steps;
      const dy = radiusKm / 111.32 * Math.cos(bearing);
      const dx = radiusKm / (111.32 * Math.max(0.05, Math.cos(lat * Math.PI / 180))) * Math.sin(bearing);
      coordinates.push([lng + dx, lat + dy]);
    }
    return { type: 'Polygon', coordinates: [coordinates] };
  }
  function setData(map, id, collection) {
    const source = map.getSource(id);
    if (source) source.setData(collection);
  }
  function addGeoSource(map, id) {
    if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: EMPTY });
  }
  function addAppLayers(map) {
    const firstSymbol = (map.getStyle().layers || []).find(layer => layer.type === 'symbol')?.id;
    if (!map.getSource('avlo-satellite')) {
      map.addSource('avlo-satellite', { type: 'raster', tiles: [fileUrl('assets/map-tiles/{z}/{x}/{y}.png')],
        tileSize: 256, minzoom: 7, maxzoom: 14, bounds: [74.7,22.2,76.4,23.8],
        attribution: 'Local Sentinel-2 imagery · Copernicus Sentinel data' });
    }
    if (!map.getLayer('avlo-satellite-layer')) map.addLayer({ id: 'avlo-satellite-layer', type: 'raster', source: 'avlo-satellite',
      layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.78, 'raster-fade-duration': 0 } }, firstSymbol);
    ['avlo-aoi','avlo-scenes','avlo-pin','avlo-markers','avlo-candidates'].forEach(id => addGeoSource(map, id));
    const layers = [
      { id: 'avlo-aoi-fill', type: 'fill', source: 'avlo-aoi', filter: ['==',['geometry-type'],'Polygon'],
        paint: { 'fill-color': '#18a3a7', 'fill-opacity': 0.1 } },
      { id: 'avlo-aoi-line', type: 'line', source: 'avlo-aoi',
        paint: { 'line-color': '#087f87', 'line-width': 2, 'line-dasharray': [2.5,1.6] } },
      { id: 'avlo-aoi-point', type: 'circle', source: 'avlo-aoi', filter: ['==',['geometry-type'],'Point'],
        paint: { 'circle-radius': 6, 'circle-color': '#ffffff', 'circle-stroke-color': '#087f87', 'circle-stroke-width': 2.5 } },
      { id: 'avlo-scenes-fill', type: 'fill', source: 'avlo-scenes', filter: ['==',['geometry-type'],'Polygon'],
        paint: { 'fill-color': ['match',['get','role'],'T1','#1594a0','T2','#d8913d','#627f9b'],
          'fill-opacity': ['case',['get','selected'],0.2,0.07] } },
      { id: 'avlo-scenes-line', type: 'line', source: 'avlo-scenes', filter: ['==',['geometry-type'],'Polygon'],
        paint: { 'line-color': ['match',['get','role'],'T1','#087f87','T2','#bd772f','#526d88'],
          'line-width': ['case',['get','selected'],3,1.5] } },
      { id: 'avlo-candidate-fill', type: 'fill', source: 'avlo-candidates', filter: ['==',['geometry-type'],'Polygon'],
        paint: { 'fill-color': '#ed5a43', 'fill-opacity': 0.28 } },
      { id: 'avlo-candidate-line', type: 'line', source: 'avlo-candidates',
        paint: { 'line-color': '#c94032', 'line-width': 2.5 } },
      { id: 'avlo-pin-fill', type: 'fill', source: 'avlo-pin', filter: ['==',['geometry-type'],'Polygon'],
        paint: { 'fill-color': '#e0a64c', 'fill-opacity': 0.05 } },
      { id: 'avlo-pin-line', type: 'line', source: 'avlo-pin', filter: ['==',['geometry-type'],'Polygon'],
        paint: { 'line-color': '#bb7c22', 'line-width': 2, 'line-dasharray': [2,1.5] } },
      { id: 'avlo-pin-point', type: 'circle', source: 'avlo-pin', filter: ['==',['geometry-type'],'Point'],
        paint: { 'circle-radius': 6, 'circle-color': '#ffffff', 'circle-stroke-color': '#b46f18', 'circle-stroke-width': 2.5 } },
      { id: 'avlo-marker-circles', type: 'circle', source: 'avlo-markers',
        paint: { 'circle-radius': ['match',['get','kind'],'selected',8,'similar',6,6],
          'circle-color': ['match',['get','kind'],'selected','#e35e48','similar','#c68943','#198c9a'],
          'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.8 } },
      { id: 'avlo-marker-labels', type: 'symbol', source: 'avlo-markers', minzoom: 8,
        layout: { 'text-field': ['get','label'], 'text-font': ['Noto Sans Regular'], 'text-size': 11,
          'text-offset': [0,1.2], 'text-anchor': 'top', 'text-allow-overlap': false, 'icon-allow-overlap': false },
        paint: { 'text-color': '#465761', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 } }
    ];
    layers.forEach(layer => { if (!map.getLayer(layer.id)) map.addLayer(layer); });
    if (!map.getLayer('avlo-scenes-labels') && map.getStyle().glyphs) map.addLayer({
      id: 'avlo-scenes-labels', type: 'symbol', source: 'avlo-scenes', minzoom: 8,
      layout: { 'text-field': ['get','label'], 'text-font': ['Noto Sans Regular'], 'text-size': 11,
        'text-allow-overlap': false, 'icon-allow-overlap': false },
      paint: { 'text-color': '#40545f', 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 }
    });
    if (map.getLayer('avlo-aoi-fill') && map.getLayer('avlo-pin-fill')) {
      ['avlo-aoi-fill','avlo-aoi-line','avlo-aoi-point'].forEach(id => {
        if (map.getLayer(id)) map.moveLayer(id,'avlo-pin-fill');
      });
    }
  }
  function tunePositronLabels(map) {
    const rules = {
      label_other: { visibility: 'none' },
      label_village: { minzoom: 12 },
      label_town: { minzoom: 9 },
      label_city: { minzoom: 6 },
      label_city_capital: { minzoom: 6 },
      waterway_line_label: { minzoom: 12 },
      water_name_line_label: { minzoom: 12 },
      water_name_point_label: { minzoom: 11 },
      'highway-name-path': { minzoom: 17 },
      'highway-name-minor': { minzoom: 16 },
      'highway-name-major': { minzoom: 14 },
      'highway-shield-non-us': { minzoom: 12 },
      'highway-shield-us-interstate': { minzoom: 12 },
      road_shield_us: { minzoom: 12 },
      airport: { minzoom: 12 }
    };
    Object.entries(rules).forEach(([id, rule]) => {
      if (!map.getLayer(id)) return;
      if (rule.visibility) map.setLayoutProperty(id, 'visibility', rule.visibility);
      if (rule.minzoom != null) map.setLayerZoomRange(id, rule.minzoom, map.getStyle().layers.find(layer => layer.id === id)?.maxzoom ?? 24);
    });
    (map.getStyle().layers || []).filter(layer => layer.type === 'symbol').forEach(layer => {
      if (layer.layout?.['text-field']) map.setLayoutProperty(layer.id, 'text-allow-overlap', false);
      if (layer.layout?.['icon-image']) map.setLayoutProperty(layer.id, 'icon-allow-overlap', false);
    });
  }
  function addLocalDetail(map) {
    if (map.__avloDetailLoading || map.__avloDetailReady || map.getZoom() < 12) return;
    map.__avloDetailLoading = true;
    Promise.all([loadGeoJSON(OSM_FILES.localRoads), loadGeoJSON(OSM_FILES.localPlaces)]).then(([roads, places]) => {
      if (!map.getSource('avlo-roads-local')) map.addSource('avlo-roads-local', { type: 'geojson', data: roads, maxzoom: 14 });
      if (!map.getLayer('avlo-roads-local')) map.addLayer({ id: 'avlo-roads-local', type: 'line', source: 'avlo-roads-local', minzoom: 12,
        paint: { 'line-color': '#cbd2d5', 'line-width': ['interpolate',['linear'],['zoom'],12,0.45,14,1.25], 'line-opacity': 0.8 } }, 'avlo-aoi-fill');
      map.__avloLocalPlaces = places.features || [];
      map.__avloDetailReady = true;
      syncPlaceLabels(map);
    }).catch(error => { console.warn('Local detail overlay unavailable:', error); map.__avloDetailLoading = false; });
  }
  function addPlaceMarkers(map) {
    if (map.__avloMajorPlacesLoading || map.__avloMajorPlaces) return;
    map.__avloMajorPlacesLoading = true;
    loadGeoJSON(OSM_FILES.majorPlaces).then(data => {
      map.__avloMajorPlaces = data.features || [];
      syncPlaceLabels(map);
    }).catch(error => console.warn('Local place labels unavailable:', error));
  }
  function syncPlaceLabels(map) {
    if (!maplibregl.Marker) return;
    if (map.__avloLabelsEnabled === false) {
      (map.__avloPlaceMarkers || []).forEach(marker => marker.remove());
      map.__avloPlaceMarkers = [];
      return;
    }
    const zoom = map.getZoom(), bounds = map.getBounds();
    const all = [...(map.__avloMajorPlaces || []), ...(zoom >= 12 ? map.__avloLocalPlaces || [] : [])];
    const candidates = all.map(feature => {
      const p = feature.properties || {}, c = feature.geometry?.coordinates;
      const name = p.name || p['name:en'];
      if (!name || !c || !bounds.contains(c)) return null;
      const rank = p.place === 'city' ? 0 : p.place === 'town' ? 1 : p.place === 'village' ? 2 : 3;
      const minZoom = p.place === 'city' ? 7 : p.place === 'town' ? 9 : p.place === 'village' ? 12 : 99;
      return zoom >= minZoom ? { c, name, rank } : null;
    }).filter(Boolean).sort((a,b) => a.rank-b.rank || a.name.localeCompare(b.name));
    const spacing = zoom < 9 ? 170 : zoom < 11 ? 140 : zoom < 13 ? 105 : zoom < 15 ? 78 : 62;
    const occupied = new Set(), visible = [];
    candidates.forEach(item => {
      const point = map.project(item.c), x = Math.floor(point.x/spacing), y = Math.floor(point.y/spacing);
      let conflict = false;
      for (let dx=-1;dx<=1&&!conflict;dx++) for (let dy=-1;dy<=1;dy++) if (occupied.has(`${x+dx}:${y+dy}`)) { conflict=true; break; }
      if (!conflict) { occupied.add(`${x}:${y}`); visible.push(item); }
    });
    const previous = map.__avloPlaceMarkers || [];
    previous.forEach(marker => marker.remove());
    map.__avloPlaceMarkers = visible.map(item => {
      const element = document.createElement('div');
      element.className = `avlo-map-label${item.rank < 2 ? ' is-major' : ''}`;
      element.textContent = item.name;
      element.setAttribute('aria-label', item.name);
      return new maplibregl.Marker({ element, anchor: 'bottom', offset: [0, -4] }).setLngLat(item.c).addTo(map);
    });
  }
  function candidateCollection(features) {
    return { type: 'FeatureCollection', features: (features || []).map((item, index) => geometryFeature(item, { candidateIndex:index })).filter(Boolean) };
  }
  function mapMode() {
    return String(window.AVLOKAN_MAP_MODE || new URLSearchParams(location.search).get('map') || 'openfreemap').toLowerCase();
  }

  window.createAvlokanMap = function (options = {}) {
    const container = typeof options.container === 'string' ? document.getElementById(options.container) : options.container;
    if (!container || !window.maplibregl || container._avlokanMap) return container?._avlokanMap || null;
    const mode = mapMode() === 'offline' ? 'offline' : 'openfreemap';
    const modeBadge = container.closest('.panel')?.querySelector('.mh-live');
    if (modeBadge) modeBadge.innerHTML = `<span class="dot"></span>${mode === 'offline' ? 'OFFLINE' : 'OPENFREEMAP'}`;
    const map = new maplibregl.Map({
      container,
      style: mode === 'offline' ? offlineStyle() : OPENFREEMAP_STYLE,
      center: options.center ? [options.center[1], options.center[0]] : START,
      zoom: options.zoom || 9,
      minZoom: mode === 'offline' ? 7 : 4,
      maxZoom: mode === 'offline' ? 14 : 20,
      maxBounds: mode === 'offline' ? LOCAL_BOUNDS : undefined,
      attributionControl: { compact: true },
      customAttribution: mode === 'offline' ? [String.fromCharCode(169)+' OpenStreetMap contributors'] : []
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }), 'top-right');
    const state = { aoi: [], scenes: [], candidates: EMPTY, markers: EMPTY, pin: EMPTY, selectedScene: null,
      satellite: false, registry: true, labels: true, loaded: false, pinLayer: null, analysisBounds: null };
    const bounds = mode === 'offline' ? LOCAL_BOUNDS : null;
    function renderState() {
      if (!state.loaded || !map.getSource('avlo-aoi')) return;
      setData(map, 'avlo-aoi', { type:'FeatureCollection', features:state.aoi });
      setData(map, 'avlo-scenes', { type:'FeatureCollection', features:state.scenes });
      setData(map, 'avlo-candidates', state.candidates);
      setData(map, 'avlo-markers', state.markers);
      setData(map, 'avlo-pin', state.pin);
      map.setLayoutProperty('avlo-aoi-fill','visibility',state.registry?'visible':'none');
      map.setLayoutProperty('avlo-aoi-line','visibility',state.registry?'visible':'none');
      map.setLayoutProperty('avlo-aoi-point','visibility',state.registry?'visible':'none');
      if (map.getLayer('avlo-scenes-labels')) map.setLayoutProperty('avlo-scenes-labels','visibility',state.labels?'visible':'none');
      map.setLayoutProperty('avlo-marker-labels','visibility',state.labels?'visible':'none');
      map.__avloLabelsEnabled = state.labels;
    }
    function renderAois(items) {
      state.aoi = (items || []).flatMap((item,index) => {
        const lat=Number(item.lat),lng=Number(item.lng),radius=Number(item.radius_km??item.rad);
        if (!Number.isFinite(lat)||!Number.isFinite(lng)) return [];
        const point={type:'Feature',geometry:{type:'Point',coordinates:[lng,lat]},properties:{id:item.id||'',name:item.name||'',radius_km:radius}};
        const polygon=radius>0?{type:'Feature',geometry:circlePolygon(lng,lat,radius),properties:{id:item.id||'',name:item.name||'',kind:'radius'}}:null;
        return polygon?[polygon,point]:[point];
      });
      renderState();
    }
    function scenesCollection(items) {
      return (items || []).map((scene,index) => {
        let feature=geometryFeature(scene.footprint,{});
        if (!feature) feature=bboxFeature(scene.bbox,{});
        if (!feature) return null;
        const role=String(scene.observation_role||'').toUpperCase().startsWith('T1')?'T1':
          String(scene.observation_role||'').toUpperCase().startsWith('T2')?'T2':'SCENE';
        feature.properties={...(feature.properties||{}),id:scene.id||'',role,
          prototype:scene.record_type==='prototype_analysis_ready',selected:index===state.selectedScene,
          label:`${role==='SCENE'?'Scene':role} · ${scene.id||'unnamed'}`,index};
        return feature;
      }).filter(Boolean);
    }
    function onStyleReady() {
      if (mode === 'openfreemap') tunePositronLabels(map);
      addAppLayers(map);
      state.loaded=true;
      map.setLayoutProperty('avlo-satellite-layer','visibility',state.satellite?'visible':'none');
      renderState();
      addPlaceMarkers(map);
      map.on('zoomend',()=>{ if(mode==='offline')addLocalDetail(map); syncPlaceLabels(map); });
      map.on('moveend',()=>{ if(mode==='offline')addLocalDetail(map); syncPlaceLabels(map); });
      map.on('click','avlo-aoi-point',event=>{
        const p=event.features?.[0]?.properties;if(p&&options.onPinHit)options.onPinHit({id:p.id,name:p.name,lat:p.lat||event.lngLat.lat,lng:p.lng||event.lngLat.lng,radius_km:p.radius_km});
      });
      ['avlo-scenes-line','avlo-scenes-fill'].forEach(layer=>map.on('click',layer,event=>{
        const index=Number(event.features?.[0]?.properties?.index);if(Number.isFinite(index)&&options.onSceneHit)options.onSceneHit(api.scenes?.[index],index);
      }));
      map.on('click','avlo-marker-circles',event=>{
        const p=event.features?.[0]?.properties;if(p&&options.onMarkerHit){event.preventDefault();options.onMarkerHit(p);}
      });
      if(mode==='offline'&&map.getZoom()>=12)addLocalDetail(map);
    }
    map.on('load',onStyleReady);
    map.on('mousemove',event=>{
      const target=options.coordsEl&&document.getElementById(options.coordsEl);
      if(target)target.textContent=`${Math.abs(event.lngLat.lat).toFixed(4)}°${event.lngLat.lat>=0?'N':'S'}  ${Math.abs(event.lngLat.lng).toFixed(4)}°${event.lngLat.lng>=0?'E':'W'}`;
    });
    map.on('click',event=>{ if(options.onPick)options.onPick(event.lngLat.lat,event.lngLat.lng); });
    map.on('error',event=>{ if(event.error&&options.onTileError)options.onTileError(event.error); });
    const api={
      map, mode, scenes:[],
      tileLayer:{setOpacity(value){state.satellite=Number(value)>0;if(state.loaded)map.setLayoutProperty('avlo-satellite-layer','visibility',state.satellite?'visible':'none');}},
      setAOIs(items){renderAois(items);},
      setAOIGeometry(geometry){const feature=geometry?.type==='bbox'?bboxFeature(geometry.coordinates,{name:'Selected AOI',kind:'aoi'}):geometryFeature(geometry,{name:'Selected AOI',kind:'aoi'});if(feature){state.aoi=[feature];renderState();}},
      setScenes(items){api.scenes=items||[];state.selectedScene=null;state.scenes=scenesCollection(api.scenes);renderState();},
      setAnalysisOverlay(t2Url,heatmapUrl,bbox,opacity=.72){
        if(!state.loaded||!t2Url||!heatmapUrl||!Array.isArray(bbox)||bbox.length!==4)return false;
        const [west,south,east,north]=bbox.map(Number);
        if(![west,south,east,north].every(Number.isFinite)||west>=east||south>=north)return false;
        const coordinates=[[west,north],[east,north],[east,south],[west,south]];
        this.clearAnalysisOverlay();
        try {
          const dLat = north - south;
          const dLng = east - west;
          const contextTiles = [
            {
              key: 'northwest',
              url: fileUrl('assets/context-tiles/context_northwest.jpg'),
              coordinates: [
                [west - dLng, north + dLat],
                [west, north + dLat],
                [west, north],
                [west - dLng, north]
              ]
            },
            {
              key: 'north',
              url: fileUrl('assets/context-tiles/context_north.jpg'),
              coordinates: [
                [west, north + dLat],
                [east, north + dLat],
                [east, north],
                [west, north]
              ]
            },
            {
              key: 'northeast',
              url: fileUrl('assets/context-tiles/context_northeast.jpg'),
              coordinates: [
                [east, north + dLat],
                [east + dLng, north + dLat],
                [east + dLng, north],
                [east, north]
              ]
            },
            {
              key: 'west',
              url: fileUrl('assets/context-tiles/context_west.jpg'),
              coordinates: [
                [west - dLng, north],
                [west, north],
                [west, south],
                [west - dLng, south]
              ]
            },
            {
              key: 'east',
              url: fileUrl('assets/context-tiles/context_east.jpg'),
              coordinates: [
                [east, north],
                [east + dLng, north],
                [east + dLng, south],
                [east, south]
              ]
            },
            {
              key: 'southwest',
              url: fileUrl('assets/context-tiles/context_southwest.jpg'),
              coordinates: [
                [west - dLng, south],
                [west, south],
                [west, south - dLat],
                [west - dLng, south - dLat]
              ]
            },
            {
              key: 'south',
              url: fileUrl('assets/context-tiles/context_south.jpg'),
              coordinates: [
                [west, south],
                [east, south],
                [east, south - dLat],
                [west, south - dLat]
              ]
            },
            {
              key: 'southeast',
              url: fileUrl('assets/context-tiles/context_southeast.jpg'),
              coordinates: [
                [east, south],
                [east + dLng, south],
                [east + dLng, south - dLat],
                [east, south - dLat]
              ]
            }
          ];
          contextTiles.forEach(tile => {
            const sourceId = `avlo-context-tile-${tile.key}-source`;
            const layerId = `avlo-context-tile-${tile.key}-layer`;
            if (!map.getSource(sourceId)) {
              map.addSource(sourceId, { type: 'image', url: tile.url, coordinates: tile.coordinates });
            }
            if (!map.getLayer(layerId)) {
              map.addLayer({
                id: layerId,
                type: 'raster',
                source: sourceId,
                paint: { 'raster-opacity': 1, 'raster-fade-duration': 0 }
              }, 'avlo-candidate-fill');
            }
          });
        } catch (ctxErr) {
          console.warn('Surrounding satellite context tiles could not be loaded:', ctxErr);
        }
        map.addSource('avlo-analysis-t2',{type:'image',url:t2Url,coordinates});
        map.addLayer({id:'avlo-analysis-t2-layer',type:'raster',source:'avlo-analysis-t2',paint:{'raster-opacity':1,'raster-fade-duration':0}},'avlo-candidate-fill');
        map.addSource('avlo-analysis-heatmap',{type:'image',url:heatmapUrl,coordinates});
        map.addLayer({id:'avlo-analysis-heatmap-layer',type:'raster',source:'avlo-analysis-heatmap',metadata:{'avlokan:display-name':'Change Probability Heatmap'},paint:{'raster-opacity':opacity,'raster-fade-duration':0}},'avlo-candidate-fill');
        state.analysisBounds=[[west,south],[east,north]];
        this.ensureAnalysisControl();this.toggleAnalysisOverlay(true);
        this.focusAnalysisOverlay();
        return true;
      },
      ensureAnalysisControl(){
        let control=container.querySelector('.map-probability-control');
        if(!control){control=document.createElement('label');control.className='map-probability-control';control.innerHTML='<input type="checkbox" checked aria-label="Toggle Change Heatmap"><span>Change Heatmap</span>';control.querySelector('input').addEventListener('change',event=>window.toggleChangeHeatmapFromMap?.(event.target.checked));container.appendChild(control);}
        control.hidden=false;
      },
      toggleAnalysisOverlay(visible){
        if(map.getLayer('avlo-analysis-heatmap-layer'))map.setLayoutProperty('avlo-analysis-heatmap-layer','visibility',visible?'visible':'none');
        const checkbox=container.querySelector('.map-probability-control input');if(checkbox)checkbox.checked=!!visible;
      },
      clearAnalysisOverlay(){
        const contextKeys = ['northwest','north','northeast','west','east','southwest','south','southeast'];
        ['avlo-analysis-heatmap-layer','avlo-analysis-t2-layer',
         ...contextKeys.map(k=>`avlo-context-tile-${k}-layer`),
         'avlo-context-tile-north-layer','avlo-context-tile-east-layer','avlo-context-tile-south-layer'
        ].forEach(id=>{if(map.getLayer(id))map.removeLayer(id);});
        ['avlo-analysis-heatmap','avlo-analysis-t2',
         ...contextKeys.map(k=>`avlo-context-tile-${k}-source`),
         'avlo-context-tile-north','avlo-context-tile-east','avlo-context-tile-south'
        ].forEach(id=>{if(map.getSource(id))map.removeSource(id);});
      },
      focusAnalysisOverlay(){if(state.analysisBounds&&container.clientWidth&&container.clientHeight)map.fitBounds(state.analysisBounds,{padding:64,maxZoom:13,duration:0});},
      setCandidates(features){state.candidates=candidateCollection(features);renderState();},
      setSelectedResult(item){const feature=pointFeature(item,'selected',0);state.markers=feature?{type:'FeatureCollection',features:[feature]}:EMPTY;renderState();if(feature)this.flyTo(feature.geometry.coordinates[1],feature.geometry.coordinates[0],12);},
      setSearchResults(items){state.markers={type:'FeatureCollection',features:(items||[]).map((item,i)=>pointFeature(item,'search',i)).filter(Boolean)};renderState();},
      setSimilarSites(items){state.markers={type:'FeatureCollection',features:(items||[]).map((item,i)=>pointFeature({...item,name:item.location||item.name},'similar',i)).filter(Boolean)};renderState();},
      setPin(point){
        if(!point||!Number.isFinite(Number(point.lat))||!Number.isFinite(Number(point.lng)))return;
        const lat=Number(point.lat),lng=Number(point.lng),radius=Number(point.rad||point.radius_km||3);
        state.pin={type:'FeatureCollection',features:[
          {type:'Feature',geometry:{type:'Point',coordinates:[lng,lat]},properties:{kind:'investigation',label:point.name||'Investigation'}},
          {type:'Feature',geometry:circlePolygon(lng,lat,radius),properties:{kind:'radius'}}]};renderState();
      },
      clearPin(){state.pin=EMPTY;renderState();},
      selectScene(index){state.selectedScene=index;state.scenes=scenesCollection(api.scenes);renderState();const feature=state.scenes[index];if(feature){const b=new maplibregl.LngLatBounds();(function addCoords(coords){if(typeof coords[0]==='number')b.extend(coords);else coords.forEach(addCoords)})(feature.geometry.coordinates);map.fitBounds(b,{padding:24,maxZoom:12});}},
      flyTo(lat,lng,zoom){if(Number.isFinite(Number(lat))&&Number.isFinite(Number(lng)))map.flyTo({center:[Number(lng),Number(lat)],zoom:zoom||map.getZoom()});},
      zoom(delta){map.setZoom(Math.max(mode==='offline'?7:4,Math.min(mode==='offline'?14:20,map.getZoom()+delta)));},
      home(){if(mode==='offline')map.fitBounds(LOCAL_BOUNDS,{padding:22});else map.flyTo({center:START,zoom:9});},
      toggle(key){if(key==='registry')state.registry=!state.registry;else if(key==='labels')state.labels=!state.labels;else if(key==='optical'||key==='satellite'){state.satellite=!state.satellite;if(state.loaded)map.setLayoutProperty('avlo-satellite-layer','visibility',state.satellite?'visible':'none');return state.satellite;}renderState();if(key==='labels')syncPlaceLabels(map);return key==='registry'?state.registry:state.labels;},
      toggleSatellite(value){state.satellite=typeof value==='boolean'?value:!state.satellite;if(state.loaded)map.setLayoutProperty('avlo-satellite-layer','visibility',state.satellite?'visible':'none');return state.satellite;},
      invalidate(){map.resize();},
      getBounds(){const b=map.getBounds();return[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()];}
    };
    container._avlokanMap=api;
    return api;
  };
  window.AVLOKAN_MAP_MODE=mapMode();
  window.AVLOKAN_MAP_OPENFREEMAP_STYLE=OPENFREEMAP_STYLE;
})();
