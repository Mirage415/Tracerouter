// globe_cesium.js

// 如果你有 Cesium Ion Token，可放这里；否则用 open-source 切片服务见下方注释
// Cesium.Ion.defaultAccessToken = 'YOUR_CESIUM_ION_TOKEN';

// Global array to keep track of unique geographic points for which entities have been added.
// Each element: { lat: Number, lon: Number, entity: Cesium.Entity, probes: [probeData1, probeData2, ...] }
const uniquePointsData = [];

const viewer = new Cesium.Viewer('cesiumContainer', {
  imageryProvider: new Cesium.ArcGisMapServerImageryProvider({
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
  }),
  baseLayerPicker: false,
  geocoder: true,
  homeButton: false,
  sceneModePicker: false,
  timeline: false,
  animation: false,
  infoBox: true // 确保InfoBox是启用的
});

// 开启光照效果
viewer.scene.globe.enableLighting = true;

/**
* Adds or updates a point on the map for a given probe's geographic location.
* If a point already exists at this lat/lon, its description is updated with the new probe's info.
* Otherwise, a new point entity is created.
* @param {Object} probeData The probe data object from CSV (must include lat, lon).
* @param {Cesium.Color} col The color for the point if a new one is created.
*/
function addOrUpdatePoint(probeData, col) {
  const { lat, lon } = probeData;
  if (isNaN(lat) || isNaN(lon)) {
    console.warn('Skipping probe with invalid lat/lon:', probeData);
    return null; // Return null if point cannot be added
  }

  let existingPointEntry = uniquePointsData.find(p => p.lat === lat && p.lon === lon);

  if (existingPointEntry) {
    // Point already exists, add this probe's data to it and update description
    existingPointEntry.probes.push(probeData);
    // Update the entity's description
    const newDescription = buildDescriptionForPoint(existingPointEntry.probes);
    if (existingPointEntry.entity) {
      existingPointEntry.entity.description = newDescription;
      // 更新颜色优先级：紫色（起点）或红色（终点）优先于绿色（中间点）
      if (col === Cesium.Color.RED || col === Cesium.Color.PURPLE) {
        existingPointEntry.entity.point.color = col;
      }
    } else {
      console.warn("Found existing point entry without an entity reference", existingPointEntry);
    }
    return existingPointEntry.entity;
  } else {
    // New geographic point, create a new entity
    const newProbesList = [probeData];
    const descriptionHtml = buildDescriptionForPoint(newProbesList);

    const newEntity = viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat),
      point: {
        pixelSize: 10,
        color: col,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
      },
      description: descriptionHtml
    });

    uniquePointsData.push({ lat, lon, entity: newEntity, probes: newProbesList });
    return newEntity;
  }
}

/**
 * Builds an HTML description string for all probes at a given geographic point.
 * @param {Array<Object>} probesAtPoint Array of probe data objects.
 * @returns {string} HTML string for the Cesium InfoBox.
 */
