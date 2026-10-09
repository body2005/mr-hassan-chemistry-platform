import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type Hls from 'hls.js';
import type { VideoLesson } from '../types/lms';
import { useProtectedPlayback } from './useProtectedPlayback';

const fake = vi.hoisted(() => ({ request: vi.fn(), generation: 0, scope: 'teacher' }));
vi.mock('../services/apiClient', () => ({ apiRequest: fake.request, apiUrl: (url: string) => url,
  getApiAuthGeneration: () => fake.generation, getApiAuthScope: () => fake.scope }));
const pending: { signal: AbortSignal; resolve: (value: { stream_url: string }) => void; reject: (error: unknown) => void }[] = [];
let host: HTMLDivElement, root: Root;
const videoRef = { current: null as HTMLVideoElement | null };
const stopLoad = vi.fn();
const hlsRef = { current: { stopLoad } as unknown as Hls };
let playback: ReturnType<typeof useProtectedPlayback>;
function Harness({ userId = 'teacher', id = 'lesson' }: { userId?: string; id?: string }) {
  playback = useProtectedPlayback({ id, videoUrl: '', requiresProtectedPlayback: true } as VideoLesson, userId, videoRef, hlsRef);
  return <output>{playback.playbackUrl}{playback.playbackError}</output>;
}
async function render(userId = 'teacher', id = 'lesson') { await act(async () => root.render(<Harness userId={userId} id={id} />)); }
beforeEach(() => {
  vi.useFakeTimers(); vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  fake.generation = 0; fake.scope = 'teacher'; fake.request.mockReset(); stopLoad.mockClear(); pending.length = 0;
  fake.request.mockImplementation((_path: string, options: { signal: AbortSignal }) => new Promise((resolve, reject) => pending.push({ signal: options.signal, resolve, reject })));
  videoRef.current = document.createElement('video');
  vi.spyOn(videoRef.current, 'pause').mockImplementation(() => {});
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it.each([401, 403, 429, 503, 0])('distinguishes token failure %s without automatic replay', async status => {
  await render(); await act(async () => pending[0].reject({ status, code: status === 0 ? 'NETWORK_ERROR' : undefined }));
  expect(host.textContent).toContain(status === 401 ? 'انتهت جلسة' : status === 403 ? 'لا تملك صلاحية' : status === 429 ? 'طلبات كثيرة' : 'تعذر الاتصال');
  await act(async () => vi.advanceTimersByTime(600000));
  expect(fake.request).toHaveBeenCalledTimes(1);
});
it.each(['user', 'lesson'])('aborts and ignores token replies after changing %s', async target => {
  await render(); await render(target === 'user' ? 'new-teacher' : 'teacher', target === 'lesson' ? 'new-lesson' : 'lesson');
  expect(pending[0].signal.aborted).toBe(true); expect(pending[1].signal.aborted).toBe(false);
  await act(async () => pending[1].resolve({ stream_url: '/new.mp4' }));
  await act(async () => pending[0].resolve({ stream_url: '/old.mp4' }));
  expect(host.textContent).toBe('/new.mp4');
});
it('stops old media on logout and does not accept its late token', async () => {
  await render(); videoRef.current!.src = '/old.mp4';
  await act(async () => { fake.scope = 'anonymous'; fake.generation++; window.dispatchEvent(new Event('lms_auth_scope_updated')); });
  expect(pending[0].signal.aborted).toBe(true); expect(videoRef.current!.hasAttribute('src')).toBe(false);
  expect(stopLoad).toHaveBeenCalledTimes(1); expect(videoRef.current!.pause).toHaveBeenCalledTimes(1);
  await act(async () => pending[0].resolve({ stream_url: '/late.mp4' }));
  expect(host.textContent).toContain('انتهت جلسة'); expect(host.textContent).not.toContain('/late.mp4');
  expect(fake.request).toHaveBeenCalledTimes(1);
});
it('starts fresh admission for a new generation of the same account without aborting its request', async () => {
  await render();
  await act(async () => { fake.generation++; window.dispatchEvent(new Event('lms_auth_scope_updated')); });
  expect(pending).toHaveLength(2); expect(pending[0].signal.aborted).toBe(true); expect(pending[1].signal.aborted).toBe(false);
  await act(async () => pending[0].reject({ status: 401 }));
  await act(async () => pending[1].resolve({ stream_url: '/fresh.mp4' }));
  expect(host.textContent).toBe('/fresh.mp4');
});
it('releases the renewal lock after failure and keeps position for an explicit retry', async () => {
  await render(); await act(async () => pending[0].resolve({ stream_url: '/first.mp4' }));
  let failure!: Promise<boolean>;
  await act(async () => { failure = playback.renewProtectedPlayback(true); });
  await act(async () => pending[1].reject({ code: 'NETWORK_ERROR' }));
  expect(await failure).toBe(false);
  videoRef.current!.currentTime = 31;
  let retry!: Promise<boolean>;
  await act(async () => { retry = playback.renewProtectedPlayback(true); });
  await act(async () => pending[2].resolve({ stream_url: '/recovered.mp4' }));
  expect(await retry).toBe(true); expect(playback.pendingPlaybackResumeRef.current?.time).toBe(31);
  expect(host.textContent).toBe('/recovered.mp4');
});
it('attempts only one scheduled renewal when the network fails', async () => {
  await render(); await act(async () => pending[0].resolve({ stream_url: '/hls/master.m3u8' }));
  await act(async () => vi.advanceTimersByTime(240000));
  await act(async () => pending[1].reject({ code: 'NETWORK_ERROR' }));
  await act(async () => vi.advanceTimersByTime(1200000));
  expect(fake.request).toHaveBeenCalledTimes(2);
});
