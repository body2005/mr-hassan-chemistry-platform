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
  return message.length > 120 || message.includes('\n') ? 10_000 : 5_000;
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
  const expiryTimers = useRef(new Map<number, number>());
  const [modalHosts, setModalHosts] = useState<HTMLElement[]>([]);
  const registerModal = useCallback((host: HTMLElement, open: boolean) => {
    setModalHosts(current => open ? [...current.filter(node => node !== host), host] : current.filter(node => node !== host));
  }, []);
  const dismiss = useCallback((id: number) => {
    window.clearTimeout(expiryTimers.current.get(id));
    expiryTimers.current.delete(id);
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
    if (itemsRef.current.length >= 4) dismiss(itemsRef.current[0].id);
    itemsRef.current = [...itemsRef.current, next];
    expiryTimers.current.set(next.id, window.setTimeout(() => dismiss(next.id), noticeDuration(next.message)));
    setItems(itemsRef.current);
    setAnnouncement(item.message);
  }, [dismiss]);

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
      expiryTimers.current.forEach(timer => window.clearTimeout(timer));
      expiryTimers.current.clear();
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
      expiryTimers.current.forEach(timer => window.clearTimeout(timer));
      expiryTimers.current.clear();
      window.removeEventListener('lms_auth_scope_updated', clearAccountFeedback);
    };
  }, [push]);

  const visible = items;

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
    return <div className="toast-stack">
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
