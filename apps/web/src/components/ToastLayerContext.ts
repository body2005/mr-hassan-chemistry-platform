import { createContext } from 'react';

// Native modal dialogs live above ordinary z-index layers and make the rest
// of the document inert. Keep the single viewport host in the active modal.
export const ToastLayerContext = createContext<((host: HTMLElement, open: boolean) => void) | null>(null);
