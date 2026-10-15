import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactElement } from 'react';
import { CornerDownLeft } from 'lucide-react';
import type { CurrentUser } from '../types/lms';
import { apiRequest } from '../services/apiClient';
import { useToast } from './ToastProvider';
import { realtimeService } from '../services/realtimeService';
import './LessonDiscussion.css';
import { useTranslation } from '../utils/i18n';

interface ServerComment {
  id: string;
  author: string;
  body: string;
  created_at: string | null;
  is_teacher: boolean;
  replies?: ServerComment[];
}

function validateComment(comment: ServerComment): ServerComment {
  if (!comment || !/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(comment.id)
      || typeof comment.body !== 'string' || typeof comment.author !== 'string') {
    throw new Error('Invalid saved discussion response');
  }
  return { ...comment, replies: (comment.replies ?? []).map(validateComment) };
}

function CommentText({ comment }: { comment: ServerComment }) {
  const { t, lang } = useTranslation();
  const date = comment.created_at ? new Date(comment.created_at) : null;
  return <>
    <div className="discussion-author">
      <strong>{comment.author}</strong>
      {comment.is_teacher && <span className="discussion-teacher">{t('lesson.teacher')}</span>}
      <time dateTime={date && Number.isFinite(date.valueOf()) ? date.toISOString() : undefined}>
        {date && Number.isFinite(date.valueOf()) ? date.toLocaleString(lang === 'ar' ? 'ar-EG' : 'en-GB', { timeZone: 'Africa/Cairo' }) : t('lesson.noCommentDate')}
      </time>
    </div>
    <p className="discussion-body">{comment.body}</p>
  </>;
}