function buildDescriptionForPoint(probesAtPoint) {
  if (!probesAtPoint || probesAtPoint.length === 0) return "No probe data available for this location.";

  // Assuming all probes at this point share the same lat/lon for the header
  const representativeProbe = probesAtPoint[0];
  let descriptionHtml = `<div style="max-height: 350px; overflow-y: auto; padding-right: 15px;">`;
  descriptionHtml += `<strong>Location: ${representativeProbe.lat.toFixed(5)}, ${representativeProbe.lon.toFixed(5)}</strong><br>`;
  descriptionHtml += `<i>Displaying ${probesAtPoint.length} probe(s) at this location.</i><hr>`;

  probesAtPoint.forEach((probe, idx) => {
    descriptionHtml += `<details style="margin-bottom: 10px;" ${idx === 0 ? 'open' : ''}>`; // Open first by default
    descriptionHtml += `<summary style="cursor: pointer;">`;
    descriptionHtml += `Hop: ${probe.hop}, Prot: ${probe.protocol}, Idx: ${probe.probe_index}`;
    if (probe.rtt) descriptionHtml += `, RTT: ${probe.rtt}ms`;
    if (probe.ip) descriptionHtml += `, From: ${probe.ip}`;
    else if (probe.from) descriptionHtml += `, From: ${probe.from}`;
    descriptionHtml += `</summary>`;
    descriptionHtml += `<table class="cesium-infoBox-defaultTable" style="margin-left: 20px; width: calc(100% - 25px); font-size: 0.9em;"><tbody>`;
    for (const key in probe) {
      if (probe.hasOwnProperty(key)) {
        if (['lat', 'lon', 'latitude', 'longitude'].includes(key.toLowerCase())) continue; // Basic geo info already in header
        const friendlyKey = key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
        descriptionHtml += `<tr><th style="width: 35%; padding: 2px;">${friendlyKey}</th><td style="padding: 2px;">${probe[key]}</td></tr>`;
      }
    }
    descriptionHtml += `</tbody></table></details>`;
  });
  descriptionHtml += '</div>';
  return descriptionHtml;
}


/**
 * Draws polyline arrows between a sequence of geographic points for a single route.
 * Duplicate line segments (identical start/end coordinates) are not drawn multiple times by this call.
 * @param {Array<{lat:Number, lon:Number}>} uniqueGeoPointsForRoute Array of unique geographic points for one route.
 */
function addPolylineForRoute(uniqueGeoPointsForRoute) {
  if (uniqueGeoPointsForRoute.length < 2) return;
  // This function will now use a local 'drawnSegments' for this specific route to avoid self-intersections or back-and-forth on the same segment for THIS route only.
  // Global de-duplication was removed earlier.
  const drawnSegmentsThisRoute = new Set();

  console.info(`Drawing ${uniqueGeoPointsForRoute.length - 1} polyline segments for a route.`);
  for (let i = 1; i < uniqueGeoPointsForRoute.length; i++) {
    const p0 = uniqueGeoPointsForRoute[i - 1];
    const p1 = uniqueGeoPointsForRoute[i];

    if (p0.lon === p1.lon && p0.lat === p1.lat) {
      continue; // Skip zero-length segment
    }

    const segmentKey = `${p0.lon},${p0.lat}-${p1.lon},${p1.lat}`;
    if (drawnSegmentsThisRoute.has(segmentKey)) {
      // console.warn(`Segment ${segmentKey} already drawn for this specific route. Skipping.`);
      continue;
    }
    drawnSegmentsThisRoute.add(segmentKey);

    viewer.entities.add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray([
          p0.lon, p0.lat,
          p1.lon, p1.lat
        ]),
        width: 6,
        material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.ORANGE)
      }
    });
  }
}

/**
 * Processes an array of all probes (from one CSV file typically) to add points and draw a route.
 * @param {Array<Object>} allProbesForRoute Array of all probe data objects for a single route.
 */
function processRouteProbes(allProbesForRoute) {
  if (!allProbesForRoute || allProbesForRoute.length === 0) {
    console.warn("No probes to process for this route.");
    return;
  }
  console.info(`Processing ${allProbesForRoute.length} probes for a route.`);

  const uniqueGeoPointsForThisRoute = [];
  const seenCoordsForThisRoute = new Set();

  const hopNums = allProbesForRoute
    .map(p => parseInt(p.hop, 10))
    .filter(n => !isNaN(n));
  const minHop = Math.min(...hopNums);
  const maxHop = Math.max(...hopNums);

  allProbesForRoute.forEach((probe) => {
    // 根据 probe.hop 判断颜色：起点紫色，中间点绿色，终点红色
    const hop = parseInt(probe.hop, 10);
    let color = Cesium.Color.GREEN;
    if (hop === minHop) {
      color = Cesium.Color.PURPLE;
    } else if (hop === maxHop) {
      color = Cesium.Color.RED;
    }


    addOrUpdatePoint(probe, color);

    // For drawing lines, collect unique geographic points in order of appearance for this route
    const coordKey = `${probe.lat},${probe.lon}`;
    if (!seenCoordsForThisRoute.has(coordKey)) {
      if (!isNaN(probe.lat) && !isNaN(probe.lon)) {
        uniqueGeoPointsForThisRoute.push({ lat: probe.lat, lon: probe.lon });
        seenCoordsForThisRoute.add(coordKey);
      }
    }
  });

  if (uniqueGeoPointsForThisRoute.length > 1) {
    addPolylineForRoute(uniqueGeoPointsForThisRoute);
  }
    if (uniqueGeoPointsForThisRoute.length > 0) {
    const start = uniqueGeoPointsForThisRoute[0];
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        start.lon,
        start.lat,
        500000   // 这里的高度（单位：米）可根据需求调整
      ),
      duration: 2  // 飞行动画时长（秒）
    });
  }
}


