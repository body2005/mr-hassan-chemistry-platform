import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import type Hls from 'hls.js';
import type { VideoLesson } from '../types/lms';
import { apiRequest, apiUrl, getApiAuthGeneration, getApiAuthScope } from '../services/apiClient';
import { playbackFailureMessage } from '../services/playbackFailure';

/** Own token admission/renewal and its auth generation, not the media UI. */
export function useProtectedPlayback(lesson: VideoLesson, userId: string | undefined,
  videoRef: RefObject<HTMLVideoElement | null>, hlsRef: RefObject<Hls | null>) {
  const [playbackUrl, setPlaybackUrl] = useState('');
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [authGeneration, setAuthGeneration] = useState(getApiAuthGeneration);
  const scopeRef = useRef<{ controller: AbortController; generation: number } | null>(null);
  const renewing = useRef(false);
  const lastRenewal = useRef(0);
  const pendingPlaybackResumeRef = useRef<{ time: number; playing: boolean } | null>(null);

  useEffect(() => {
    const onScopeChange = () => {
      scopeRef.current?.controller.abort();
      scopeRef.current = null;
      renewing.current = false;
      pendingPlaybackResumeRef.current = null;
      hlsRef.current?.stopLoad();
      const video = videoRef.current;
      video?.pause();
      video?.removeAttribute('src');
      setPlaybackUrl('');
      setAuthGeneration(getApiAuthGeneration());
      setPlaybackError(getApiAuthScope() === 'anonymous' ? playbackFailureMessage({ status: 401 }) : null);
    };
    window.addEventListener('lms_auth_scope_updated', onScopeChange);
    return () => window.removeEventListener('lms_auth_scope_updated', onScopeChange);
  }, [videoRef, hlsRef]);

  useEffect(() => {
    const scope = { controller: new AbortController(), generation: getApiAuthGeneration() };
    scopeRef.current = scope;
    renewing.current = false;
    lastRenewal.current = 0;
    pendingPlaybackResumeRef.current = null;
    setPlaybackUrl('');
    setPlaybackError(null);
    if (getApiAuthScope() === 'anonymous' && lesson.requiresProtectedPlayback) {
      setPlaybackError(playbackFailureMessage({ status: 401 }));
    } else if (!lesson.videoUrl && !lesson.requiresProtectedPlayback) {
      setPlaybackError('لا يوجد فيديو جاهز لهذا الدرس بعد. إذا كنت قد رفعته، تحقق من اكتمال الرفع والمعالجة في إدارة الدروس ثم حدّث الصفحة.');
    } else if (!lesson.requiresProtectedPlayback) {
      setPlaybackUrl(lesson.videoUrl);
    } else {
      void apiRequest<{ stream_url: string }>(`/lessons/${lesson.id}/video-token`, { method: 'POST', signal: scope.controller.signal })
        .then(({ stream_url }) => { if (scopeRef.current === scope) setPlaybackUrl(apiUrl(stream_url)); })
        .catch(error => { if (scopeRef.current === scope) setPlaybackError(playbackFailureMessage(error)); });
    }
    return () => {
      scope.controller.abort();
      if (scopeRef.current === scope) scopeRef.current = null;
    };
  }, [lesson.id, lesson.videoUrl, lesson.requiresProtectedPlayback, userId, authGeneration]);

  const renewProtectedPlayback = useCallback(async (manual = false): Promise<boolean> => {
    const scope = scopeRef.current;
    if (!scope || getApiAuthScope() === 'anonymous' || !lesson.requiresProtectedPlayback || renewing.current) return false;
    if (!manual && Date.now() - lastRenewal.current < 10000) {
      setPlaybackError('تعذر تشغيل الفيديو. أعد المحاولة بعد قليل.');
      return false;
    }
    lastRenewal.current = Date.now();
    renewing.current = true;
    const video = videoRef.current;
    const resume = { time: video?.currentTime ?? 0, playing: Boolean(video && !video.paused) };
    try {
      const { stream_url } = await apiRequest<{ stream_url: string }>(`/lessons/${lesson.id}/video-token`, { method: 'POST', signal: scope.controller.signal });
      if (scopeRef.current !== scope || scope.generation !== getApiAuthGeneration()) return false;
      pendingPlaybackResumeRef.current = resume;
      setPlaybackError(null);
      setPlaybackUrl(apiUrl(stream_url));
      return true;
    } catch (error) {
      if (scopeRef.current !== scope) return false;
      hlsRef.current?.stopLoad();
      setPlaybackError(playbackFailureMessage(error));
      return false;
    } finally {
      if (scopeRef.current === scope) renewing.current = false;
    }
  }, [lesson.id, lesson.requiresProtectedPlayback, videoRef, hlsRef]);

  useEffect(() => {
    if (!playbackUrl.includes('/hls/') || !lesson.requiresProtectedPlayback) return;
    // One finite renewal, no automatic replay on 401/429 or network failure.
    const timer = window.setTimeout(() => { void renewProtectedPlayback(); }, 240000);
    return () => window.clearTimeout(timer);
  }, [playbackUrl, lesson.requiresProtectedPlayback, renewProtectedPlayback]);
  return { playbackUrl, playbackError, setPlaybackError, renewProtectedPlayback, pendingPlaybackResumeRef };
}