/** Own discussion persistence independently of player/token/telemetry state. */
export function LessonDiscussion({ lessonId, currentUser, onSummary }: {
  lessonId: string;
  currentUser?: CurrentUser | null;
  onSummary?: (summary: { count: number; unread: number }) => void;
}) {
  const toast = useToast();
  const { t: tr } = useTranslation();
  const [comments, setComments] = useState<ServerComment[]>([]);
  const [draft, setDraft] = useState('');
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [replyTarget, setReplyTarget] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savingReply, setSavingReply] = useState<string | null>(null);
  const scopeRef = useRef<object | null>(null);
  const writeRef = useRef<object | null>(null);
  const userId = currentUser?.id;
  const loadSequence = useRef(0);

  const load = useCallback(async (quiet = false) => {
    const scope = scopeRef.current;
    if (!scope) return;
    const sequence = ++loadSequence.current;
    if (!quiet) setLoading(true);
    setLoadError(false);
    try {
      const result = await apiRequest<{ comments: ServerComment[]; unread_count?: number }>(`/lessons/${lessonId}/comments`, { skipCache: true });
      if (scopeRef.current !== scope || sequence !== loadSequence.current) return;
      if (!Array.isArray(result.comments)) throw new Error('Invalid discussion response');
      const saved = result.comments.map(validateComment);
      setComments(saved);
      onSummary?.({ count: countComments(saved), unread: Math.max(0, result.unread_count ?? 0) });
    } catch {
      if (scopeRef.current === scope && sequence === loadSequence.current) setLoadError(true);
    } finally {
      if (scopeRef.current === scope && sequence === loadSequence.current) setLoading(false);
    }
  }, [lessonId, onSummary]);

  useEffect(() => {
    const scope = {};
    scopeRef.current = scope;
    writeRef.current = null;
    setComments([]);
    setDraft('');
    setReplyDrafts({});
    setReplyTarget(null);
    setMutationError(null);
    setSaving(false);
    setSavingReply(null);
    void load();
    return () => { if (scopeRef.current === scope) scopeRef.current = null; };
  }, [lessonId, userId, load]);

  useEffect(() => {
    if (!userId) return;
    let timer: number | undefined;
    const schedule = () => {
      if (timer !== undefined) return;
      timer = window.setTimeout(() => { timer = undefined; void load(true); }, 300);
    };
    const offComment = realtimeService.on<{ lesson_id: string }>('lesson_comment_created', data => {
      if (data.lesson_id === lessonId) schedule();
    });
    const offStatus = realtimeService.on<{ status: string }>('status', data => {
      if (data.status === 'connected') schedule();
    });
    const read = (event: Event) => { if ((event as CustomEvent<{ lessonId: string }>).detail?.lessonId === lessonId) schedule(); };
    window.addEventListener('lms_discussion_read', read);
    const clearScope = () => { offComment(); offStatus(); window.removeEventListener('lms_discussion_read', read); window.clearTimeout(timer); scopeRef.current = null; };
    window.addEventListener('lms_auth_scope_updated', clearScope);
    return () => { offComment(); offStatus(); window.removeEventListener('lms_discussion_read', read); window.clearTimeout(timer); window.removeEventListener('lms_auth_scope_updated', clearScope); };
  }, [lessonId, userId, load]);

  async function submitComment(event: FormEvent) {
    event.preventDefault();
    const scope = scopeRef.current;
    const body = draft.trim();
    if (!scope || !userId || !body || loading || loadError || writeRef.current) return;
    writeRef.current = scope;
    setSaving(true);
    setMutationError(null);
    try {
      const result = await apiRequest<ServerComment>(`/lessons/${lessonId}/comments`, {
        method: 'POST', body: JSON.stringify({ body }),
      });
      if (scopeRef.current !== scope) return;
      const saved = validateComment(result);
      setComments(previous => [saved, ...previous.filter(item => item.id !== saved.id)]);
      setDraft('');
      void load(true);
      toast(tr('lesson.commentSaved'), 'success');
    } catch {
      if (scopeRef.current !== scope) return;
      setMutationError(tr('lesson.commentPreserved'));
      toast(tr('lesson.commentError'), 'danger');
    } finally {
      if (scopeRef.current === scope) { writeRef.current = null; setSaving(false); }
    }
  }

  async function submitReply(event: FormEvent, parentId: string) {
    event.preventDefault();
    const scope = scopeRef.current;
    const body = replyDrafts[parentId]?.trim();
    if (!scope || !userId || !body || loading || loadError || writeRef.current) return;
    writeRef.current = scope;
    setSavingReply(parentId);
    setMutationError(null);
    try {
      const result = await apiRequest<ServerComment>(`/lessons/${lessonId}/comments`, {
        method: 'POST', body: JSON.stringify({ body, parent_id: parentId }),
      });
      if (scopeRef.current !== scope) return;
      const saved = validateComment(result);
      const insert = (items: ServerComment[]): ServerComment[] => items.map(parent => parent.id === parentId ? {
        ...parent, replies: [...(parent.replies ?? []).filter(item => item.id !== saved.id), saved],
      } : { ...parent, replies: insert(parent.replies ?? []) });
      setComments(insert);
      setReplyDrafts(previous => ({ ...previous, [parentId]: '' }));
      setReplyTarget(null);
      void load(true);
      toast(tr('lesson.replySaved'), 'success');
    } catch {
      if (scopeRef.current !== scope) return;
      setMutationError(tr('lesson.replyPreserved'));
      toast(tr('lesson.replyError'), 'danger');
    } finally {
      if (scopeRef.current === scope) { writeRef.current = null; setSavingReply(null); }
    }
  }

  const busy = loading || saving || savingReply !== null;
  const ordered = [...comments].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '') || b.id.localeCompare(a.id));
  const count = countComments(comments);
  const renderComment = (comment: ServerComment, depth = 0): ReactElement => <article key={comment.id} data-comment-id={comment.id}
    style={depth >= 2 ? { padding: '12px 0', borderInline: 0, borderRadius: 0, background: 'transparent' } : undefined}>
    <CommentText comment={comment} />
    <button type="button" className="discussion-reply-toggle" disabled={busy || loadError || !userId || depth >= 7}
      aria-expanded={replyTarget === comment.id}
      onClick={() => setReplyTarget(previous => previous === comment.id ? null : comment.id)}>
      <CornerDownLeft size={14} aria-hidden="true" />{tr('lesson.reply')}
    </button>
    {replyTarget === comment.id && <form className="discussion-reply-composer" onSubmit={event => void submitReply(event, comment.id)}>
      <input type="text" aria-label={tr('lesson.replyTo', { author: comment.author })} maxLength={2000}
        placeholder={tr('lesson.replyPlaceholder')} value={replyDrafts[comment.id] ?? ''} disabled={busy}
        onChange={event => setReplyDrafts(previous => ({ ...previous, [comment.id]: event.target.value }))} />
      <button type="submit" disabled={busy || !replyDrafts[comment.id]?.trim()}>{tr(savingReply === comment.id ? 'lesson.sending' : 'lesson.reply')}</button>
    </form>}
    <div className="discussion-replies" style={depth >= 2 ? { marginInlineStart: 0, paddingInlineStart: 0 } : undefined}>
      {comment.replies?.map(reply => renderComment(reply, depth + 1))}
    </div>
  </article>;
  return <section className="lesson-discussion" aria-label={tr('lesson.discussion')}>
    <header className="discussion-header">
      <h3>{tr('lesson.discussion')}{!loading && !loadError ? ` (${count})` : ''}</h3>
    </header>
    {loading && <p role="status">{tr('lesson.discussionLoading')}</p>}
    {loadError && <div role="alert" className="discussion-error">
      <p>{tr('lesson.discussionLoadError')}</p>
      <button type="button" disabled={busy} onClick={() => void load()}>{tr('lesson.discussionRetry')}</button>
    </div>}
    {mutationError && <p role="alert" className="discussion-error">{mutationError}</p>}
    <form onSubmit={submitComment} className="discussion-composer">
      <input type="text" aria-label={tr('lesson.commentLabel')} maxLength={2000} value={draft}
        disabled={busy || loadError || !userId}
        onChange={event => setDraft(event.target.value)} placeholder={tr('lesson.commentPlaceholder')} />
      <button type="submit" disabled={busy || loadError || !userId || !draft.trim()}>
        {tr(saving ? 'lesson.publishing' : 'lesson.addComment')}
      </button>
    </form>
    {!loading && !loadError && comments.length === 0 && <p className="discussion-empty">
      {tr('lesson.noComments')}
    </p>}
    <div className="discussion-list">{ordered.map(comment => renderComment(comment))}</div>
  </section>;
}

function countComments(items: ServerComment[]): number {
  return items.reduce((sum, item) => sum + 1 + countComments(item.replies ?? []), 0);
}
