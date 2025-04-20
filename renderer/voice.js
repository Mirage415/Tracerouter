function startRecording(){
  console.log('Recording started');
  isRecording = true;
}
function stopRecording(){
  console.log('Recording stopped');
  isRecording = false;
}


let mic;
let curves = 100;    // 曲线条数
let cx, cy;         // 曲线首尾固定点（中心）
let angles = [];    // 每条曲线的基准方向角
let baseRs = [];    // 每条曲线的基准半径
let phases1 = [], phases2 = [];   // 两组相位，用于控制两个控制点
let speeds1 = [], speeds2 = [];   // 相位增速
let textResult = "Listening..."; // 用于显示语音识别结果
let isRecording = false;

function setup() {
  createCanvas(windowWidth, windowHeight);
  mic = new p5.AudioIn();
  mic.start();

  cx = width / 2;
  cy = height / 2;

  // 为每条曲线随机分配一个方向和基准半径，以及两组相位/速度
  for (let i = 0; i < curves; i++) {
    angles.push(map(i, 0, curves, 0, TWO_PI));
    baseRs.push(random(height * 0.15, height * 0.3));
    phases1.push(random(TWO_PI));
    phases2.push(random(TWO_PI));
    speeds1.push(random(0.02, 0.08));
    speeds2.push(random(0.02, 0.08));
  }

  stroke(255);
  // noFill();
  // 创建按钮开始录音
  let recordButton = createButton("Start Recording");
  recordButton.position(20, 20);
  recordButton.mousePressed(startRecording);

  // 创建按钮停止录音
  let stopButton = createButton("Stop Recording");
  stopButton.position(150, 20);
  stopButton.mousePressed(stopRecording);
}

function draw() {
  background(20);

  // 获取响度并映射到最大振幅
  let vol = mic.getLevel();
  let maxAmp = map(vol, 0, 0.3, 0, height * 0.15);

  for (let i = 0; i < curves; i++) {
    // 更新两组相位
    phases1[i] += speeds1[i];
    phases2[i] += speeds2[i];

    // 计算两个控制点相对于中心的偏移半径
    let r = baseRs[i];
    let off1 = 100 * sin(phases1[i]) * maxAmp + random(5,15);
    let off2 = 100 * sin(phases2[i]) * maxAmp + random(5,15);

    // 控制点 1 坐标
    let cp1x = cx + cos(angles[i]) * (r + off1);
    let cp1y = cy + sin(angles[i]) * (r + off1);

    // 控制点 2 坐标（同方向、不同相位振荡）
    let cp2x = cx + cos(angles[i]) * (r + off2);
    let cp2y = cy + sin(angles[i]) * (r + off2);
    stroke('#05c9fa');
    // 绘制首尾都是 (cx, cy) 的贝塞尔曲线
    bezier(cx, cy, cp1x, cp1y, cp2x, cp2y, cx, cy);
  }
  // 显示语音识别结果
  fill(255);
  textSize(24);
  text("Speech-to-Text Result:", 20, 100);
  text(textResult, 20, 140);
}

function windowResized() {
  resizeCanvas(windowWidth, windowHeight);
  cx = width / 2;
  cy = height / 2;
}
