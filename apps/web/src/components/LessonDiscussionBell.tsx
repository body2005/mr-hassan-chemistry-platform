import { Bell } from 'lucide-react';

export const discussionIntentKey = 'lms_open_lesson_discussion';

/** A lesson identifier is navigation intent only, never an access grant. */
export function LessonDiscussionBell({ lessonId, unread = 0, onOpen }: {
  lessonId: string; unread?: number; onOpen: () => void;
}) {
  return <button type="button" className="btn-secondary"
    aria-label={`فتح التعليقات؛ ${unread} إشعارات غير مقروءة`} title="التعليقات وإشعارات الردود"
    style={{ minWidth: 44, minHeight: 44, padding: 8, display: 'inline-flex', gap: 4, alignItems: 'center', justifyContent: 'center' }}
    onClick={event => {
      event.stopPropagation();
      try { sessionStorage.setItem(discussionIntentKey, lessonId); } catch { /* The authorized player can still open. */ }
      onOpen();
    }}>
    <Bell size={18} aria-hidden="true" /><span>{unread}</span>
  </button>;
}
