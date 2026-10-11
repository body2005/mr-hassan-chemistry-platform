import { Play, Upload } from 'lucide-react';
import type { LessonVideoState } from '../services/lessonVideoState';

export function LessonVideoAction({ state, onWatch, onUpload }: {
  state: LessonVideoState; onWatch: () => void; onUpload: () => void;
}) {
  if (state.phase === 'ready') return <button type="button" onClick={onWatch}
    className="btn-primary" style={{ fontSize: 12, padding: '7px 14px', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
    <Play size={13} fill="currentColor" /><span>مشاهدة الدرس</span>
  </button>;
  if (state.phase === 'uploading' || state.phase === 'processing') return <div
    style={{ flex: 1, minWidth: 140, maxWidth: 280, fontSize: 12, color: 'var(--text-main)' }}>
    <span role="status">{state.label}</span>
    <progress aria-label={state.phase === 'uploading' ? 'رفع الفيديو' : 'تجهيز الفيديو'}
      max={100} value={state.phase === 'uploading' ? state.percent : undefined}
      style={{ display: 'block', width: '100%', height: 8, marginTop: 6, accentColor: '#059669' }} />
  </div>;
  return <div style={{ fontSize: 12, maxWidth: 280 }}>
    <p role={state.phase === 'error' ? 'alert' : undefined} style={{ margin: '0 0 6px', color: 'var(--text-main)' }}>{state.label}</p>
    <button type="button" className="btn-secondary" onClick={onUpload}>
      <Upload size={13} /> {state.phase === 'error' ? 'إعادة رفع الفيديو' : 'رفع فيديو'}
    </button>
  </div>;
}
