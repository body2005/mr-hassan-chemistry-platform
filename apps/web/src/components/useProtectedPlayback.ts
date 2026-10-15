import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import type Hls from 'hls.js';
import type { VideoLesson } from '../types/lms';
import { apiRequest, apiUrl, getApiAuthGeneration, getApiAuthScope, getApiSessionRevision } from '../services/apiClient';
import { playbackFailureMessage } from '../services/playbackFailure';
import type { VideoDrmDescriptor } from '../services/videoDrm';

type PlaybackAdmission = { stream_url: string; expires_in?: number; drm?: VideoDrmDescriptor | null };

/** Own token admission/renewal and its auth generation, not the media UI. */
export function useProtectedPlayback(lesson: VideoLesson, userId: string | undefined,
  videoRef: RefObject<HTMLVideoElement | null>, hlsRef: RefObject<Hls | null>) {
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [authGeneration, setAuthGeneration] = useState(getApiAuthGeneration);
  const playbackKey = JSON.stringify([lesson.id, lesson.videoUrl, lesson.requiresProtectedPlayback, userId, authGeneration]);
  const [source, setSource] = useState({ key: '', url: '' });
  const [drmAdmission, setDrmAdmission] = useState<{ key: string; value?: VideoDrmDescriptor }>({ key: '' });
  const drm = drmAdmission.key === playbackKey ? drmAdmission.value : undefined;
  const playbackUrl = source.key === playbackKey ? source.url : '';
  const setPlaybackUrl = useCallback((url: string) => setSource({ key: playbackKey, url }), [playbackKey]);
  const scopeRef = useRef<{ controller: AbortController; generation: number } | null>(null);
  const renewing = useRef<Promise<boolean> | null>(null);
  const credential = useRef<{ key: string; url: string; renewAt: number; sessionRevision: string } | null>(null);
  const [renewAt, setRenewAt] = useState(0);
  const rememberCredential = useCallback((reply: PlaybackAdmission) => {
    const url = apiUrl(reply.stream_url);
    let descriptor: VideoDrmDescriptor | undefined;
    if (reply.drm) {
      if (reply.drm.scheme !== 'cbcs') throw new Error('Unsupported DRM scheme');
      const normalize = (resource: string) => {
        const endpoint = new URL(apiUrl(resource), window.location.href);
        const admitted = new URL(url, window.location.href);
        const prefix = admitted.pathname.slice(0, admitted.pathname.lastIndexOf('/') + 1);
        if (!prefix.includes('/hls/') || endpoint.origin !== admitted.origin || !endpoint.pathname.startsWith(`${prefix}drm/`)) {
          throw new Error('Unexpected DRM resource');
        }
        // Renewal updates admission, without recreating EME/MediaSource merely
        // because the signed query changed. Every request gets a fresh token.
        endpoint.searchParams.delete('token');
        return endpoint.href;
      };
      descriptor = { scheme: 'cbcs', widevine_license_url: normalize(reply.drm.widevine_license_url),
        fairplay_license_url: normalize(reply.drm.fairplay_license_url),
        fairplay_certificate_url: normalize(reply.drm.fairplay_certificate_url) };
    }
    setDrmAdmission(previous => previous.key === playbackKey && JSON.stringify(previous.value) === JSON.stringify(descriptor)
      ? previous : { key: playbackKey, value: descriptor });
    const ttl = Number.isFinite(reply.expires_in) && (reply.expires_in ?? 0) > 0 ? reply.expires_in! : 300;
    const deadline = Date.now() + Math.max(1, Math.min(ttl * .8, ttl - 15)) * 1000;
    credential.current = { key: playbackKey, url, renewAt: deadline, sessionRevision: getApiSessionRevision() };
    setRenewAt(deadline);
    return url;
  }, [playbackKey]);
  const lastRenewal = useRef(0);
  const automaticDenied = useRef(false);
  const retryAllowedAt = useRef(0);
  const recordDenial = (error: unknown) => {
    const failure = error as { status?: number; retryAfterMs?: number } | null;
    if (failure && [401, 403, 404, 429].includes(failure.status || 0)) automaticDenied.current = true;
    if (failure?.status === 429) retryAllowedAt.current = Date.now() + Math.max(1000, failure.retryAfterMs ?? 30000);
  };
  const pendingPlaybackResumeRef = useRef<{ time: number; playing: boolean } | null>(null);

  useEffect(() => {
    const onScopeChange = () => {
      scopeRef.current?.controller.abort();
      scopeRef.current = null;
      renewing.current = null;
      credential.current = null;
      setRenewAt(0);
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
  }, [videoRef, hlsRef, setPlaybackUrl]);

  useEffect(() => {
    const scope = { controller: new AbortController(), generation: getApiAuthGeneration() };
    scopeRef.current = scope;
    renewing.current = null;
    credential.current = null;
    setRenewAt(0);
    lastRenewal.current = 0;
    automaticDenied.current = false;
    retryAllowedAt.current = 0;
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
      void apiRequest<PlaybackAdmission>(`/lessons/${lesson.id}/video-token`, { method: 'POST', signal: scope.controller.signal })
        .then(reply => { if (scopeRef.current === scope) setPlaybackUrl(rememberCredential(reply)); })
        .catch(error => { if (scopeRef.current === scope) { recordDenial(error); setPlaybackError(playbackFailureMessage(error)); } });
    }
    return () => {
      scope.controller.abort();
      if (scopeRef.current === scope) scopeRef.current = null;
    };
  }, [lesson.id, lesson.videoUrl, lesson.requiresProtectedPlayback, userId, authGeneration, setPlaybackUrl, rememberCredential]);

  const renewProtectedPlayback = useCallback((manual = false, keepBuffer = false): Promise<boolean> => {
    const scope = scopeRef.current;
    if (!scope || getApiAuthScope() === 'anonymous' || !lesson.requiresProtectedPlayback) return Promise.resolve(false);
    if (renewing.current) return renewing.current;
    if (Date.now() < retryAllowedAt.current || (!manual && automaticDenied.current)) return Promise.resolve(false);
    const sessionChanged = credential.current?.sessionRevision !== getApiSessionRevision();
    if (!manual && !sessionChanged && Date.now() - lastRenewal.current < 10000) {
      setPlaybackError('تعذر تشغيل الفيديو. أعد المحاولة بعد قليل.');
      return Promise.resolve(false);
    }
    lastRenewal.current = Date.now();
    const video = videoRef.current;
    const resume = { time: video?.currentTime ?? 0, playing: Boolean(video && !video.paused) };
    const request = (async () => {
    try {
      const reply = await apiRequest<PlaybackAdmission>(`/lessons/${lesson.id}/video-token`, { method: 'POST', signal: scope.controller.signal });
      if (scopeRef.current !== scope || scope.generation !== getApiAuthGeneration()) return false;
      const oldUrl = credential.current?.url;
      const nextUrl = rememberCredential(reply);
      automaticDenied.current = false;
      retryAllowedAt.current = 0;
      setPlaybackError(null);
      const oldAddress = oldUrl ? new URL(oldUrl, window.location.href) : null;
      const nextAddress = new URL(nextUrl, window.location.href);
      const sameGeneration = oldAddress?.origin === nextAddress.origin && oldAddress?.pathname === nextAddress.pathname;
      if (!(keepBuffer && hlsRef.current && sameGeneration)) {
        pendingPlaybackResumeRef.current = resume;
        setPlaybackUrl(nextUrl);
      }
      return true;
    } catch (error) {
      if (scopeRef.current !== scope) return false;
      recordDenial(error);
      hlsRef.current?.stopLoad();
      setPlaybackError(playbackFailureMessage(error));
      return false;
    } finally {
      if (scopeRef.current === scope) renewing.current = null;
    }
    })();
    renewing.current = request;
    return request;
  }, [lesson.id, lesson.requiresProtectedPlayback, videoRef, hlsRef, setPlaybackUrl, rememberCredential]);

  const authorizeHlsRequest = useCallback(async (url: string): Promise<string> => {
    if (!lesson.requiresProtectedPlayback) return url;
    const scope = scopeRef.current;
    if (!scope || scope.controller.signal.aborted || scope.generation !== getApiAuthGeneration() ||
        getApiAuthScope() === 'anonymous' || credential.current?.key !== playbackKey || automaticDenied.current) {
      throw new Error('Playback authorization unavailable');
    }
    if ((Date.now() >= credential.current.renewAt || credential.current.sessionRevision !== getApiSessionRevision()) &&
        !await renewProtectedPlayback(false, true)) {
      throw new Error('Playback renewal failed');
    }
    const current = credential.current;
    if (scopeRef.current !== scope || !current || current.key !== playbackKey) throw new Error('Playback changed');
    const admitted = new URL(current.url, window.location.href);
    const target = new URL(url, window.location.href);
    const prefix = admitted.pathname.slice(0, admitted.pathname.lastIndexOf('/') + 1);
    // Never send a signed token to another origin, lesson or video generation.
    if (!prefix.includes('/hls/') || target.origin !== admitted.origin || !target.pathname.startsWith(prefix)) {
      throw new Error('Unexpected playback resource');
    }
    const token = admitted.searchParams.get('token');
    if (!token) throw new Error('Playback token missing');
    target.searchParams.set('token', token);
    return target.href;
  }, [lesson.requiresProtectedPlayback, playbackKey, renewProtectedPlayback]);

  useEffect(() => {
    const refreshed = () => {
      if (credential.current?.key === playbackKey && credential.current.sessionRevision !== getApiSessionRevision()) {
        void renewProtectedPlayback(false, true);
      }
    };
    const storage = (event: StorageEvent) => { if (event.key === 'lms_session_revision') refreshed(); };
    window.addEventListener('lms_session_refreshed', refreshed);
    window.addEventListener('storage', storage);
    return () => {
      window.removeEventListener('lms_session_refreshed', refreshed);
      window.removeEventListener('storage', storage);
    };
  }, [playbackKey, renewProtectedPlayback]);

  useEffect(() => {
    if (!playbackUrl.includes('/hls/') || !lesson.requiresProtectedPlayback || !renewAt) return;
    // One finite renewal, no automatic replay on 401/429 or network failure.
    const timer = window.setTimeout(() => { void renewProtectedPlayback(false, true); }, Math.max(0, renewAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [playbackUrl, lesson.requiresProtectedPlayback, renewProtectedPlayback, renewAt]);
  return { playbackUrl, drm, playbackError, setPlaybackError, renewProtectedPlayback, pendingPlaybackResumeRef, authorizeHlsRequest };
}
