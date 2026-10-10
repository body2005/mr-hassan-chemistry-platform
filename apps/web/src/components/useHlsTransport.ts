import { useCallback, useEffect, useRef, type RefObject } from 'react';
import Hls from 'hls.js';
import { playbackFailureMessage } from '../services/playbackFailure';

export const AUTO_QUALITY = 'تلقائي';

/** Own one media transport; token admission/renewal remains separate. */
export function useHlsTransport(
  playbackUrl: string,
  videoRef: RefObject<HTMLVideoElement | null>,
  hlsRef: RefObject<Hls | null>,
  setQualityOptions: (options: string[]) => void,
  setSelectedQuality: (quality: string) => void,
  setPlaybackError: (error: string | null) => void,
) {
  const preference = useRef(AUTO_QUALITY);
  const selectQuality = useCallback((quality: string) => {
    const hls = hlsRef.current;
    if (!hls) return;
    const level = quality === AUTO_QUALITY ? -1 : hls.levels.findIndex(item => item.height <= 1080 && `${item.height}p` === quality);
    if (quality !== AUTO_QUALITY && level < 0) return;
    // currentLevel flushes buffered fragments so a manual choice changes the
    // actual media immediately. -1 returns control to hls.js bandwidth ABR.
    hls.currentLevel = level;
    preference.current = quality;
    setSelectedQuality(quality);
  }, [hlsRef, setSelectedQuality]);
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const releaseSource = () => {
      video.removeAttribute('src');
      // Reset the media resource, aborting its outstanding Range request.
      video.load();
    };
    if (!playbackUrl) {
      // Do not retain the previous lesson's source while admission is pending.
      video.removeAttribute('src');
      setQualityOptions([]);
      return;
    }
    if (!playbackUrl.includes('/hls/')) {
      video.src = playbackUrl;
      const showResolution = () => {
        const quality = video.videoHeight > 0 ? `${video.videoHeight}p` : '';
        setQualityOptions(quality ? [quality] : []);
        setSelectedQuality(quality);
      };
      showResolution();
      video.addEventListener('loadedmetadata', showResolution);
      return () => { video.removeEventListener('loadedmetadata', showResolution); releaseSource(); };
    }
    if (!Hls.isSupported()) {
      if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = playbackUrl;
        setQualityOptions([AUTO_QUALITY]);
        setSelectedQuality(AUTO_QUALITY);
        return releaseSource;
      } else setPlaybackError('المتصفح لا يدعم البث التكيفي؛ جرّب متصفحًا حديثًا.');
      return;
    }
    let disposed = false;
    const hls = new Hls({
      maxBufferLength: 30,
      maxMaxBufferLength: 60,
      startLevel: -1,
      // No automatic error/timeout request loops, including HTTP429.
      manifestLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 20000, timeoutRetry: null, errorRetry: null } },
      playlistLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 20000, timeoutRetry: null, errorRetry: null } },
      fragLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 30000, timeoutRetry: null, errorRetry: null } },
    });
    hlsRef.current = hls;
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      if (disposed) return;
      const allowed = hls.levels.map((level, index) => level.height <= 1080 ? index : -1).filter(index => index >= 0);
      if (!allowed.length) { hls.stopLoad(); setPlaybackError('الفيديو يحتاج تجهيز نسخة لا تتجاوز 1080p.'); return; }
      hls.autoLevelCapping = Math.max(...allowed);
      const options = [AUTO_QUALITY, ...Array.from(new Set(hls.levels
        .filter(level => level.height > 0 && level.height <= 1080).map(level => `${level.height}p`)))];
      setQualityOptions(options);
      selectQuality(options.includes(preference.current) ? preference.current : AUTO_QUALITY);
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
  }, [playbackUrl, videoRef, hlsRef, setQualityOptions, setSelectedQuality, setPlaybackError, selectQuality]);
  return { selectQuality };
}
