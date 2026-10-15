import { useEffect, useState, type RefObject } from 'react';
import Hls from 'hls.js/light';

/** MediaSource may contain several islands after a seek; never fill the gaps. */
export function useVideoBufferedRanges(videoRef: RefObject<HTMLVideoElement | null>, hlsRef: RefObject<Hls | null>, source: string) {
  const [ranges, setRanges] = useState<Array<{ start: number; end: number }>>([]);
  useEffect(() => {
    const video = videoRef.current;
    setRanges([]);
    if (!video || !source) return;
    const update = () => {
      const next: Array<{ start: number; end: number }> = [];
      const buffered = video.buffered;
      for (let i = 0; i < buffered.length; i++) {
        const start = buffered.start(i), end = buffered.end(i);
        if (Number.isFinite(start) && Number.isFinite(end) && end > start) next.push({ start, end });
      }
      setRanges(previous => previous.length === next.length && previous.every((range, i) =>
        range.start === next[i].start && range.end === next[i].end) ? previous : next);
    };
    const events = ['progress', 'timeupdate', 'seeking', 'seeked', 'loadedmetadata', 'durationchange', 'emptied'];
    events.forEach(event => video.addEventListener(event, update));
    const hls = hlsRef.current;
    hls?.on(Hls.Events.BUFFER_APPENDED, update);
    hls?.on(Hls.Events.BUFFER_FLUSHED, update);
    update();
    return () => {
      events.forEach(event => video.removeEventListener(event, update));
      hls?.off(Hls.Events.BUFFER_APPENDED, update);
      hls?.off(Hls.Events.BUFFER_FLUSHED, update);
    };
  }, [videoRef, hlsRef, source]);
  return ranges;
}
