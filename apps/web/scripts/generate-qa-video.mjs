import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const directory = resolve(process.env.QA_MEDIA_DIR || '../../.qa/production/media');
mkdirSync(directory, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const encoded = await page.evaluate(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 1280; canvas.height = 720;
    const context = canvas.getContext('2d');
    const stream = canvas.captureStream(15);
    const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8', videoBitsPerSecond: 4_000_000 });
    const chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    const finished = new Promise((resolve) => { recorder.onstop = resolve; });
    recorder.start(1000);
    let seed = 17;
    const started = performance.now();
    while (performance.now() - started < 20_000) {
      const pixels = context.createImageData(1280, 720);
      for (let offset = 0; offset < pixels.data.length; offset += 4) {
        seed = (seed * 1664525 + 1013904223) >>> 0;
        pixels.data[offset] = seed & 255;
        pixels.data[offset + 1] = (seed >>> 8) & 255;
        pixels.data[offset + 2] = (seed >>> 16) & 255;
        pixels.data[offset + 3] = 255;
      }
      context.putImageData(pixels, 0, 0);
      context.fillStyle = 'white'; context.font = '40px sans-serif';
      context.fillText(`Chemistry QA ${(performance.now() - started).toFixed(0)} ms`, 40, 60);
      await new Promise((resolve) => setTimeout(resolve, 65));
    }
    recorder.stop(); await finished;
    stream.getTracks().forEach((track) => track.stop());
    const blob = new Blob(chunks, { type: 'video/webm' });
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]); reader.readAsDataURL(blob);
    });
  });
  const video = Buffer.from(encoded, 'base64');
  if (video.length < 5 * 1024 * 1024) throw new Error(`QA video too small: ${video.length}`);
  writeFileSync(resolve(directory, 'video.webm'), video);
  console.log(JSON.stringify({ video: 'video.webm', bytes: video.length, recording_seconds: 20 }));
} finally { await browser.close(); }