function draw_path(text) {
  const rawLines = text.split(/\n+/).map(l => l.trim()).filter(l => l);
  if (rawLines.length < 2) {
    console.warn('CSV data insufficient (less than header + 1 data row)');
    return;
  }

  const header = rawLines[0].split(',').map(h => h.trim().toLowerCase());
  const allProbesFromFile = rawLines.slice(1).map(line => {
    const values = line.split(',');
    const probeObject = {};
    header.forEach((key, index) => {
      probeObject[key] = values[index] ? values[index].trim() : '';
    });
    probeObject.lat = parseFloat(probeObject.latitude); // Ensure lat/lon are numbers
    probeObject.lon = parseFloat(probeObject.longitude);
    return probeObject;
  }); // No early filtering of invalid lat/lon, addOrUpdatePoint will handle it

  if (allProbesFromFile.length === 0) {
    console.warn('No probe objects parsed from CSV.');
    return;
  }

  // Process all probes from this CSV file as a single route
  processRouteProbes(allProbesFromFile);
}

// —— Main data loading and processing block ——
setTimeout(async () => {
  try {
    const targetsResponse = await fetch('targets-2.txt');
    if (!targetsResponse.ok) throw new Error(`Failed to fetch targets-2.txt: ${targetsResponse.status}`);
    const targetsText = await targetsResponse.text();
    const ips = targetsText.split('\n').filter(s => s.trim()).map(s => s.trim().split('.').join('_'));

    if (ips.length === 0) {
      console.warn("No target IPs found in targets-2.txt.");
      return;
    }

    // viewer.entities.removeAll(); // Optional: Clear all entities before drawing new ones
    uniquePointsData.length = 0; // Clear the cache of unique points before processing new files
    // Note: This also means if multiple CSVs share a point, info won't aggregate across CSVs, only within a CSV. 
    // If cross-CSV aggregation is needed, this clear needs rethinking or a different global store.

    let filesLoadedCount = 0;
    for (const ip of ips) {
      
      
      try {
        const csvResponse = await fetch(`/Users/mac/Documents/GitHub/cnproject/Tracerouter/renderer/output_${ip}.csv`);
        if (csvResponse.ok) {
          const csvText = await csvResponse.text();
          if (csvText.trim()) {
            console.info('Processing CSV for:', ip);
            draw_path(csvText); // Process one CSV file
            filesLoadedCount++;
          } else {
            console.warn('Empty CSV content for:', ip);
          }
        } else {
          console.warn('Failed to fetch CSV for:', ip, csvResponse.status);
        }
      } catch (err) {
        console.warn('Error fetching or processing CSV for target:', ip, err);
      }
    }

    if (filesLoadedCount === 0) {
      console.warn("No CSV files were successfully loaded and processed. Check paths and file contents.");
    }

  } catch (err) {
    console.error('Error in main CSV loading/processing block:', err);
  }
}, 1000);

// function drawAll(){
//   for (var i; i <= )
// }