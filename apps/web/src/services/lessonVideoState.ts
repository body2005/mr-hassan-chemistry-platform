import type { VideoLesson } from '../types/lms';
import type { UploadTask } from './uploadManager';

export interface LessonVideoState {
  phase: 'ready' | 'uploading' | 'processing' | 'error' | 'missing';
  label: string;
  percent?: number;
}

export function lessonVideoState(lesson: VideoLesson, tasks: UploadTask[], ownerScope: string): LessonVideoState {
  const server = lesson.videoUpload;
  const task = tasks.filter(task => task.type === 'lesson_video' && task.lessonId === lesson.id &&
    ownerScope !== 'anonymous' && task.ownerScope === ownerScope)
    .sort((a, b) => b.createdAt - a.createdAt)[0];
  // A later upload from another tab supersedes a stale local failure/completion.
  const local = task && (!server || task.videoUploadId === server.id || task.createdAt >= Date.parse(server.createdAt))
    ? task : undefined;
  if (local?.status === 'queued' || local?.status === 'uploading') {
    const percent = Math.round(Math.max(0, Math.min(100, local.uploadPercent)));
    return { phase: 'uploading', label: local.status === 'queued' ? 'في انتظار رفع الفيديو' : `جارٍ رفع الفيديو ${percent}٪`, percent };
  }
  if (local?.status === 'processing') return { phase: 'processing', label: 'جارٍ إكمال الرفع وتجهيز الفيديو تلقائيًا' };
  if (local?.status === 'error') return { phase: 'error', label: local.error || 'تعذر إكمال رفع الفيديو؛ أعد المحاولة' };
  if (server && ['creating', 'uploading', 'completing'].includes(server.status)) {
    return { phase: 'uploading', label: 'جارٍ رفع الفيديو' };
  }
  if (server && ['queued', 'processing'].includes(server.status)) {
    return { phase: 'processing', label: 'جارٍ تجهيز الفيديو تلقائيًا' };
  }
  if (server && ['failed', 'rejected', 'expired', 'aborted'].includes(server.status)) {
    return { phase: 'error', label: 'لم يكتمل تجهيز الفيديو؛ أعد رفع الملف للمحاولة مجددًا' };
  }
  if (lesson.hasUploadedVideo || lesson.videoUrl) return { phase: 'ready', label: 'جاهز للتشغيل' };
  if (local?.status === 'completed') return { phase: 'processing', label: 'جارٍ تحديث بيانات الفيديو' };
  return { phase: 'missing', label: 'لا يوجد فيديو مرفوع' };
}
