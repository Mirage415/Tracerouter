// globe_cesium.js

// 如果你有 Cesium Ion Token，可放这里；否则用 open-source 切片服务见下方注释
// Cesium.Ion.defaultAccessToken = 'YOUR_CESIUM_ION_TOKEN';

const dots = [];
const paths = [];

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
function addPoint(lat, lon, col) {
  if (dots.filter((dot) => dot.lat === lat && dot.lon === lon).length) {
    return;
  }

  dots.push({ lat: lat, lon: lon })

viewer.entities.add({
  position: Cesium.Cartesian3.fromDegrees(lon, lat),
  point: {
    pixelSize: 10,
    color: col,
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
  console.info(`Add ${points.length - 1} lines`)
  for (let i = 1; i < points.length; i++) {
    const lon0 = points[i - 1].lon;
    const lat0 = points[i - 1].lat;
    const lon1 = points[i - 0].lon;
    const lat1 = points[i - 0].lat;
  
    if (lon0 === lon1 && lat0 === lat1) {
      continue;
    }

    if (paths.filter((path) => (
      path[0].lon === lon0 && paths[0].lat === lat0 &&
      path[1].lon === lon1 && paths[1].lat === lat1
    )).length) {
      continue;
    }

    paths.push([ { lon: lon0, lat: lat0 }, { lon: lon1, lat: lat1 } ])

    console.info(`Add (${lon0}, ${lat0}) --> (${lon1}, ${lat1})`)
    viewer.entities.add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray([
          lon0, lat0,
          lon1, lat1
        ]),
        width: 6,
        material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.ORANGE)
      }
    });
  }
}

// 替换 updateRoute 里的连线调用
function updateRoute(hops) {
  //viewer.entities.removeAll();
  console.info('Add', hops);
  hops.forEach((h, i) => {
    let color = Cesium.Color.RED;
    if (i === 0) {
      color = Cesium.Color.PURPLE
    } else if (i === hops.length - 1) {
      color = Cesium.Color.WHITE
    }
    addPoint(h.lat, h.lon, color)
  });
  if (hops.length > 1) {
    addPolylineArrowsForEachSegment(hops);
  }
  //viewer.flyTo(viewer.entities, { duration: 1.5 });
}

// ...existing code...

function draw_path(text){
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
  //for (let i = 1; i <= allHops.length; i++) {
    //const segment = allHops.slice(0, i);
    //updateRoute(segment);
    // 等 500ms 再画下一跳
    // await new Promise(r => setTimeout(r, 100));
  //}
  updateRoute(allHops)
}

// —— 动态从 output.csv 读取并绘制 ——
setTimeout(async () => {
try {
  // 1. 读取 CSV
  const targets = await fetch('targets-2.txt');
  const ips = (await targets.text()).split('\n').filter((s) => s).map((s) => {
    return s.split('.').join('_')
  });

  ///Users/mac/Documents/GitHub/Tracerouter/renderer/output_2_248_180_1.csv
  const files = (await Promise.all(ips.map((ip) => {
    return fetch(`/Users/mac/Documents/GitHub/Tracerouter/renderer/output_${ip}.csv`).then((r) => {
      if (r.ok) {
        console.info('Got', ip);
        return r.text();
      } else {
        return '';
      }
    }).catch((err) => {
      console.warn('Didn\'t find for:', ip);
      console.error(err);
    })
  }))).filter((s) => s);

  //files.length = 2;
  files.forEach((text) => draw_path(text))
//for i in len(files):
//    const resp = await fetch(files[i])

  // const resp = await fetch('renderer/output.csv');
  // if (!resp.ok) throw new Error(`Fetch CSV failed: ${resp.status}`);

  // 2. 按行拆分、滤掉空行
  // const rawLines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l);
  // console.log('rawLines:', rawLines);

  // // 3. 如果有表头，就去掉
  // const dataLines = rawLines[0]?.toLowerCase().startsWith('ip,')
  //   ? rawLines.slice(1)
  //   : rawLines;
  // console.log('dataLines (no header):', dataLines);

  // // 4. 解析成 [{lat,lon},…]，丢弃解析失败的行
  // const allHops = dataLines.map(line => {
  //   const [ip, latStr, lonStr] = line.split(',');
  //   const lat = parseFloat(latStr), lon = parseFloat(lonStr);
  //   return (!isNaN(lat) && !isNaN(lon))
  //     ? { lat, lon }
  //     : null;
  // }).filter(x => x);
  // console.log('allHops:', allHops);

  // if (allHops.length === 0) {
  //   console.warn('No valid hops parsed—请检查 output.csv 在 renderer 目录下，且没有多余空行或表头');
  //   return;
  // }

  // // 5. 按序“长”出路径
  // for (let i = 1; i <= allHops.length; i++) {
  //   const segment = allHops.slice(0, i);
  //   updateRoute(segment);
  //   // 等 500ms 再画下一跳
  //   await new Promise(r => setTimeout(r, 100));
  // }

} catch (err) {
  console.error('Error loading CSV route:', err);
}
}, 1000);

// function drawAll(){
//   for (var i; i <= )
// }