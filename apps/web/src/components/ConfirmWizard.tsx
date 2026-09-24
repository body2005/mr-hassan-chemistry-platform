import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type WizardTone = "danger" | "warning" | "info" | "success";

interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: WizardTone;
  steps?: string[];
}

interface ConfirmState extends ConfirmOptions {
  resolve: (value: boolean) => void;
}

type PushFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<PushFn | null>(null);

function Dialog({ state }: { state: ConfirmState }) {
  const confirm = useCallback(() => state.resolve(true), [state]);
  const dismiss = useCallback(() => state.resolve(false), [state]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") dismiss();
      if (event.key === "Enter") confirm();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirm, dismiss]);

  return (
    <div
      className="confirm-wizard-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={state.title}
      onClick={dismiss}
    >
      <div className="confirm-wizard-card" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-wizard-header">
          <h2 className="confirm-wizard-title">{state.title}</h2>
        </div>

        <div className="confirm-wizard-body">
          <p className="confirm-wizard-message">{state.message}</p>

          {state.steps && state.steps.length > 0 && (
            <ul className="confirm-wizard-steps">
              {state.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          )}

          <div className="confirm-wizard-actions">
            <button
              className={`confirm-wizard-btn primary ${state.tone === "danger" ? "tone-danger" : ""}`}
              onClick={confirm}
              autoFocus
            >
              {state.confirmLabel ?? "تأكيد"}
            </button>
            {state.cancelLabel !== null && (
              <button className="confirm-wizard-btn ghost" onClick={dismiss}>
                {state.cancelLabel ?? "إلغاء"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ConfirmWizardProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ConfirmState | null>(null);
  const counter = useRef(0);

  const push = useMemo<PushFn>(() => {
    return (options: ConfirmOptions) =>
      new Promise<boolean>((resolve) => {
        counter.current += 1;
        setActive({
          ...options,
          resolve: (value: boolean) => {
            setActive(null);
            resolve(value);
          },
        });
      });
  }, []);

  return (
    <ConfirmContext.Provider value={push}>
      {children}
      {active && <Dialog key={counter.current} state={active} />}
    </ConfirmContext.Provider>
  );
}

export const useConfirm = (): PushFn => {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used inside ConfirmWizardProvider");
  return ctx;
};
