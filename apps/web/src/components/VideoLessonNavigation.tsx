import { ArrowRight, ChevronLeft } from 'lucide-react';
import type { CSSProperties } from 'react';

type Props = {
  courseTitle: string;
  lessonTitle: string;
  isTeacher: boolean;
  onClose: () => void;
};

const navigationButton: CSSProperties = {
  background: 'transparent', border: 'none', color: 'var(--text-main, #0f172a)',
  font: 'inherit', fontWeight: 700, cursor: 'pointer', padding: '2px 4px',
  borderRadius: '4px', minWidth: 0, overflowWrap: 'anywhere',
};

/** Navigation owns layout/keyboard semantics, not playback or auth state. */
export function VideoLessonNavigation({ courseTitle, lessonTitle, isTeacher, onClose }: Props) {
  return <div style={{
    background: 'var(--bg-surface, #ffffff)', borderBottom: '1px solid var(--border-color, #e2e8f0)',
    padding: '9px 24px', position: 'sticky', top: '-4px', zIndex: 40,
  }}>
    <div style={{
      maxWidth: '1400px', margin: '0 auto', display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px',
    }}>
      <nav aria-label="Breadcrumb" style={{
        display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px',
        flexWrap: 'wrap', minWidth: 0, maxWidth: '100%',
      }}>
        <button type="button" onClick={onClose} style={navigationButton}>الرئيسية</button>
        <ChevronLeft size={14} aria-hidden="true" style={{ color: 'var(--text-muted, #64748b)', flexShrink: 0 }} />
        <button type="button" onClick={onClose} style={navigationButton}>{courseTitle}</button>
        <ChevronLeft size={14} aria-hidden="true" style={{ color: 'var(--text-muted, #64748b)', flexShrink: 0 }} />
        <span aria-current="page" style={{
          color: 'var(--text-main, #0f172a)', fontWeight: 800, maxWidth: 'min(320px, 100%)',
          minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{lessonTitle}</span>
      </nav>
      <button type="button" onClick={onClose} style={{
        display: 'inline-flex', alignItems: 'center', gap: '6px',
        background: 'var(--bg-surface-secondary, #f1f5f9)', border: '1px solid var(--border-color, #e2e8f0)',
        borderRadius: '10px', padding: '7px 14px', fontSize: '12.5px', fontWeight: 800,
        color: 'var(--text-main, #0f172a)', cursor: 'pointer', transition: 'background 0.2s ease',
      }}>
        <ArrowRight size={15} aria-hidden="true" />
        <span>{isTeacher ? 'رجوع لإدارة الدروس' : 'رجوع للمقرر'}</span>
      </button>
    </div>
  </div>;
}
