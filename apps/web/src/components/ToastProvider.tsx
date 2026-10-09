import { createContext, useContext, useState, useCallback, useRef, useEffect, useId, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, AlertTriangle, XCircle, X } from "lucide-react";

export type ToastTone = "info" | "warning" | "danger" | "success";
export type Toast = { id: number; message: string; tone?: ToastTone };
export type ToastPush = (toast: string | Omit<Toast, "id">, tone?: ToastTone) => void;
type OwnedToast = Toast & { regionId?: string };

const ToastContext = createContext<ToastPush | null>(null);
const RegionContext = createContext<((id: string, node: HTMLElement | null) => void) | null>(null);

export function noticeDuration(message: string): number {
  return Math.min(14000, Math.max(4500, 2500 + message.length * 65));
}

/** Keep feedback in document flow beside the action, never over its controls. */
export function ToastRegion({ label }: { label?: string }) {
  const register = useContext(RegionContext);
  const id = useId();
  const attach = useCallback((node: HTMLDivElement | null) => register?.(id, node), [id, register]);
  return <div ref={attach} className="action-feedback-region" role={label ? 'region' : undefined} aria-label={label} />;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<OwnedToast[]>([]);
  const itemsRef = useRef<OwnedToast[]>([]);
  const counter = useRef(0);
  const [announcement, setAnnouncement] = useState("");
  const [regions, setRegions] = useState<Map<string, HTMLElement>>(() => new Map());
  const regionsRef = useRef<Map<string, HTMLElement>>(new Map());
  const [paused, setPaused] = useState(false);
  const register = useCallback((id: string, node: HTMLElement | null) => {
    const prev = regionsRef.current;
    if (prev.get(id) === node || (!node && !prev.has(id))) return;
    const next = new Map(prev);
    if (node) next.set(id, node); else next.delete(id);
    regionsRef.current = next;
    setRegions(next);
    if (!node && itemsRef.current.some(item => item.regionId === id)) {
      itemsRef.current = itemsRef.current.filter(item => item.regionId !== id);
      setItems(itemsRef.current);
      if (!itemsRef.current.length) setAnnouncement("");
    }
  }, []);
  const dismiss = useCallback((id: number) => {
    itemsRef.current = itemsRef.current.filter(item => item.id !== id);
    setItems(itemsRef.current);
    if (!itemsRef.current.length) setAnnouncement("");
  }, []);

  const push = useCallback<ToastPush>((toast, tone) => {
    const item: Omit<Toast, "id"> =
      typeof toast === "string" ? { message: toast, tone: tone ?? "success" } : toast;
    const regionId = [...regionsRef.current.keys()].at(-1);
    if (!item.message.trim() || itemsRef.current.some(old => old.message === item.message && old.tone === (item.tone ?? "success") && old.regionId === regionId)) return;
    const next = { ...item, tone: item.tone ?? "success", id: ++counter.current, regionId };
    itemsRef.current = [...itemsRef.current, next];
    setItems(itemsRef.current);
    setAnnouncement(item.message);
  }, []);

  // Persistent warnings/errors; only one transient notice at a time.
  const transient = items.find(item => item.tone === "info" || item.tone === "success");
  useEffect(() => {
    if (!transient || paused) return;
    const timer = window.setTimeout(() => dismiss(transient.id), noticeDuration(transient.message));
    return () => window.clearTimeout(timer);
  }, [transient, paused, dismiss]);
  const visible = items.filter(item => item.tone === "danger" || item.tone === "warning" || item.id === transient?.id);
  const host = [...regions.values()].at(-1);

  return (
    <ToastContext.Provider value={push}>
      <RegionContext.Provider value={register}>
      <span className="sr-only" role={announcement ? "status" : undefined} aria-live="polite" aria-atomic="true">{announcement}</span>
      {!host && notices()}
      {children}
      {host && createPortal(notices(), host)}
      </RegionContext.Provider>
    </ToastContext.Provider>
  );

  function notices() {
    return <div className="toast-stack" onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}>
        {visible.map((item) => (
          <div key={item.id} className={`toast-item toast-${item.tone ?? "success"}`}>
            <span className="toast-icon" aria-hidden="true">
              {item.tone === "danger" ? (
                <XCircle size={20} />
              ) : item.tone === "warning" ? (
                <AlertTriangle size={20} />
              ) : (
                <CheckCircle2 size={20} />
              )}
            </span>
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
