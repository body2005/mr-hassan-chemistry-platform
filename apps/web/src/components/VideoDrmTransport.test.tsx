import { act, useRef, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type Hls from 'hls.js';
import type { HlsConfig } from 'hls.js';
import { useHlsTransport } from './useHlsTransport';
import type { VideoDrmDescriptor } from '../services/videoDrm';

const mock = vi.hoisted(() => ({ supported: true, configurations: [] as Partial<HlsConfig>[] }));
vi.mock('hls.js', () => ({ default: class {
  static isSupported = () => mock.supported;
  static Events = { MANIFEST_PARSED: 'manifest', ERROR: 'error', FRAG_BUFFERED: 'fragment', LEVEL_SWITCHING: 'switching' };
  levels = []; loadLevel = -1;
  constructor(config: Partial<HlsConfig>) { mock.configurations.push(config); }
  on() {} attachMedia() {} loadSource() {} stopLoad() {} destroy() {}
} }));
const descriptor: VideoDrmDescriptor = { scheme: 'cbcs',
  widevine_license_url: '/api/v1/lessons/lesson/hls/asset/drm/license/widevine',
  fairplay_license_url: '/api/v1/lessons/lesson/hls/asset/drm/license/fairplay',
  fairplay_certificate_url: '/api/v1/lessons/lesson/hls/asset/drm/certificate' };
const authorize = vi.fn(async (url: string) => `${url}?token=synthetic-fresh`);
function Harness() {
  const video = useRef<HTMLVideoElement>(null), hls = useRef<Hls | null>(null);
  const [, setOptions] = useState<string[]>([]), [, setQuality] = useState(''), [error, setError] = useState<string | null>(null);
  useHlsTransport('/api/v1/lessons/lesson/hls/asset/master.m3u8', video, hls, setOptions, setQuality, setError, authorize, descriptor);
  return <><video ref={video} /><output>{error}</output></>;
}
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); mock.supported = true; mock.configurations.length = 0; authorize.mockClear();
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {});
  document.cookie = 'matgar_csrf=synthetic-csrf';
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); document.cookie = 'matgar_csrf=; Max-Age=0'; vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('configures EME Widevine/FairPlay and sends renewed scoped license requests with CSRF', async () => {
  await act(async () => root.render(<Harness />));
  const config = mock.configurations[0];
  expect(config.emeEnabled).toBe(true);
  expect(config.drmSystemOptions?.videoEncryptionScheme).toBe('cbcs');
  expect(config.drmSystems?.['com.apple.fps']?.serverCertificateUrl).toBe(descriptor.fairplay_certificate_url);
  const xhr = { open: vi.fn(), setRequestHeader: vi.fn(), withCredentials: false };
  // Exercise the exact callback installed for the CDM transport.
  await config.licenseXhrSetup!.call(null as never, xhr as unknown as XMLHttpRequest, descriptor.widevine_license_url, {} as never, new Uint8Array([1]));
  expect(authorize).toHaveBeenCalledWith(descriptor.widevine_license_url);
  expect(xhr.open).toHaveBeenCalledWith('POST', `${descriptor.widevine_license_url}?token=synthetic-fresh`, true);
  expect(xhr.withCredentials).toBe(true);
  expect(xhr.setRequestHeader).toHaveBeenCalledWith('X-CSRF-Token', 'synthetic-csrf');
  expect(config.keyLoadPolicy?.default.errorRetry).toBeNull();
});
it('fails closed when the browser lacks the protected transport instead of switching to clear/native playback', async () => {
  mock.supported = false;
  await act(async () => root.render(<Harness />));
  expect(host.querySelector('video')?.hasAttribute('src')).toBe(false);
  expect(host.querySelector('output')?.textContent).toContain('DRM');
  expect(mock.configurations).toHaveLength(0);
});
