import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from "react";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

export type ToastTone = "info" | "warning" | "danger" | "success";
export type Toast = { id: number; message: string; tone?: ToastTone };
export type ToastPush = (toast: string | Omit<Toast, "id">, tone?: ToastTone) => void;

const ToastContext = createContext<ToastPush | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const counter = useRef(0);

  const push = useCallback<ToastPush>((toast, tone) => {
    const id = ++counter.current;
    const item: Omit<Toast, "id"> =
      typeof toast === "string" ? { message: toast, tone: tone ?? "success" } : toast;
    setItems((prev) => [...prev, { ...item, id }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 2000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-stack">
        {items.map((item) => (
          <div key={item.id} className={`toast-item toast-${item.tone ?? "success"}`}>
            <span className="toast-icon">
              {item.tone === "danger" ? (
                <XCircle size={18} color="#ef4444" />
              ) : item.tone === "warning" ? (
                <AlertTriangle size={18} color="#f59e0b" />
              ) : (
                <CheckCircle2 size={18} color="#10b981" />
              )}
            </span>
            <span className="toast-text">{item.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = (): ToastPush => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
};
