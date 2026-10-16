import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { uploadVideoParts, putVideoPart, videoOverallProgress, type VideoUploadSession } from './directVideoUpload';
import { apiRequest } from './apiClient';

vi.mock('./apiClient', () => ({ apiRequest: vi.fn() }));

class PartRequest {
  static instances: PartRequest[] = [];
  static maxActive = 0;
  static active = 0;
  url = '';
  status = 0;
  withCredentials = true;
  timeout = 0;
  inFlight = false;
  upload = { onprogress: null as ((event: { loaded: number }) => void) | null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  constructor() { PartRequest.instances.push(this); }
  open(_method: string, url: string) { this.url = url; }
  send = vi.fn(() => {
    this.inFlight = true;
    PartRequest.active++;
    PartRequest.maxActive = Math.max(PartRequest.maxActive, PartRequest.active);
  });
  finish() { if (this.inFlight) { this.inFlight = false; PartRequest.active--; } }
  abort = vi.fn(() => { this.finish(); this.onabort?.(); });
  succeed() { this.finish(); this.status = 200; this.onload?.(); }
  fail() { this.finish(); this.onerror?.(); }
}

const session = (parts = 5): VideoUploadSession => ({ id: 'job', status: 'uploading',
  size_bytes: parts * 10, part_bytes: 10, fingerprint: '', uploaded_parts: [] });
const file = (size = 50) => new File([new Uint8Array(size)], 'lesson.mp4');
const options = () => ({ active: () => true, signal: new AbortController().signal,
  progress: vi.fn(), partComplete: vi.fn() });

beforeEach(() => {
  vi.clearAllMocks();
  PartRequest.instances = []; PartRequest.active = 0; PartRequest.maxActive = 0;
  vi.stubGlobal('XMLHttpRequest', PartRequest);
  vi.mocked(apiRequest).mockImplementation(async path => ({ url: `https://store.test${path}`, size_bytes: 10 }));
});
afterEach(() => vi.unstubAllGlobals());

it('keeps three parts in flight, counts out-of-order progress once, and waits for the final PUT', async () => {
  const config = options();
  let done = false;
  const upload = uploadVideoParts(session(), file(), config).then(() => { done = true; });
  await vi.waitFor(() => expect(PartRequest.instances).toHaveLength(3));
  PartRequest.instances[0].upload.onprogress?.({ loaded: 4 });
  PartRequest.instances[1].upload.onprogress?.({ loaded: 8 });
  expect(config.progress).toHaveBeenLastCalledWith(12);
  PartRequest.instances[1].succeed();
  await vi.waitFor(() => expect(PartRequest.instances).toHaveLength(4));
  expect(config.progress).toHaveBeenLastCalledWith(14);
  PartRequest.instances[2].succeed();
  await vi.waitFor(() => expect(PartRequest.instances).toHaveLength(5));
  PartRequest.instances[0].succeed(); PartRequest.instances[3].succeed();
  await Promise.resolve();
  expect(done).toBe(false);
  PartRequest.instances[4].succeed();
  await upload;
  expect(PartRequest.maxActive).toBe(3);
  expect(config.progress).toHaveBeenLastCalledWith(50);
  const values = config.progress.mock.calls.map(([bytes]) => bytes);
  expect(values).toEqual([...values].sort((a, b) => a - b));
  expect(config.partComplete).toHaveBeenCalledTimes(5);
  expect(PartRequest.instances.every(xhr => !xhr.withCredentials)).toBe(true);
});

it('resumes only missing parts, including a short last part', async () => {
  const resumed = { ...session(), size_bytes: 43, uploaded_parts: [{ number: 1, size_bytes: 10 }, { number: 3, size_bytes: 10 }] };
  vi.mocked(apiRequest).mockImplementation(async path => ({ url: `https://store.test${path}`, size_bytes: path.endsWith('/5') ? 3 : 10 }));
  const config = options();
  const upload = uploadVideoParts(resumed, file(43), config);
  await vi.waitFor(() => expect(PartRequest.instances).toHaveLength(3));
  expect(config.progress).toHaveBeenNthCalledWith(1, 20);
  expect(PartRequest.instances.map(xhr => xhr.url.split('/').pop())).toEqual(['2', '4', '5']);
  PartRequest.instances.forEach(xhr => xhr.succeed());
  await upload;
  expect(config.progress).toHaveBeenLastCalledWith(43);
});

it('stops and drains sibling transfers on failure without signing remaining parts', async () => {
  const upload = uploadVideoParts(session(), file(), options());
  const failed = expect(upload).rejects.toThrow('انقطع الاتصال');
  await vi.waitFor(() => expect(PartRequest.instances).toHaveLength(3));
  PartRequest.instances[0].fail();
  await failed;
  expect(apiRequest).toHaveBeenCalledTimes(3);
  expect(PartRequest.instances[1].abort).toHaveBeenCalledTimes(1);
  expect(PartRequest.instances[2].abort).toHaveBeenCalledTimes(1);
  expect(PartRequest.active).toBe(0);
});

it('aborts every active part when cancelled and never reports late progress', async () => {
  const controller = new AbortController(); const config = { ...options(), signal: controller.signal };
  const upload = uploadVideoParts(session(), file(), config);
  const failed = expect(upload).rejects.toThrow('تم إيقاف');
  await vi.waitFor(() => expect(PartRequest.instances).toHaveLength(3));
  controller.abort();
  await failed;
  expect(PartRequest.instances.every(xhr => xhr.abort.mock.calls.length === 1)).toBe(true);
  expect(config.progress).toHaveBeenCalledTimes(1);
  expect(config.partComplete).not.toHaveBeenCalled();
});

it('does not send signed parts after the account changes while signing', async () => {
  const resolvers: Array<(value: { url: string; size_bytes: number }) => void> = [];
  vi.mocked(apiRequest).mockImplementation(() => new Promise(resolve => { resolvers.push(resolve); }));
  let active = true;
  const upload = uploadVideoParts(session(), file(), { ...options(), active: () => active });
  const failed = expect(upload).rejects.toThrow('تم إيقاف');
  expect(resolvers).toHaveLength(3);
  active = false;
  resolvers.forEach(resolve => resolve({ url: 'https://store.test/part', size_bytes: 10 }));
  await failed;
  expect(PartRequest.instances).toHaveLength(0);
});

it('does no work when already cancelled, or when all parts are stored', async () => {
  const controller = new AbortController(); controller.abort();
  await expect(uploadVideoParts(session(), file(), { ...options(), signal: controller.signal })).rejects.toThrow('تم إيقاف');
  await uploadVideoParts({ ...session(1), uploaded_parts: [{ number: 1, size_bytes: 10 }] }, file(10), options());
  expect(apiRequest).not.toHaveBeenCalled();
});

it('does not send an XHR cancelled before its send call', async () => {
  await expect(putVideoPart('https://store.test/part', new Blob(['a']), vi.fn(), () => false)).rejects.toThrow('تم إيقاف');
  expect(PartRequest.instances[0].send).not.toHaveBeenCalled();
});

it('leaves room for real encoding and storage work instead of spending 40 percent on the first transfer', () => {
  expect(videoOverallProgress(50)).toBe(5);
  expect(videoOverallProgress(100)).toBe(10);
  expect(videoOverallProgress(100, 0)).toBe(10);
  expect(videoOverallProgress(100, 5)).toBe(15);
  expect(videoOverallProgress(100, 45)).toBe(45);
  expect(videoOverallProgress(100, 85)).toBe(75);
  expect(videoOverallProgress(100, 92)).toBe(87);
});

it('never reports 100 before readiness, stays monotonic across stage boundaries, and ignores invalid measurements', () => {
  const values = [videoOverallProgress(0), videoOverallProgress(50), videoOverallProgress(100),
    ...Array.from({ length: 101 }, (_, processing) => videoOverallProgress(100, processing))];
  expect(values).toEqual([...values].sort((a, b) => a - b));
  expect(Math.max(...values)).toBe(99);
  expect(videoOverallProgress(Number.NaN)).toBe(0);
  expect(videoOverallProgress(100, Number.NaN)).toBe(10);
});
