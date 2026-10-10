import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, AlertTriangle, X } from "lucide-react";
import { subscribeToRequestErrors } from '../services/errorFeedback';
import { ToastLayerContext } from './ToastLayerContext';

export type ToastTone = "info" | "warning" | "danger" | "success";
export type Toast = { id: number; message: string; tone?: ToastTone };
export type ToastPush = (toast: string | Omit<Toast, "id">, tone?: ToastTone) => void;

const ToastContext = createContext<ToastPush | null>(null);

export function noticeDuration(message: string): number {
  return Math.min(14000, Math.max(4500, 2500 + message.length * 65));
}

/** Compatibility anchor for forms; all feedback uses one viewport host. */
export function ToastRegion({ label }: { label?: string }) {
  return <div className="action-feedback-region" role={label ? 'region' : undefined} aria-label={label} />;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const itemsRef = useRef<Toast[]>([]);
  const counter = useRef(0);
  const [announcement, setAnnouncement] = useState("");
  const errorRevision = useRef(0);
  const [paused, setPaused] = useState(false);
  const [modalHosts, setModalHosts] = useState<HTMLElement[]>([]);
  const registerModal = useCallback((host: HTMLElement, open: boolean) => {
    setModalHosts(current => open ? [...current.filter(node => node !== host), host] : current.filter(node => node !== host));
  }, []);
  const dismiss = useCallback((id: number) => {
    itemsRef.current = itemsRef.current.filter(item => item.id !== id);
    setItems(itemsRef.current);
    if (!itemsRef.current.length) setAnnouncement("");
  }, []);

  const push = useCallback<ToastPush>((toast, tone) => {
    const item: Omit<Toast, "id"> =
      typeof toast === "string" ? { message: toast, tone: tone ?? "success" } : toast;
    if (item.tone === 'danger' || item.tone === 'warning') errorRevision.current++;
    if (!item.message.trim() || itemsRef.current.some(old => old.message === item.message && old.tone === (item.tone ?? "success"))) return;
    const next = { ...item, tone: item.tone ?? "success", id: ++counter.current };
    itemsRef.current = [...itemsRef.current, next];
    setItems(itemsRef.current);
    setAnnouncement(item.message);
  }, []);

  useEffect(() => {
    const receive = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (typeof detail?.message !== 'string') return;
      const tone: ToastTone = ['info', 'warning', 'danger', 'success'].includes(detail.tone) ? detail.tone : 'info';
      push(detail.message, tone);
    };
    window.addEventListener('lms_toast_notification', receive);
    return () => window.removeEventListener('lms_toast_notification', receive);
  }, [push]);

  useEffect(() => {
    const timers = new Set<number>();
    const clearAccountFeedback = () => {
      timers.forEach(timer => window.clearTimeout(timer));
      timers.clear();
      errorRevision.current++;
      itemsRef.current = [];
      setItems([]);
      setAnnouncement("");
      setPaused(false);
    };
    window.addEventListener('lms_auth_scope_updated', clearAccountFeedback);
    const unsubscribe = subscribeToRequestErrors(message => {
      const revision = errorRevision.current;
      // Give the form a chance to supply a more specific recovery message.
      const timer = window.setTimeout(() => {
        timers.delete(timer);
        if (revision === errorRevision.current) {
          push(message, 'danger');
          // Another simultaneous request failure must still be shown.
          errorRevision.current = revision;
        }
      }, 100);
      timers.add(timer);
    });
    return () => {
      unsubscribe();
      timers.forEach(timer => window.clearTimeout(timer));
      window.removeEventListener('lms_auth_scope_updated', clearAccountFeedback);
    };
  }, [push]);

  // Persistent warnings/errors; only one transient notice at a time.
  const transient = items.find(item => item.tone === "info" || item.tone === "success");
  useEffect(() => {
    if (!transient || paused) return;
    const timer = window.setTimeout(() => dismiss(transient.id), noticeDuration(transient.message));
    return () => window.clearTimeout(timer);
  }, [transient, paused, dismiss]);
  const visible = items.filter(item => item.tone === "danger" || item.tone === "warning" || item.id === transient?.id);

  return (
    <ToastContext.Provider value={push}>
      <ToastLayerContext.Provider value={registerModal}>
      {children}
      {createPortal(<>
        <span className="sr-only" role={announcement ? "status" : undefined} aria-live="polite" aria-atomic="true">{announcement}</span>
        {notices()}
      </>, modalHosts.at(-1) ?? document.body)}
      </ToastLayerContext.Provider>
    </ToastContext.Provider>
  );

  function notices() {
    return <div className="toast-stack" onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}>
        {visible.map((item) => (
          <div key={item.id} className={`toast-item toast-${item.tone ?? "success"}`}>
            {item.tone !== "danger" && <span className="toast-icon" aria-hidden="true">
              {item.tone === "warning" ? (
                <AlertTriangle size={20} />
              ) : (
                <CheckCircle2 size={20} />
              )}
            </span>}
            <span className="toast-text">{item.message}</span>
            <button type="button" className="toast-dismiss" aria-label="إغلاق الرسالة" onClick={() => dismiss(item.id)}><X size={20} /></button>
          </div>
        ))}
      </div>;
  }
}

export const useToast = (): ToastPush => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
};
