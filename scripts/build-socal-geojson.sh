#!/usr/bin/env bash
# Build SoCal city + county GeoJSON from US Census TIGER/Line shapefiles.
# Output: public/data/socal-cities.geojson, public/data/socal-counties.geojson
#
# Requires: curl, unzip, npx mapshaper (installed as devDep)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA="$ROOT/public/data"
TMP="$ROOT/.tmp-tiger"
mkdir -p "$DATA" "$TMP"

# FIPS codes — California=06, SoCal counties:
#   LA=037, Orange=059, San Bernardino=071, Riverside=065, San Diego=073
SOCAL_COUNTY_FIPS="037 059 065 071 073"
SOCAL_EXPR='["037","059","065","071","073"].indexOf(this.properties.COUNTYFP) > -1'

# 1. Counties (CA) — filter to the 5 SoCal
if [ ! -f "$TMP/tl_2023_us_county.zip" ]; then
  echo "Downloading US counties..."
  curl -fsSL -o "$TMP/tl_2023_us_county.zip" \
    "https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip"
fi
(cd "$TMP" && unzip -o -q tl_2023_us_county.zip)

npx mapshaper "$TMP/tl_2023_us_county.shp" \
  -proj wgs84 \
  -filter 'STATEFP === "06" && ["037","059","065","071","073"].indexOf(COUNTYFP) > -1' \
  -simplify 5% keep-shapes \
  -each 'county = NAME' \
  -o format=geojson "$DATA/socal-counties.geojson"

# 2. Places (CA) — TIGER "place" is cities/towns/CDPs.
#    Places don't carry a COUNTYFP directly, so we spatial-join to counties.
if [ ! -f "$TMP/tl_2023_06_place.zip" ]; then
  echo "Downloading CA places..."
  curl -fsSL -o "$TMP/tl_2023_06_place.zip" \
    "https://www2.census.gov/geo/tiger/TIGER2023/PLACE/tl_2023_06_place.zip"
fi
(cd "$TMP" && unzip -o -q tl_2023_06_place.zip)

# Build a counties-only source for the join (all CA counties, not just SoCal)
npx mapshaper "$TMP/tl_2023_us_county.shp" \
  -proj wgs84 \
  -filter 'STATEFP === "06"' \
  -each 'county = NAME, countyFP = COUNTYFP' \
  -o format=geojson "$TMP/ca-counties.geojson" force

npx mapshaper "$TMP/tl_2023_06_place.shp" \
  -proj wgs84 \
  -join "$TMP/ca-counties.geojson" fields=county,countyFP calc='joinCount = count()' largest-overlap \
  -filter '["037","059","065","071","073"].indexOf(countyFP) > -1' \
  -simplify 5% keep-shapes \
  -each 'name = NAME, geoid = GEOID' \
  -filter-fields name,geoid,county,countyFP \
  -o format=geojson "$DATA/socal-cities.geojson"

echo "---"
echo "Output:"
ls -lah "$DATA"/*.geojson
echo ""
echo "City count:"
node -e "console.log(JSON.parse(require('fs').readFileSync('$DATA/socal-cities.geojson','utf8')).features.length)"
