import type { VideoLesson } from '../types/lms';
import type { UploadTask } from './uploadManager';
import { VIDEO_UPLOAD_LABEL, videoOverallProgress } from './directVideoUpload';

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
  if (server?.id === local?.videoUploadId && server && ['failed', 'rejected', 'expired', 'aborted', 'cancelled', 'superseded'].includes(server.status)) {
    return { phase: 'error', label: 'لم يكتمل رفع الفيديو؛ أعد المحاولة' };
  }
  if (local?.status === 'queued' || local?.status === 'uploading') {
    return { phase: 'uploading', label: VIDEO_UPLOAD_LABEL, percent: Math.min(99, local.progress ?? videoOverallProgress(local.uploadPercent)) };
  }
  if (local?.status === 'processing') {
    const serverPercent = server?.id === local.videoUploadId ? videoOverallProgress(100, server?.processing_percent ?? 0) : 0;
    return { phase: 'processing', label: VIDEO_UPLOAD_LABEL, percent: Math.min(99, Math.max(local.progress ?? videoOverallProgress(100, 0), serverPercent)) };
  }
  if (local?.status === 'error') return { phase: 'error', label: local.error || 'تعذر إكمال رفع الفيديو؛ أعد المحاولة' };
  if (server && ['creating', 'uploading', 'completing'].includes(server.status)) {
    return { phase: 'uploading', label: VIDEO_UPLOAD_LABEL, percent: server.status === 'completing' ? 40 : undefined };
  }
  if (server && ['queued', 'processing'].includes(server.status)) {
    return { phase: 'processing', label: VIDEO_UPLOAD_LABEL, percent: videoOverallProgress(100, server.processing_percent ?? 0) };
  }
  if (server && ['failed', 'rejected', 'expired', 'aborted', 'cancelled', 'superseded'].includes(server.status)) {
    return { phase: 'error', label: 'لم يكتمل رفع الفيديو؛ أعد المحاولة' };
  }
  if (lesson.hasUploadedVideo || lesson.videoUrl) return { phase: 'ready', label: 'جاهز للتشغيل' };
  if (local?.status === 'completed') return { phase: 'processing', label: VIDEO_UPLOAD_LABEL, percent: 99 };
  return { phase: 'missing', label: 'لا يوجد فيديو مرفوع' };
}
