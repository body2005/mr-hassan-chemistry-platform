import { Play, Upload } from 'lucide-react';
import type { LessonVideoState } from '../services/lessonVideoState';
import { VideoUploadProgress } from './VideoUploadProgress';
import { LessonDiscussionBell } from './LessonDiscussionBell';

export function LessonVideoAction({ state, onWatch, onUpload, lessonId, discussionUnreadCount }: {
  state: LessonVideoState; onWatch: () => void; onUpload: () => void;
  lessonId?: string; discussionUnreadCount?: number;
}) {
  if (state.phase === 'ready') return <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
    <button type="button" onClick={onWatch} className="btn-primary"
      style={{ fontSize: 12, padding: '7px 14px', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <Play size={13} fill="currentColor" /><span>مشاهدة الدرس</span>
    </button>
    {lessonId && <LessonDiscussionBell lessonId={lessonId} unread={discussionUnreadCount} onOpen={onWatch} />}
  </div>;
  if (state.phase === 'uploading' || state.phase === 'processing') return <div
    style={{ flex: 1, minWidth: 140, maxWidth: 280, fontSize: 12, color: 'var(--text-main)' }}>
    <VideoUploadProgress percent={state.percent} />
  </div>;
  return <div style={{ fontSize: 12, maxWidth: 280 }}>
    <p role={state.phase === 'error' ? 'alert' : undefined} style={{ margin: '0 0 6px', color: 'var(--text-main)' }}>{state.label}</p>
    <button type="button" className="btn-secondary" onClick={onUpload}>
      <Upload size={13} /> {state.phase === 'error' ? 'إعادة المحاولة' : 'رفع فيديو'}
    </button>
  </div>;
}
