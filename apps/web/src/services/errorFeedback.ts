type Listener = (message: string) => void;
const listeners = new Set<Listener>();

export function subscribeToRequestErrors(listener: Listener) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** Final foreground failures only; cancellations and identity probes stay quiet. */
export function reportRequestError(error: unknown) {
  if (!(error instanceof Error)) return;
  const code = (error as Error & { code?: string }).code;
  if (code === 'REQUEST_CANCELLED' || code === 'ABORTED' || error.name === 'AbortError') return;
  const message = code === 'NETWORK_ERROR' ? 'تعذر الاتصال بالخادم. تحقق من اتصالك ثم أعد المحاولة.'
    : code === 'REQUEST_TIMEOUT' ? 'استغرق الطلب وقتًا طويلًا. أعد المحاولة.' : error.message;
  listeners.forEach(listener => listener(message));
}
