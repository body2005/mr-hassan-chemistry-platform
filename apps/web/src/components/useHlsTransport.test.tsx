import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type Hls from 'hls.js';
import { useHlsTransport } from './useHlsTransport';

const fake = vi.hoisted(() => ({ instances: [] as Array<{
  handlers: Record<string, (...args: unknown[]) => void>;
  destroy: ReturnType<typeof vi.fn>; stopLoad: ReturnType<typeof vi.fn>;
  config: { fragLoadPolicy: { default: { errorRetry: null; timeoutRetry: null } } };
}> }));
vi.mock('hls.js', () => ({ default: class {
  static isSupported() { return true; }
  static Events = { ERROR: 'error', MANIFEST_PARSED: 'manifest' };
  handlers: Record<string, (...args: unknown[]) => void> = {};
  levels = [{ height: 360 }, { height: 720 }];
  destroy = vi.fn(); stopLoad = vi.fn(); attachMedia = vi.fn(); loadSource = vi.fn();
  constructor(public config: typeof fake.instances[number]['config']) { fake.instances.push(this); }
  on(event: string, callback: (...args: unknown[]) => void) { this.handlers[event] = callback; }
} }));
let root: Root;
let host: HTMLDivElement;
const videoRef = { current: null as HTMLVideoElement | null };
const hlsRef = { current: null as Hls | null };
const error = vi.fn(), options = vi.fn(), selected = vi.fn();
function Harness({ url }: { url: string }) {
  useHlsTransport(url, videoRef, hlsRef, options, selected, error);
  return null;
}
async function render(url: string) { await act(async () => root.render(<Harness url={url} />)); }
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  fake.instances.length = 0;
  error.mockClear(); options.mockClear(); selected.mockClear();
  videoRef.current = document.createElement('video');
  hlsRef.current = null;
  host = document.createElement('div'); document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

it.each([401, 403, 429])('stops HLS at %s without enabling transport retry loops', async code => {
  await render('/hls/master.m3u8');
  const transport = fake.instances[0];
  transport.handlers.error('error', { fatal: false, response: { code } });
  expect(transport.stopLoad).toHaveBeenCalledTimes(1);
  expect(error).toHaveBeenCalledTimes(1);
  expect(transport.config.fragLoadPolicy.default.errorRetry).toBeNull();
  expect(transport.config.fragLoadPolicy.default.timeoutRetry).toBeNull();
  expect(fake.instances).toHaveLength(1);
});
it('disposes the old transport and ignores its late callbacks', async () => {
  await render('/hls/first.m3u8');
  const old = fake.instances[0];
  await render('/hls/second.m3u8');
  expect(old.destroy).toHaveBeenCalledTimes(1);
  old.handlers.error('error', { fatal: true });
  old.handlers.manifest();
  expect(error).not.toHaveBeenCalled();
  expect(options).not.toHaveBeenCalled();
  fake.instances[1].handlers.manifest();
  expect(options).toHaveBeenCalledWith(['تلقائي', '360p', '720p']);
});
it('removes the previous native source during token admission', async () => {
  await render('/first.mp4');
  expect(videoRef.current?.getAttribute('src')).toBe('/first.mp4');
  await render('');
  expect(videoRef.current?.hasAttribute('src')).toBe(false);
});
