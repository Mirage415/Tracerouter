// whisper-test.js - 测试nodejs-whisper模块

const path = require('path');
const fs = require('fs');

let nodewhisper;
try {
    nodewhisper = require('nodejs-whisper');
    console.log('成功引入nodejs-whisper模块');
    console.log('nodejs-whisper类型:', typeof nodewhisper);

    // 显示对象结构
    console.log('nodejs-whisper对象键:');
    for (const key in nodewhisper) {
        console.log(`- ${key}: ${typeof nodewhisper[key]}`);
    }

    // 检查模块导出内容
    if (typeof nodewhisper === 'function') {
        console.log('nodejs-whisper是函数');
    } else if (typeof nodewhisper === 'object') {
        console.log('nodejs-whisper是对象');
        console.log('可用方法:', Object.keys(nodewhisper).filter(k => typeof nodewhisper[k] === 'function'));

        // 检查nodewhisper内部结构
        if (nodewhisper.default && typeof nodewhisper.default === 'function') {
            console.log('找到 nodewhisper.default 函数');
        }
    }
} catch (error) {
    console.error('引入nodejs-whisper失败:', error);
    process.exit(1);
}

// 添加一些辅助函数
function createDummyWavFile() {
    // 创建一个简单的测试WAV文件
    const tempDir = path.join(__dirname, 'temp');
    if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
    }

    const testFilePath = path.join(tempDir, 'test.wav');

    // 如果已经存在测试文件，则不再创建
    if (fs.existsSync(testFilePath)) {
        console.log(`测试文件已存在: ${testFilePath}`);
        return testFilePath;
    }

    // 使用一个简单的WAV文件头模板
    const header = Buffer.from([
        0x52, 0x49, 0x46, 0x46, // "RIFF"
        0x24, 0x00, 0x00, 0x00, // Chunk size
        0x57, 0x41, 0x56, 0x45, // "WAVE"
        0x66, 0x6d, 0x74, 0x20, // "fmt "
        0x10, 0x00, 0x00, 0x00, // Subchunk1 size
        0x01, 0x00,             // AudioFormat (PCM)
        0x01, 0x00,             // NumChannels (Mono)
        0x44, 0xac, 0x00, 0x00, // SampleRate (44100 Hz)
        0x88, 0x58, 0x01, 0x00, // ByteRate
        0x02, 0x00,             // BlockAlign
        0x10, 0x00,             // BitsPerSample (16 bits)
        0x64, 0x61, 0x74, 0x61, // "data"
        0x00, 0x00, 0x00, 0x00  // Subchunk2 size
    ]);

    // 写入测试文件
    fs.writeFileSync(testFilePath, header);
    console.log(`创建测试文件: ${testFilePath}`);
    return testFilePath;
}

async function testWhisper() {
    try {
        // 创建测试WAV文件
        const testFilePath = createDummyWavFile();
        console.log(`开始测试，使用文件: ${testFilePath}`);

        // 尝试通过不同方式调用nodejs-whisper
        if (typeof nodewhisper === 'function') {
            console.log('尝试直接调用nodejs-whisper函数...');
            const result = await nodewhisper(testFilePath, {
                modelName: 'tiny.en',
                autoDownloadModelName: 'tiny.en',
                whisperOptions: {
                    outputInText: true
                }
            });
            console.log('处理结果:', result);
        } else if (nodewhisper && typeof nodewhisper.transcribe === 'function') {
            console.log('尝试调用nodejs-whisper.transcribe方法...');
            const result = await nodewhisper.transcribe(testFilePath, {
                modelName: 'tiny.en',
                autoDownloadModelName: 'tiny.en'
            });
            console.log('处理结果:', result);
        } else {
            console.error('无法找到可用的whisper调用方法');
        }
    } catch (error) {
        console.error('测试过程中出错:', error);
    }
}

// 运行测试
console.log('开始nodejs-whisper测试...');
testWhisper().then(() => {
    console.log('测试完成');
}).catch(err => {
    console.error('测试失败:', err);
}); 