import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { CornerDownLeft } from 'lucide-react';
import type { CurrentUser } from '../types/lms';
import { apiRequest } from '../services/apiClient';
import { useToast } from './ToastProvider';
import { realtimeService } from '../services/realtimeService';
import './LessonDiscussion.css';

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
  const date = comment.created_at ? new Date(comment.created_at) : null;
  return <>
    <div className="discussion-author">
      <strong>{comment.author}</strong>
      {comment.is_teacher && <span className="discussion-teacher">المعلم</span>}
      <time dateTime={date && Number.isFinite(date.valueOf()) ? date.toISOString() : undefined}>
        {date && Number.isFinite(date.valueOf()) ? date.toLocaleString('ar-EG') : 'وقت التعليق غير متاح'}
      </time>
    </div>
    <p className="discussion-body">{comment.body}</p>
  </>;
}

/** Own discussion persistence independently of player/token/telemetry state. */
export function LessonDiscussion({ lessonId, currentUser }: {
  lessonId: string;
  currentUser?: CurrentUser | null;
}) {
  const toast = useToast();
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
      const result = await apiRequest<{ comments: ServerComment[] }>(`/lessons/${lessonId}/comments`, { skipCache: true });
      if (scopeRef.current !== scope || sequence !== loadSequence.current) return;
      if (!Array.isArray(result.comments)) throw new Error('Invalid discussion response');
      setComments(result.comments.map(validateComment));
    } catch {
      if (scopeRef.current === scope && sequence === loadSequence.current) setLoadError(true);
    } finally {
      if (scopeRef.current === scope && sequence === loadSequence.current) setLoading(false);
    }
  }, [lessonId]);

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
    const clearScope = () => { offComment(); offStatus(); window.clearTimeout(timer); scopeRef.current = null; };
    window.addEventListener('lms_auth_scope_updated', clearScope);
    return () => { offComment(); offStatus(); window.clearTimeout(timer); window.removeEventListener('lms_auth_scope_updated', clearScope); };
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
      toast('تم إضافة تعليقك بنجاح', 'success');
    } catch {
      if (scopeRef.current !== scope) return;
      setMutationError('تعذر نشر التعليق؛ النص محفوظ. يمكنك إعادة المحاولة يدويًا.');
      toast('تعذر نشر التعليق، حاول مجدداً', 'danger');
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
      setComments(previous => previous.map(parent => parent.id === parentId ? {
        ...parent, replies: [...(parent.replies ?? []).filter(item => item.id !== saved.id), saved],
      } : parent));
      setReplyDrafts(previous => ({ ...previous, [parentId]: '' }));
      setReplyTarget(null);
      toast('تم إرسال الرد بنجاح', 'success');
    } catch {
      if (scopeRef.current !== scope) return;
      setMutationError('تعذر إرسال الرد؛ النص محفوظ. يمكنك إعادة المحاولة يدويًا.');
      toast('تعذر إرسال الرد، حاول مجدداً', 'danger');
    } finally {
      if (scopeRef.current === scope) { writeRef.current = null; setSavingReply(null); }
    }
  }

  const busy = loading || saving || savingReply !== null;
  const ordered = [...comments].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '') || b.id.localeCompare(a.id));
  const count = comments.reduce((sum, item) => sum + 1 + (item.replies?.length ?? 0), 0);
  return <section className="lesson-discussion" aria-label="التعليقات والمناقشات">
    <header className="discussion-header">
      <h3>التعليقات والمناقشات{!loading && !loadError ? ` (${count})` : ''}</h3>
    </header>
    {loading && <p role="status">جارٍ تحميل المناقشة...</p>}
    {loadError && <div role="alert" className="discussion-error">
      <p>تعذر تحميل المناقشة. لا يعني ذلك عدم وجود تعليقات.</p>
      <button type="button" disabled={busy} onClick={() => void load()}>إعادة تحميل المناقشة</button>
    </div>}
    {mutationError && <p role="alert" className="discussion-error">{mutationError}</p>}
    <form onSubmit={submitComment} className="discussion-composer">
      <input type="text" aria-label="تعليقك على الدرس" maxLength={2000} value={draft}
        disabled={busy || loadError || !userId}
        onChange={event => setDraft(event.target.value)} placeholder="اكتب سؤالك أو تعليقك حول هذا الدرس..." />
      <button type="submit" disabled={busy || loadError || !userId || !draft.trim()}>
        {saving ? 'جاري النشر...' : 'إضافة تعليق'}
      </button>
    </form>
    {!loading && !loadError && comments.length === 0 && <p className="discussion-empty">
      لا توجد تعليقات بعد على هذا الدرس — كن أول من يطرح سؤاله أو استفساره.
    </p>}
    <div className="discussion-list">{ordered.map(comment => <article key={comment.id} data-comment-id={comment.id}>
      <CommentText comment={comment} />
      <button type="button" className="discussion-reply-toggle" disabled={busy || loadError || !userId}
        aria-expanded={replyTarget === comment.id}
        onClick={() => setReplyTarget(previous => previous === comment.id ? null : comment.id)}>
        <CornerDownLeft size={14} aria-hidden="true" />رد
      </button>
      {replyTarget === comment.id && <form className="discussion-reply-composer" onSubmit={event => void submitReply(event, comment.id)}>
        <input type="text" aria-label={`الرد على تعليق ${comment.author}`} maxLength={2000}
          placeholder="اكتب ردك هنا..." value={replyDrafts[comment.id] ?? ''} disabled={busy}
          onChange={event => setReplyDrafts(previous => ({ ...previous, [comment.id]: event.target.value }))} />
        <button type="submit" disabled={busy || !replyDrafts[comment.id]?.trim()}>
          {savingReply === comment.id ? 'جاري الإرسال...' : 'رد'}
        </button>
      </form>}
      <div className="discussion-replies">{comment.replies?.map(reply => <article key={reply.id} data-comment-id={reply.id}>
        <CommentText comment={reply} />
      </article>)}</div>
    </article>)}</div>
  </section>;
}
