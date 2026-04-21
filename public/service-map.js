/**
 * Service map bootstrap.
 * Loads the SoCal cities GeoJSON from /data/socal-cities.geojson,
 * joins it with the CMS-managed city list from window.__BUCKNAM_CITIES__,
 * and renders coloured polygons per customer / active-survey status.
 */
import * as L from 'https://esm.sh/leaflet@1.9.4';

const MAP_CENTER = [33.95, -117.4];
const MAP_ZOOM = 8;

const styleFor = (match) => {
  if (!match) return { color: '#888', weight: 1, fillOpacity: 0, opacity: 0 };
  if (match.isCurrentSurvey) {
    return { color: '#15803d', weight: 2, fillColor: '#22c55e', fillOpacity: 0.55 };
  }
  if (match.isCustomer) {
    return { color: '#1d4ed8', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.45 };
  }
  return { color: '#999', weight: 1, fillColor: '#bbb', fillOpacity: 0.05 };
};

async function run() {
  const map = L.map('service-map').setView(MAP_CENTER, MAP_ZOOM);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 18,
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
        ? (match.isCurrentSurvey ? `Surveying FY${fy}` : (match.isCustomer ? 'Customer' : ''))
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
