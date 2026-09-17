/**
 * Service map bootstrap.
 * Loads the SoCal cities GeoJSON from /data/socal-cities.geojson,
 * joins it with the CMS-managed city list from window.__BUCKNAM_CITIES__,
 * and renders coloured polygons per customer / active-survey status.
 */
import * as L from 'https://esm.sh/leaflet@1.9.4';

const MAP_CENTER = [33.95, -117.4];
const MAP_ZOOM = 8;

// Every city in the CMS list is a customer. Customers default to blue;
// the "Survey this year" toggle turns them green. Non-customers stay hidden.
const styleFor = (match) => {
  if (!match) return { color: '#888', weight: 1, fillOpacity: 0, opacity: 0 };
  if (match.isCustomer) {
    return { color: '#15803d', weight: 2, fillColor: '#22c55e', fillOpacity: 0.55 };
  }
  return { color: '#1d4ed8', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.45 };
};

async function run() {
  const map = L.map('service-map', { maxZoom: 16 }).setView(MAP_CENTER, MAP_ZOOM);
  // Esri World Light Gray Canvas — keyless. CARTO's free basemaps started
  // stamping "API KEY REQUIRED" on every tile (Sept 2026), so we moved off them.
  // Base = land/water/roads; Reference = place labels, drawn above the polygons
  // so city names stay readable over the coloured fills.
  const esri = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas';
  const esriAttribution = 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ';
  L.tileLayer(`${esri}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {
    attribution: esriAttribution,
    maxZoom: 16,
  }).addTo(map);
  map.createPane('labels');
  map.getPane('labels').style.zIndex = 450;
  map.getPane('labels').style.pointerEvents = 'none';
  L.tileLayer(`${esri}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`, {
    pane: 'labels',
    maxZoom: 16,
  }).addTo(map);

  const cities = window.__BUCKNAM_CITIES__ || [];
  const fy = window.__BUCKNAM_FY__;

  // Index CMS data by place GEOID (preferred) or by normalised name
  const byGeoId = new Map();
  const byName = new Map();
  for (const c of cities) {
    if (c.placeGeoId) byGeoId.set(c.placeGeoId, c);
    byName.set(c.name.toLowerCase().trim(), c);
  }

  // County outlines (background context)
  try {
    const countyResp = await fetch('/data/socal-counties.geojson');
    if (countyResp.ok) {
      const countyData = await countyResp.json();
      L.geoJSON(countyData, {
        style: { color: '#666', weight: 2, fillOpacity: 0, dashArray: '4 4' },
        interactive: false,
      }).addTo(map);
    }
  } catch (e) { /* counties are optional */ }

  // TIGER cities
  let placesData;
  try {
    const resp = await fetch('/data/socal-cities.geojson');
    placesData = await resp.json();
  } catch (e) {
    console.error('Failed to load socal-cities.geojson', e);
    return;
  }

  L.geoJSON(placesData, {
    style: (feature) => {
      const geoid = feature.properties.GEOID || feature.properties.geoid;
      const name = (feature.properties.NAME || feature.properties.name || '').toLowerCase().trim();
      const match = byGeoId.get(geoid) || byName.get(name);
      return styleFor(match);
    },
    onEachFeature: (feature, layer) => {
      const geoid = feature.properties.GEOID || feature.properties.geoid;
      const name = feature.properties.NAME || feature.properties.name;
      const match = byGeoId.get(geoid) || byName.get((name || '').toLowerCase().trim());
      const status = match
        ? (match.isCustomer ? `Surveying FY${fy}` : 'Customer')
        : '';
      const popup = `<strong>${name}</strong><br/><span style="color:#666">${feature.properties.county || match?.county || ''}</span>${status ? `<br/><span style="color:#059669;font-weight:600">${status}</span>` : ''}`;
      layer.bindPopup(popup);
    },
  }).addTo(map);

  // Custom (non-TIGER) HOA/special-district polygons
  for (const c of cities) {
    if (c.customGeoJson) {
      L.geoJSON(c.customGeoJson, {
        style: styleFor(c),
      }).bindPopup(`<strong>${c.name}</strong>`).addTo(map);
    }
  }
}

run();
