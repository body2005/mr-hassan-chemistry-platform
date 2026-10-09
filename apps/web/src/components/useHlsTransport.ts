import { useEffect, type RefObject } from 'react';
import Hls from 'hls.js';
import { playbackFailureMessage } from '../services/playbackFailure';

/** Own one media transport; token admission/renewal remains separate. */
export function useHlsTransport(
  playbackUrl: string,
  videoRef: RefObject<HTMLVideoElement | null>,
  hlsRef: RefObject<Hls | null>,
  setQualityOptions: (options: string[]) => void,
  setSelectedQuality: (quality: string) => void,
  setPlaybackError: (error: string | null) => void,
) {
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (!playbackUrl) {
      // Do not retain the previous lesson's source while admission is pending.
      video.removeAttribute('src');
      return;
    }
    if (!playbackUrl.includes('/hls/')) {
      video.src = playbackUrl;
      setQualityOptions(['الأصلية']);
      setSelectedQuality('الأصلية');
      return;
    }
    if (!Hls.isSupported()) {
      if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = playbackUrl;
        setQualityOptions(['تلقائي']);
        setSelectedQuality('تلقائي');
      } else setPlaybackError('المتصفح لا يدعم البث التكيفي؛ جرّب متصفحًا حديثًا.');
      return;
    }
    let disposed = false;
    const hls = new Hls({
      maxBufferLength: 30,
      maxMaxBufferLength: 60,
      // No automatic error/timeout request loops, including HTTP429.
      manifestLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 20000, timeoutRetry: null, errorRetry: null } },
      playlistLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 20000, timeoutRetry: null, errorRetry: null } },
      fragLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 30000, timeoutRetry: null, errorRetry: null } },
    });
    hlsRef.current = hls;
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      if (disposed) return;
      setQualityOptions(['تلقائي', ...hls.levels.map(level => `${level.height}p`)]);
      setSelectedQuality('تلقائي');
    });
    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (disposed) return;
      if (data.fatal || [401, 403, 429].includes(data.response?.code || 0)) {
        hls.stopLoad();
        setPlaybackError(playbackFailureMessage({ status: data.response?.code }));
      }
    });
    hls.attachMedia(video);
    hls.loadSource(playbackUrl);
    return () => {
      disposed = true;
      hls.destroy();
      if (hlsRef.current === hls) hlsRef.current = null;
    };
  }, [playbackUrl, videoRef, hlsRef, setQualityOptions, setSelectedQuality, setPlaybackError]);
}
