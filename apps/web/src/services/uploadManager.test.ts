import { beforeEach, afterEach, expect, it, vi } from 'vitest';
vi.mock('./lmsService', () => ({ courseService: { uploadLessonVideo: vi.fn() } }));
const stored = (ownerScope?: string) => ({ id: 'task', title: 'QA video', type: 'lesson_video', fileName: 'qa.webm',
  fileSizeBytes: 100, formattedSize: '100 B', progress: 99, uploadPercent: 100, status: 'processing',
  lessonId: 'lesson', videoUploadId: 'job', createdAt: Date.now(), ownerScope });
const response = (status: string) => new Response(JSON.stringify({ id: 'job', status }), { status: 200 });
beforeEach(() => { vi.resetModules(); localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

it('automatically waits for encoded renditions after a standard upload instead of completing at 100 percent bytes', async () => {
  let completeUpload!: (value: Awaited<ReturnType<typeof import('./lmsService').courseService.uploadLessonVideo>>) => void;
  let completeProcessing!: (value: Response) => void;
  const { courseService } = await import('./lmsService');
  vi.mocked(courseService.uploadLessonVideo).mockImplementation((_id, _file, progress) => {
    progress?.(100);
    return new Promise(resolve => { completeUpload = resolve; });
  });
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/auth/me')) return new Response('{}', { status: 200 });
    if (url.endsWith('/video-upload-capabilities')) return new Response('{"direct_upload":false}', { status: 200 });
    if (url.endsWith('/video-uploads/job')) return new Promise<Response>(resolve => { completeProcessing = resolve; });
    throw new Error(`Unexpected request: ${url}`);
  }));
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-a');
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  const onSuccess = vi.fn();
  manager.enqueueVideoUpload({ lessonId: 'lesson', lessonTitle: 'الكيمياء', file: new File(['video'], 'lesson.mp4', { type: 'video/mp4' }), onSuccess });
  await vi.waitFor(() => expect(completeUpload).toBeTypeOf('function'));
  expect(manager.getTasks()[0]).toMatchObject({ status: 'processing', uploadPercent: 100 });
  completeUpload({ id: 'lesson', video_url: '/protected', filename: 'lesson.mp4', video_upload_id: 'job' });
  await vi.waitFor(() => expect(completeProcessing).toBeTypeOf('function'));
  expect(onSuccess).not.toHaveBeenCalled();
  expect(manager.getTasks()[0].status).toBe('processing');
  completeProcessing(response('ready'));
  await vi.waitFor(() => expect(manager.getTasks()[0].status).toBe('completed'));
  expect(onSuccess).toHaveBeenCalledTimes(1);
});

it('announces a background material failure with its reason instead of failing silently', async () => {
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-a');
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  const listener = vi.fn();
  window.addEventListener('lms_toast_notification', listener);
  try {
    manager.enqueueKnowledgeBatchUpload({ files: [new File(['%PDF'], 'notes.pdf')], lessonTitle: 'بنية الذرة' });
    expect(manager.getTasks()[0].status).toBe('error');
    expect(listener).toHaveBeenCalledTimes(1);
    const detail = (listener.mock.calls[0][0] as CustomEvent).detail;
    expect(detail.tone).toBe('danger');
    expect(detail.message).toContain('لا يمكن رفع المذكرات بدون تحديد الدرس');
  } finally { window.removeEventListener('lms_toast_notification', listener); }
});

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

it('prepares an existing stored video without a file transfer and completes from the server job', async () => {
  const calls: Array<{ url: string; method: string }> = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method || 'GET' });
    return new Response(JSON.stringify({ id: 'prepared', status: 'ready', size_bytes: 1234 }), { status: 200 });
  }));
  const api = await import('./apiClient'); api.setApiAuthScope('teacher-a');
  const { UploadManager } = await import('./uploadManager'); const manager = new UploadManager();
  await manager.prepareVideo('lesson', 'Saved video', 'course');
  await vi.waitFor(() => expect(manager.getTasks()[0].status).toBe('completed'));
  expect(calls.map(call => call.method)).toEqual(['POST', 'GET']);
  expect(calls[0].url).toContain('/lessons/lesson/prepare-video');
  expect(calls[1].url).toContain('/video-uploads/prepared');
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
