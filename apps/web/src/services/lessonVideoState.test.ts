import { expect, it } from 'vitest';
import { lessonVideoState } from './lessonVideoState';
import type { VideoLesson } from '../types/lms';
import type { UploadTask } from './uploadManager';

const lesson = { id: 'lesson', hasUploadedVideo: true, videoUrl: '/protected' } as VideoLesson;
const task = { id: 'task', lessonId: 'lesson', ownerScope: 'teacher', type: 'lesson_video', createdAt: 2000,
  uploadPercent: 42, status: 'uploading' } as UploadTask;

it('hides playback during a replacement upload and processing, then restores it on completion', () => {
  expect(lessonVideoState(lesson, [task], 'teacher')).toMatchObject({ phase: 'uploading', percent: 42 });
  expect(lessonVideoState(lesson, [{ ...task, status: 'processing', uploadPercent: 100 }], 'teacher').phase).toBe('processing');
  expect(lessonVideoState(lesson, [{ ...task, status: 'completed' }], 'teacher').phase).toBe('ready');
});

it('restores server processing on reload without inventing a processing percentage', () => {
  const result = lessonVideoState({ ...lesson, videoUpload: { id: 'job', status: 'processing', createdAt: new Date(3000).toISOString() } }, [], 'teacher');
  expect(result.phase).toBe('processing');
  expect(result.percent).toBeUndefined();
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
