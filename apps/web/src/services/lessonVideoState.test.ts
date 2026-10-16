import { expect, it } from 'vitest';
import { lessonVideoState } from './lessonVideoState';
import type { VideoLesson } from '../types/lms';
import type { UploadTask } from './uploadManager';

const lesson = { id: 'lesson', hasUploadedVideo: true, videoUrl: '/protected' } as VideoLesson;
const task = { id: 'task', lessonId: 'lesson', ownerScope: 'teacher', type: 'lesson_video', createdAt: 2000,
  uploadPercent: 42, status: 'uploading' } as UploadTask;

it('hides playback during a replacement upload and processing, then restores it on completion', () => {
  expect(lessonVideoState(lesson, [task], 'teacher')).toMatchObject({ phase: 'uploading', percent: 4, label: 'جاري رفع الفيديو…' });
  expect(lessonVideoState(lesson, [{ ...task, status: 'processing', uploadPercent: 100 }], 'teacher').phase).toBe('processing');
  expect(lessonVideoState(lesson, [{ ...task, status: 'completed' }], 'teacher').phase).toBe('ready');
});

it('restores the completed-transfer milestone while waiting for server progress', () => {
  const result = lessonVideoState({ ...lesson, videoUpload: { id: 'job', status: 'processing', createdAt: new Date(3000).toISOString() } }, [], 'teacher');
  expect(result.phase).toBe('processing');
  expect(result.percent).toBe(10);
  expect(lessonVideoState({ ...lesson, videoUpload: { id: 'job', status: 'completing', createdAt: new Date(3000).toISOString() } }, [], 'teacher').percent).toBe(10);
});

it('ignores other accounts and lessons, and local failures older than a later server upload', () => {
  expect(lessonVideoState(lesson, [task], 'other').phase).toBe('ready');
  expect(lessonVideoState(lesson, [{ ...task, lessonId: 'other' }], 'teacher').phase).toBe('ready');
  expect(lessonVideoState({ ...lesson, videoUpload: { id: 'new-job', status: 'ready', createdAt: new Date(3000).toISOString() } },
    [{ ...task, status: 'error' }], 'teacher').phase).toBe('ready');
});

it('shows the failure reason and never declares a missing video ready', () => {
  expect(lessonVideoState(lesson, [{ ...task, status: 'error', error: 'انقطع الاتصال' }], 'teacher')).toMatchObject({ phase: 'error', label: 'انقطع الاتصال' });
  expect(lessonVideoState({ ...lesson, hasUploadedVideo: false, videoUrl: '' }, [], 'teacher').phase).toBe('missing');
});

it('authoritative completion of the same job clears stale local processing or errors', () => {
  const ready = { ...lesson, videoUpload: { id: 'job', status: 'ready', createdAt: new Date(1000).toISOString() } };
  for (const status of ['processing', 'error'] as const) {
    expect(lessonVideoState(ready, [{ ...task, videoUploadId: 'job', status }], 'teacher').phase).toBe('ready');
  }
  expect(lessonVideoState(ready, [{ ...task, videoUploadId: 'replacement', status: 'processing' }], 'teacher').phase).toBe('processing');
});
it('maps real server work into the same overall bar without technical quality labels', () => {
  const result = lessonVideoState({ ...lesson, videoUpload: { id: 'job', status: 'processing', createdAt: new Date(3000).toISOString(), processing_percent: 40, processing_stage: 'encoding:360p:3:6' } }, [], 'teacher');
  expect(result.percent).toBe(41); expect(result.label).toBe('جاري رفع الفيديو…');
});

it('keeps the highest observed overall percentage when a worker retries and never exposes 100 before ready', () => {
  const processing = { ...lesson, videoUpload: { id: 'job', status: 'processing', createdAt: new Date(1000).toISOString(), processing_percent: 10 } };
  const local = { ...task, videoUploadId: 'job', status: 'processing' as const, progress: 86 };
  expect(lessonVideoState(processing, [local], 'teacher').percent).toBe(86);
  expect(lessonVideoState({ ...processing, videoUpload: { ...processing.videoUpload, processing_percent: 100 } }, [], 'teacher').percent).toBe(99);
});
