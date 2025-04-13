let hops = [];
let currentStep = 0;
let lastUpdate = 0;
let delayPerStep = 800;
let waveform = [];

function fetchTraceroute(url) {
  fetch(url)
    .then(res => res.json())
    .then(data => {
      hops = data;
    });
}

function setup() {
  createCanvas(windowWidth, windowHeight);
  textFont("monospace");
  fetchTraceroute("http://localhost:5000/traceroute?target=8.8.8.8");
  frameRate(60);
}



function draw() {
  background(20);
  drawPath();
  drawWaveform();
}

function drawPath() {
  let spacing = 80;
  for (let i = 0; i < currentStep; i++) {
    let hop = hops[i];
    let y = 100 + i * spacing;

    // 线
    stroke(100 + i * 5, 150, 255);
    line(width / 4, y - spacing, width / 4, y);

    // 圆圈
    fill(100, 200, 255);
    ellipse(width / 4, y, 30, 30);

    // IP + RTT
    fill(255);
    noStroke();
    textAlign(LEFT, CENTER);
    text(`TTL ${hop.ttl}: ${hop.addr || '*'}   ${hop.rtt || ''}`, width / 4 + 40, y);
  }

  // 控制逐步出现
  if (millis() - lastUpdate > delayPerStep && currentStep < hops.length) {
    waveform.push(getWaveValue(hops[currentStep]));
    currentStep++;
    lastUpdate = millis();
  }
}

function getWaveValue(hop) {
  if (hop.type === "timeout") return 0;
  let rtt = parseFloat(hop.rtt);
  return map(rtt, 0, 300, 0, height / 3); // 映射 RTT 到可视范围
}

function drawWaveform() {
  push();
  translate(0, height * 0.75);
  stroke(0, 255, 150);
  strokeWeight(2);
  noFill();
  beginShape();
  for (let i = 0; i < waveform.length; i++) {
    let x = map(i, 0, hops.length - 1, 100, width - 100);
    let y = -waveform[i]; // y向上画
    vertex(x, y);
  }
  endShape();

  // 横轴标注
  fill(255);
  noStroke();
  text("RTT Waveform", 20, -height * 0.05);
  pop();
}
