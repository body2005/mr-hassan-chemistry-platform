import { beforeEach, afterEach, expect, it, vi } from 'vitest';
vi.mock('./lmsService', () => ({ courseService: {} }));
const stored = (ownerScope?: string) => ({ id: 'task', title: 'QA video', type: 'lesson_video', fileName: 'qa.webm',
  fileSizeBytes: 100, formattedSize: '100 B', progress: 99, uploadPercent: 100, status: 'processing',
  lessonId: 'lesson', videoUploadId: 'job', createdAt: Date.now(), ownerScope });
const response = (status: string) => new Response(JSON.stringify({ id: 'job', status }), { status: 200 });
beforeEach(() => { vi.resetModules(); localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

it('recovers a ready legacy job after reload without any POST or re-upload, invalidating stale courses', async () => {
  localStorage.setItem('lms_global_upload_tasks_v3', JSON.stringify([stored()]));
  const fetcher = vi.fn(async () => response('ready')); vi.stubGlobal('fetch', fetcher);
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-a');
  api.setCachedData('composed:/courses', { stale: true }, 60_000);
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  await manager.reconcileVideos();
  expect(manager.getTasks()[0]).toMatchObject({ status: 'completed', progress: 100, ownerScope: 'teacher-a' });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(api.getCachedData('composed:/courses')).toBeUndefined();
});

it('does not inspect, retry, cancel or clear another teacher account task', async () => {
  localStorage.setItem('lms_global_upload_tasks_v3', JSON.stringify([stored('teacher-a')]));
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-b');
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  await manager.reconcileVideos(); manager.retryUpload('task'); manager.cancelUpload('task'); manager.clearCompleted();
  expect(fetcher).not.toHaveBeenCalled(); expect(manager.getTasks()).toHaveLength(1);
});

it('never binds or displays an inaccessible legacy job', async () => {
  localStorage.setItem('lms_global_upload_tasks_v3', JSON.stringify([stored()]));
  const fetcher = vi.fn(async () => new Response('{}', { status: 403 })); vi.stubGlobal('fetch', fetcher);
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-b');
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  await manager.reconcileVideos();
  expect(manager.getTasks()[0].ownerScope).toBeUndefined(); expect(fetcher).toHaveBeenCalledTimes(1);
});

it('stops on 429 rather than creating a retry loop', async () => {
  localStorage.setItem('lms_global_upload_tasks_v3', JSON.stringify([stored('teacher-a')]));
  const fetcher = vi.fn(async () => new Response('{}', { status: 429 })); vi.stubGlobal('fetch', fetcher);
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-a');
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  await manager.reconcileVideos();
  expect(manager.getTasks()[0].status).toBe('error'); expect(fetcher).toHaveBeenCalledTimes(1);
});

it('shows complete byte transfer separately from processing, then completes when the worker is ready', async () => {
  localStorage.setItem('lms_global_upload_tasks_v3', JSON.stringify([stored('teacher-a')]));
  let statusReads = 0; let finish: (response: Response) => void = () => {};
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    if (input.endsWith('/auth/me')) return new Response('{}', { status: 200 });
    if (input.endsWith('/video-upload-capabilities')) return new Response('{"direct_upload":true}', { status: 200 });
    return ++statusReads <= 2 ? response('queued') : new Promise<Response>(resolve => { finish = resolve; });
  }));
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-a');
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  await manager.reconcileVideos();
  await vi.waitFor(() => expect(statusReads).toBe(3));
  expect(manager.getTasks()[0]).toMatchObject({ status: 'processing', progress: 100, uploadPercent: 100 });
  finish(response('ready'));
  await vi.waitFor(() => expect(manager.getTasks()[0].status).toBe('completed'));
});
