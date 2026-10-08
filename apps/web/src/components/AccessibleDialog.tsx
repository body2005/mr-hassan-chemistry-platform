import { useLayoutEffect, useRef, type CSSProperties, type ReactNode } from 'react';

// Native modal semantics make the background inert, contain keyboard focus
// and restore focus on close. Escape is disabled only during an active write.
export function AccessibleDialog({ children, labelledBy, locked = false, onClose, style, className }: {
  children: ReactNode; labelledBy: string; locked?: boolean; onClose: () => void;
  style?: CSSProperties; className?: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const element = dialog.current!;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element.showModal();
    return () => {
      // Close before React detaches the dialog. A passive-effect cleanup runs
      // after removal, when the browser can no longer restore the opener.
      if (element.open) element.close();
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);
  return <dialog ref={dialog} aria-labelledby={labelledBy} aria-modal="true" className={className}
    onCancel={event => { event.preventDefault(); if (!locked) onClose(); }}
    style={{ margin: 0, border: 0, width: '100vw', height: '100dvh', maxWidth: 'none', maxHeight: 'none', boxSizing: 'border-box', ...style }}>
    {children}
  </dialog>;
}
