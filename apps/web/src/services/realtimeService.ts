import { ApiClientError, apiRequest, apiUrl, invalidateApiCache } from "./apiClient";

export interface RealtimeMessage<T = unknown> {
  id?: string;
  type: string;
  data: T;
  timestamp?: string;
}

type EventCallback<T = unknown> = (data: T) => void;

class RealTimeService {
  private eventSource: EventSource | null = null;
  private reconnectTimer: number | null = null;
  private reconnectAttempts = 0;
  private isConnecting = false;
  private listeners = new Map<string, Set<EventCallback>>();
  private active = false;
  private connectionGeneration = 0;

  /**
   * Connect to the SSE endpoint if not already connected.
   */
  connect(): void {
    if (this.eventSource || this.isConnecting) return;
    if (typeof window === "undefined" || !("EventSource" in window)) return;

    this.active = true;
    this.isConnecting = true;
    void this.openStream(++this.connectionGeneration);
  }

  private async openStream(generation: number): Promise<void> {
    try {
      // Cookie-only identity probe shares apiClient's single refresh and CSRF
      // protection. Neither the SPA nor EventSource uses a readable bearer.
      await apiRequest("/auth/me", { cookieOnly: true, skipCache: true, timeoutMs: 8000 });
      if (!this.active || generation !== this.connectionGeneration) return;
      const streamUrl = apiUrl("/realtime/stream");
      const es = new EventSource(streamUrl, { withCredentials: true });
      this.eventSource = es;

      es.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        console.debug("[RealTime] Connected to event stream");
        this.emit("status", { status: "connected" });
        // Redis events are hints, not durable history. Recover notifications
        // missed while offline from the authenticated database-backed route.
        invalidateApiCache("/notifications");
        window.dispatchEvent(new CustomEvent("lms_notifications_updated"));
      };

      // Listen for named SSE events from the backend
      const registeredEvents = [
        "connected",
        "notification_created",
        "lesson_access_requested",
        "lesson_access_approved",
        "lesson_access_rejected",
        "submission_created",
        "submission_graded",
        "payment_created",
        "payment_reviewed",
        "calendar_updated",
      ];

      for (const eventName of registeredEvents) {
        es.addEventListener(eventName, (event: MessageEvent) => {
          this.handleIncomingEvent(eventName, event.data);
        });
      }

      es.onmessage = (event: MessageEvent) => {
        this.handleIncomingEvent("message", event.data);
      };

      es.onerror = (err) => {
        console.debug("[RealTime] SSE stream error or closed, scheduling reconnect", err);
        this.cleanupEventSource();
        this.scheduleReconnect();
      };
    } catch (err) {
      if (generation !== this.connectionGeneration) return;
      if (err instanceof ApiClientError && err.status === 401) {
        this.disconnect();
        this.emit("status", { status: "disconnected", reason: "authentication_required" });
        return;
      }
      console.warn("[RealTime] Failed to instantiate EventSource", err);
      this.cleanupEventSource();
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect and clear any reconnect timers (e.g. on logout).
   */
  disconnect(): void {
    this.active = false;
    this.connectionGeneration += 1;
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.cleanupEventSource();
    this.reconnectAttempts = 0;
  }

  private cleanupEventSource(): void {
    if (this.eventSource) {
      try {
        this.eventSource.close();
      } catch {
        // Ignore close error
      }
      this.eventSource = null;
    }
    this.isConnecting = false;
  }

  private scheduleReconnect(): void {
    if (!this.active) return;
    if (this.reconnectTimer) return;

    this.reconnectAttempts += 1;
    if (this.reconnectAttempts > 8) {
      this.active = false;
      this.emit("status", { status: "disconnected", reason: "retry_limit" });
      return;
    }
    // Bounded exponential backoff with randomized jitter to prevent reconnect storms
    const jitter = Math.random() * 800;
    const delayMs = Math.min(25000, 1000 * Math.pow(1.5, Math.min(this.reconnectAttempts, 8)) + jitter);

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (this.active) {
        this.connect();
      }
    }, delayMs);
  }

  private handleIncomingEvent(eventType: string, rawData: string): void {
    let parsed: unknown = null;
    try {
      parsed = typeof rawData === "string" ? JSON.parse(rawData) : rawData;
    } catch {
      parsed = rawData;
    }

    // Invalidate caches and dispatch custom browser events
    switch (eventType) {
      case "notification_created":
        invalidateApiCache("/notifications");
        window.dispatchEvent(new CustomEvent("lms_notifications_updated", { detail: parsed }));
        break;

      case "lesson_access_requested":
        invalidateApiCache("/lessons/access-requests");
        invalidateApiCache("/notifications");
        window.dispatchEvent(new CustomEvent("lms_lesson_access_requested", { detail: parsed }));
        window.dispatchEvent(new CustomEvent("lms_notifications_updated", { detail: parsed }));
        break;

      case "lesson_access_approved":
        invalidateApiCache("/lessons");
        invalidateApiCache("/courses");
        invalidateApiCache("/payments/me/entitlements");
        window.dispatchEvent(new CustomEvent("lms_lesson_unlocked", { detail: parsed }));
        window.dispatchEvent(new CustomEvent("lms_notifications_updated", { detail: parsed }));
        break;

      case "lesson_access_rejected":
        invalidateApiCache("/lessons/me/access-requests");
        window.dispatchEvent(new CustomEvent("lms_lesson_access_rejected", { detail: parsed }));
        window.dispatchEvent(new CustomEvent("lms_notifications_updated", { detail: parsed }));
        break;

      case "submission_created":
        invalidateApiCache("/submissions");
        invalidateApiCache("/assignments");
        window.dispatchEvent(new CustomEvent("lms_submission_received", { detail: parsed }));
        break;

      case "submission_graded":
        invalidateApiCache("/submissions");
        invalidateApiCache("/assignments");
        window.dispatchEvent(new CustomEvent("lms_submission_graded", { detail: parsed }));
        break;

      case "payment_created":
        invalidateApiCache("/payments/orders");
        window.dispatchEvent(new CustomEvent("lms_payment_updated", { detail: parsed }));
        break;

      case "payment_reviewed":
        invalidateApiCache("/payments/orders");
        invalidateApiCache("/payments/me/orders");
        invalidateApiCache("/payments/me/entitlements");
        window.dispatchEvent(new CustomEvent("lms_payment_updated", { detail: parsed }));
        // Approval already emits lesson_access_approved. A review (including
        // rejection) only refreshes authoritative access, never unlocks it.
        break;

      case "calendar_updated":
        invalidateApiCache("/calendar");
        window.dispatchEvent(new CustomEvent("lms_schedule_updated", { detail: parsed }));
        window.dispatchEvent(new CustomEvent("lms_notifications_updated", { detail: parsed }));
        break;

      default:
        break;
    }

    this.emit(eventType, parsed);
  }

  /**
   * Register a subscriber callback for a specific SSE event.
   */
  on<T = unknown>(eventType: string, callback: EventCallback<T>): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    const bucket = this.listeners.get(eventType)!;
    const listener: EventCallback = (data) => callback(data as T);
    bucket.add(listener);
    return () => {
      bucket.delete(listener);
    };
  }

  private emit(eventType: string, data: unknown): void {
    const bucket = this.listeners.get(eventType);
    if (!bucket) return;
    for (const cb of bucket) {
      try {
        cb(data);
      } catch (err) {
        console.error(`[RealTime] Error in listener for ${eventType}:`, err);
      }
    }
  }

  isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN;
  }
}

export const realtimeService = new RealTimeService();
