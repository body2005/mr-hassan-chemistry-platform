import { apiRequest } from "./lmsService";

type VideoEventType =
  | "play"
  | "pause"
  | "seek"
  | "resume"
  | "ended"
  | "visibilitychange"
  | "pagehide";

type BufferedVideoEvent = {
  client_event_id: string;
  lesson_id: string;
  event_type: VideoEventType;
  position_seconds: number;
  watched_delta_seconds: number;
  duration_seconds: number | null;
  occurred_at: string;
};

function eventId(): string {
  return typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export class VideoTelemetryTracker {
  private readonly lessonId: string;
  private readonly events: BufferedVideoEvent[] = [];
  private readonly listeners: Array<() => void> = [];
  private flushTimer: number | null = null;
  private pendingWatchedSeconds = 0;
  private lastObservedTime: number | null = null;
  private playing = false;

  constructor(lessonId: string) {
    this.lessonId = lessonId;
  }

  attach(video: HTMLVideoElement): () => void {
    const bind = (eventName: string, handler: EventListener) => {
      video.addEventListener(eventName, handler);
      this.listeners.push(() => video.removeEventListener(eventName, handler));
    };

    bind("play", () => {
      this.playing = true;
      this.lastObservedTime = video.currentTime;
      this.record("play", video);
    });
    bind("pause", () => {
      this.playing = false;
      this.record("pause", video);
    });
    bind("seeked", () => this.record("seek", video));
    bind("ended", () => {
      this.playing = false;
      this.record("ended", video);
    });
    bind("timeupdate", () => {
      if (!this.playing || this.lastObservedTime === null) {
        this.lastObservedTime = video.currentTime;
        return;
      }
      const delta = video.currentTime - this.lastObservedTime;
      if (delta > 0 && delta < 10) this.pendingWatchedSeconds += delta;
      this.lastObservedTime = video.currentTime;
    });

    const handleVisibility = () => this.record("visibilitychange", video);
    const handlePageHide = () => {
      this.record("pagehide", video);
      void this.flush();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("pagehide", handlePageHide);
    this.listeners.push(() => document.removeEventListener("visibilitychange", handleVisibility));
    this.listeners.push(() => window.removeEventListener("pagehide", handlePageHide));

    this.flushTimer = window.setInterval(() => void this.flush(), 10000);
    return () => this.detach();
  }

  record(type: VideoEventType, video: HTMLVideoElement): void {
    this.events.push({
      client_event_id: eventId(),
      lesson_id: this.lessonId,
      event_type: type,
      position_seconds: Math.max(0, video.currentTime || 0),
      watched_delta_seconds: Math.max(0, this.pendingWatchedSeconds),
      duration_seconds: Number.isFinite(video.duration) ? video.duration : null,
      occurred_at: new Date().toISOString(),
    });
    this.pendingWatchedSeconds = 0;
    if (this.events.length >= 100) void this.flush();
  }

  async flush(): Promise<void> {
    if (!this.events.length) return;
    const batch = this.events.splice(0, this.events.length);
    try {
      await apiRequest("/telemetry/video-events", {
        method: "POST",
        body: JSON.stringify({ events: batch }),
      });
    } catch {
      // Preserve events for a later retry when the network is offline.
      this.events.unshift(...batch);
    }
  }

  detach(): void {
    this.listeners.splice(0).forEach((remove) => remove());
    if (this.flushTimer !== null) window.clearInterval(this.flushTimer);
    this.flushTimer = null;
    void this.flush();
  }
}
