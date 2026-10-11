import { act, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AUTO_QUALITY, useHlsTransport } from './useHlsTransport';
import type Hls from 'hls.js';

interface MockHls {
  levels: Array<{ height: number }>;
  currentLevel: number;
  autoLevelCapping: number;
  handlers: Map<string, () => void>;
  stopLoad: ReturnType<typeof vi.fn>;
  destroy: ReturnType<typeof vi.fn>;
}
const mocks = vi.hoisted(() => ({ instances: [] as MockHls[] }));
vi.mock('hls.js', () => ({ default: class {
  static isSupported = () => true;
  static Events = { MANIFEST_PARSED: 'manifest', ERROR: 'error' };
  levels = [{ height: 144 }, { height: 360 }, { height: 720 }, { height: 720 }];
  currentLevel = -1;
  autoLevelCapping = -1;
  handlers = new Map<string, () => void>();
  constructor() { mocks.instances.push(this); }
  on(event: string, callback: () => void) { this.handlers.set(event, callback); }
  attachMedia() {}
  loadSource() {}
  stopLoad = vi.fn();
  destroy = vi.fn();
} }));

function Harness({ url }: { url: string }) {
  const video = useRef<HTMLVideoElement>(null), hls = useRef<Hls | null>(null);
  const [options, setOptions] = useState<string[]>([]), [selected, setSelected] = useState('');
  const [, setError] = useState<string | null>(null);
  const { selectQuality } = useHlsTransport(url, video, hls, setOptions, setSelected, setError);
  return <><video ref={video} /><output>{selected}</output>{options.map(option =>
    <button key={option} onClick={() => selectQuality(option)}>{option}</button>)}</>;
}
let host: HTMLDivElement, root: ReturnType<typeof createRoot>;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  mocks.instances.length = 0;
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {});
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const render = (url: string) => act(async () => root.render(<Harness url={url} />));
const parsed = () => act(async () => mocks.instances.at(-1)!.handlers.get('manifest')!());
const choose = (label: string) => act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === label)!.click());

it('aborts the old progressive resource when changing lessons or awaiting fresh admission', async () => {
  await render('/first.mp4');
  const video = host.querySelector('video')!;
  await render('/second.mp4');
  expect(video.getAttribute('src')).toBe('/second.mp4');
  expect(video.load).toHaveBeenCalledTimes(1);
  await render('');
  expect(video.hasAttribute('src')).toBe(false);
  expect(video.load).toHaveBeenCalledTimes(2);
});

it('switches the media level, restores automatic bandwidth ABR, and keeps a manual choice through token renewal', async () => {
  await render('/hls/first/master.m3u8'); await parsed();
  expect([...host.querySelectorAll('button')].map(button => button.textContent)).toEqual([AUTO_QUALITY, '144p', '360p', '720p']);
  await choose('720p'); expect(mocks.instances[0].currentLevel).toBe(2);
  await render('/hls/first/master.m3u8?token=renewed'); await parsed();
  expect(mocks.instances[1].currentLevel).toBe(2);
  await choose(AUTO_QUALITY); expect(mocks.instances[1].currentLevel).toBe(-1);
  expect(host.querySelector('output')?.textContent).toBe(AUTO_QUALITY);
});

it('labels a single-file fallback with its actual resolution and does not fabricate other qualities', async () => {
  await render('/source.mp4');
  const video = host.querySelector('video')!;
  Object.defineProperty(video, 'videoHeight', { value: 480 });
  await act(async () => video.dispatchEvent(new Event('loadedmetadata')));
  expect([...host.querySelectorAll('button')].map(button => button.textContent)).toEqual(['480p']);
  expect(host.textContent).not.toContain('الأصلية');
});

it('caps automatic playback at 1080p and excludes larger manual levels', async () => {
  await render('/hls/capped/master.m3u8');
  const hls = mocks.instances[0];
  hls.levels = [{ height: 360 }, { height: 1080 }, { height: 1440 }, { height: 2160 }];
  await parsed();
  expect(hls.autoLevelCapping).toBe(1);
  expect([...host.querySelectorAll('button')].map(button => button.textContent)).toEqual([AUTO_QUALITY, '360p', '1080p']);
  await choose('1080p');
  expect(hls.currentLevel).toBe(1);
  await choose(AUTO_QUALITY);
  expect(hls.currentLevel).toBe(-1);
  expect(hls.autoLevelCapping).toBe(1);
});
