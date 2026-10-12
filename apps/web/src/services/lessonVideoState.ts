import type { VideoLesson } from '../types/lms';
import type { UploadTask } from './uploadManager';
import { videoProcessingLabel } from './directVideoUpload';

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
  // The matching job's authoritative completion overrides stale browser state.
  // An older ready job must never hide a newer replacement upload.
  if (server?.id === local?.videoUploadId && server?.status === 'ready') {
    return { phase: 'ready', label: 'جاهز للتشغيل' };
  }
  if (server?.id === local?.videoUploadId && server && ['failed', 'rejected', 'expired', 'aborted', 'superseded'].includes(server.status)) {
    return { phase: 'error', label: 'لم يكتمل تجهيز الفيديو؛ أعد المحاولة' };
  }
  if (local?.status === 'queued' || local?.status === 'uploading') {
    const percent = Math.round(Math.max(0, Math.min(100, local.uploadPercent)));
    return { phase: 'uploading', label: local.status === 'queued' ? 'في انتظار رفع الفيديو' : `جارٍ رفع الفيديو ${percent}٪`, percent };
  }
  if (local?.status === 'processing') {
    const serverIsNewer = server && server.id === local.videoUploadId && (server.processing_percent ?? -1) > local.progress;
    return { phase: 'processing', label: serverIsNewer && server ? videoProcessingLabel(server) : local.statusDetail || (server ? videoProcessingLabel(server) : 'اكتمل الرفع؛ جارٍ تجهيز جودات الفيديو'), percent: serverIsNewer ? server?.processing_percent ?? undefined : local.progress || undefined };
  }
  if (local?.status === 'error') return { phase: 'error', label: local.error || 'تعذر إكمال رفع الفيديو؛ أعد المحاولة' };
  if (server && ['creating', 'uploading', 'completing'].includes(server.status)) {
    return { phase: 'uploading', label: 'جارٍ رفع الفيديو' };
  }
  if (server && ['queued', 'processing'].includes(server.status)) {
    return { phase: 'processing', label: videoProcessingLabel(server), percent: server.processing_percent ?? undefined };
  }
  if (server && ['failed', 'rejected', 'expired', 'aborted'].includes(server.status)) {
    return { phase: 'error', label: 'لم يكتمل تجهيز الفيديو؛ أعد رفع الملف للمحاولة مجددًا' };
  }
  if (lesson.hasUploadedVideo || lesson.videoUrl) return { phase: 'ready', label: 'جاهز للتشغيل' };
  if (local?.status === 'completed') return { phase: 'processing', label: 'جارٍ تحديث بيانات الفيديو' };
  return { phase: 'missing', label: 'لا يوجد فيديو مرفوع' };
}
