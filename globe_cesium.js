// globe_cesium.js

// 如果你有 Cesium Ion Token，可放这里；否则用 open-source 切片服务见下方注释
// Cesium.Ion.defaultAccessToken = 'YOUR_CESIUM_ION_TOKEN';

const viewer = new Cesium.Viewer('cesiumContainer', {
  imageryProvider: new Cesium.ArcGisMapServerImageryProvider({
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
  }),
  baseLayerPicker: false,
  geocoder: true,
  homeButton: false,
  sceneModePicker: false,
  timeline: false,
  animation: false
});

// 开启光照效果
viewer.scene.globe.enableLighting = true;

/**
* 将经纬度标注为红点
* @param {Number} lat 纬度
* @param {Number} lon 经度
*/
function addPoint(lat, lon) {
viewer.entities.add({
  position: Cesium.Cartesian3.fromDegrees(lon, lat),
  point: {
    pixelSize: 10,
    color: Cesium.Color.RED,
    outlineColor: Cesium.Color.WHITE,
    outlineWidth: 2,
    heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
  }
});
}

/**
* 根据一组点连成带箭头的折线
// ...existing code...

/**
 * 连线，只有最后一段带箭头
 * @param {Array<{lat:Number, lon:Number}>} points
 */
function addPolylineArrowsForEachSegment(points) {
  if (points.length < 2) return;
  for (let i = 1; i < points.length; i++) {
    viewer.entities.add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray([
          points[i - 1].lon, points[i - 1].lat,
          points[i].lon, points[i].lat
        ]),
        width: 6,
        material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.ORANGE)
      }
    });
  }
}

// 替换 updateRoute 里的连线调用
function updateRoute(hops) {
  viewer.entities.removeAll();
  hops.forEach(h => addPoint(h.lat, h.lon));
  if (hops.length > 1) {
    addPolylineArrowsForEachSegment(hops);
  }
  viewer.flyTo(viewer.entities, { duration: 1.5 });
}

// ...existing code...

// —— 动态从 output.csv 读取并绘制 ——
setTimeout(async () => {
try {
  // 1. 读取 CSV
  const resp = await fetch('renderer/output.csv');
  if (!resp.ok) throw new Error(`Fetch CSV failed: ${resp.status}`);
  const text = await resp.text();

  // 2. 按行拆分、滤掉空行
  const rawLines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l);
  console.log('rawLines:', rawLines);

  // 3. 如果有表头，就去掉
  const dataLines = rawLines[0]?.toLowerCase().startsWith('ip,')
    ? rawLines.slice(1)
    : rawLines;
  console.log('dataLines (no header):', dataLines);

  // 4. 解析成 [{lat,lon},…]，丢弃解析失败的行
  const allHops = dataLines.map(line => {
    const [ip, latStr, lonStr] = line.split(',');
    const lat = parseFloat(latStr), lon = parseFloat(lonStr);
    return (!isNaN(lat) && !isNaN(lon))
      ? { lat, lon }
      : null;
  }).filter(x => x);
  console.log('allHops:', allHops);

  if (allHops.length === 0) {
    console.warn('No valid hops parsed—请检查 output.csv 在 renderer 目录下，且没有多余空行或表头');
    return;
  }

  // 5. 按序“长”出路径
  for (let i = 1; i <= allHops.length; i++) {
    const segment = allHops.slice(0, i);
    updateRoute(segment);
    // 等 500ms 再画下一跳
    await new Promise(r => setTimeout(r, 500));
  }

} catch (err) {
  console.error('Error loading CSV route:', err);
}
}, 1000);