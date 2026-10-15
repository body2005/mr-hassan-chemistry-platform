import { useCallback, useEffect, useRef, type RefObject } from 'react';
// The full build includes EME; the light build cannot play licensed content.
import Hls from 'hls.js';
import hlsWorkerUrl from 'hls.js/dist/hls.worker.js?url';
import { playbackFailureMessage } from '../services/playbackFailure';
import type { VideoDrmDescriptor } from '../services/videoDrm';

export const AUTO_QUALITY = 'تلقائي';

/** Own one media transport; token admission/renewal remains separate. */
export function useHlsTransport(
  playbackUrl: string,
  videoRef: RefObject<HTMLVideoElement | null>,
  hlsRef: RefObject<Hls | null>,
  setQualityOptions: (options: string[]) => void,
  setSelectedQuality: (quality: string) => void,
  setPlaybackError: (error: string | null) => void,
  authorizeRequest?: (url: string) => Promise<string>,
  drm?: VideoDrmDescriptor,
) {
  const preference = useRef(AUTO_QUALITY);
  const selectQuality = useCallback((quality: string) => {
    const hls = hlsRef.current;
    if (!hls) return;
    const level = quality === AUTO_QUALITY ? -1 : hls.levels.findIndex(item => item.height <= 1080 && `${item.height}p` === quality);
    if (quality !== AUTO_QUALITY && level < 0) return;
    // Preserve the playing fragment instead of flushing the entire buffer.
    // hls.js schedules the earliest safe switch using its buffer/fetch estimate;
    // -1 restores bandwidth ABR. Re-selecting the same mode needs no switch.
    if (hls.manualLevel !== level) hls.nextLevel = level;
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
      if (drm) { setPlaybackError('الفيديو المحمي يتطلب مشغّل DRM متوافقًا.'); return; }
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
      // Native HLS without a FairPlay CDM handshake is not a DRM fallback.
      if (drm) { setPlaybackError('هذا المتصفح لا يدعم تشغيل الفيديو المحمي؛ استخدم متصفحًا حديثًا يدعم DRM.'); return; }
      if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = playbackUrl;
        setQualityOptions([AUTO_QUALITY]);
        setSelectedQuality(AUTO_QUALITY);
        return releaseSource;
      } else setPlaybackError('المتصفح لا يدعم البث التكيفي؛ جرّب متصفحًا حديثًا.');
      return;
    }
    let disposed = false;
    const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
    const constrained = typeof memory !== 'number' || memory <= 4;
    const byteBudget = (constrained ? 24 : 64) * 1024 * 1024;
    const maximumAhead = constrained ? 90 : 120;
    const retainedBehind = constrained ? 10 : 20;
    let desiredAhead = 60;
    let blocked = false;
    const hls = new Hls({
      emeEnabled: Boolean(drm),
      drmSystems: drm ? {
        'com.widevine.alpha': { licenseUrl: drm.widevine_license_url },
        'com.apple.fps': { licenseUrl: drm.fairplay_license_url, serverCertificateUrl: drm.fairplay_certificate_url },
      } : {},
      drmSystemOptions: drm ? { videoEncryptionScheme: 'cbcs', audioEncryptionScheme: 'cbcs' } : undefined,
      licenseXhrSetup: drm ? async (xhr, url) => {
        if (!authorizeRequest) throw new Error('DRM authorization unavailable');
        const endpoint = await authorizeRequest(url);
        if (disposed) throw new Error('Playback ended');
        xhr.open('POST', endpoint, true);
        xhr.withCredentials = true;
        xhr.setRequestHeader('Content-Type', 'application/octet-stream');
        const cookie = document.cookie.split(';').map(item => item.trim()).find(item => item.startsWith('matgar_csrf='));
        if (!cookie) throw new Error('DRM session unavailable');
        xhr.setRequestHeader('X-CSRF-Token', decodeURIComponent(cookie.slice('matgar_csrf='.length)));
      } : undefined,
      workerPath: hlsWorkerUrl,
      maxBufferLength: 60,
      maxMaxBufferLength: 60,
      maxBufferSize: byteBudget,
      backBufferLength: retainedBehind,
      frontBufferFlushThreshold: maximumAhead,
      startLevel: -1,
      // Keep requests bound to the private, admitted generation while renewing
      // credentials without replacing its MediaSource and downloaded buffer.
      xhrSetup: authorizeRequest ? async (xhr, url) => {
        const admittedUrl = await authorizeRequest(url);
        if (!disposed) xhr.open('GET', admittedUrl, true);
        else throw new Error('Playback ended');
        xhr.withCredentials = true;
      } : undefined,
      // No automatic error/timeout request loops, including HTTP429.
      manifestLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 20000, timeoutRetry: null, errorRetry: null } },
      playlistLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 20000, timeoutRetry: null, errorRetry: null } },
      fragLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 30000, timeoutRetry: null, errorRetry: null } },
      keyLoadPolicy: { default: { maxTimeToFirstByteMs: 10000, maxLoadTimeMs: 20000, timeoutRetry: null, errorRetry: null } },
    });
    hlsRef.current = hls;
    const boundBuffer = () => {
      const level = hls.levels[hls.loadLevel];
      const bitrate = level?.bitrate || Math.max(0, ...hls.levels.filter(item => item.height <= 1080).map(item => item.bitrate));
      // maxBufferSize is a minimum byte target in hls.js, not a hard RAM cap.
      // Bound time too, with headroom for muxing and the retained back buffer.
      const affordableAhead = bitrate > 0 ? byteBudget * 8 / (bitrate * 1.2) - retainedBehind : desiredAhead;
      const ahead = Math.max(12, Math.min(desiredAhead, maximumAhead, affordableAhead));
      hls.config.maxBufferLength = ahead;
      hls.config.maxMaxBufferLength = ahead;
      hls.config.frontBufferFlushThreshold = ahead;
    };
    hls.on(Hls.Events.FRAG_BUFFERED, (_event, data) => {
      if (disposed) return;
      const level = hls.levels[data.frag.level];
      if (!video.paused && level?.bitrate > 0 && hls.bandwidthEstimate > level.bitrate * 1.5) {
        let ahead = 0;
        for (let i = 0; i < video.buffered.length; i++) {
          if (video.buffered.start(i) <= video.currentTime && video.buffered.end(i) >= video.currentTime) {
            ahead = video.buffered.end(i) - video.currentTime;
            break;
          }
        }
        if (ahead >= hls.config.maxBufferLength - 12) desiredAhead = Math.min(maximumAhead, desiredAhead + 15);
      }
      boundBuffer();
    });
    hls.on(Hls.Events.LEVEL_SWITCHING, boundBuffer);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      if (disposed) return;
      const allowed = hls.levels.map((level, index) => level.height <= 1080 ? index : -1).filter(index => index >= 0);
      if (!allowed.length) { hls.stopLoad(); setPlaybackError('الفيديو يحتاج تجهيز نسخة لا تتجاوز 1080p.'); return; }
      hls.autoLevelCapping = Math.max(...allowed);
      boundBuffer();
      const options = [AUTO_QUALITY, ...Array.from(new Set(hls.levels
        .filter(level => level.height > 0 && level.height <= 1080).map(level => `${level.height}p`)))];
      setQualityOptions(options);
      selectQuality(options.includes(preference.current) ? preference.current : AUTO_QUALITY);
    });
    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (disposed) return;
      if (data.fatal || [401, 403, 429].includes(data.response?.code || 0)) {
        blocked = true;
        hls.stopLoad();
        setPlaybackError(playbackFailureMessage({ status: data.response?.code }));
      }
    });
    const prioritizeSeek = () => {
      if (disposed || blocked || !Number.isFinite(video.currentTime)) return;
      for (let i = 0; i < video.buffered.length; i++) {
        if (video.buffered.start(i) <= video.currentTime && video.currentTime < video.buffered.end(i)) return;
      }
      // Cancel even a nearly downloaded distant fragment. Start loading around
      // the new playhead without changing time, speed, volume or ABR preference.
      hls.stopLoad();
      hls.startLoad(video.currentTime, true);
    };
    video.addEventListener('seeking', prioritizeSeek);
    hls.attachMedia(video);
    hls.loadSource(playbackUrl);
    return () => {
      disposed = true;
      video.removeEventListener('seeking', prioritizeSeek);
      hls.destroy();
      if (hlsRef.current === hls) hlsRef.current = null;
    };
  }, [playbackUrl, videoRef, hlsRef, setQualityOptions, setSelectedQuality, setPlaybackError, selectQuality, authorizeRequest, drm]);
  return { selectQuality };
}
