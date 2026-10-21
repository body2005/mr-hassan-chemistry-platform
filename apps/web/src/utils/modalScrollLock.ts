const MODAL_SELECTOR = '.modal-overlay, .confirm-wizard-overlay, .password-wizard-overlay, [role="dialog"], [aria-modal="true"], [data-modal-overlay]';

function visibleModal(element: Element) {
  if (element.closest('[hidden], [aria-hidden="true"]')) return false;
  if (element instanceof HTMLDialogElement && !element.open) return false;
  const style = getComputedStyle(element);
  return style.display !== 'none' && style.visibility !== 'hidden';
}

/** One page-wide lock, including stacked and legacy inline wizard overlays. */
export function installModalScrollLock() {
  const body = document.body, html = document.documentElement;
  let unlock: (() => void) | undefined;
  const update = () => {
    const hasModal = [...document.querySelectorAll(MODAL_SELECTOR)].some(visibleModal);
    if (!hasModal) { unlock?.(); unlock = undefined; return; }
    if (unlock) return;
    const x = window.scrollX, y = window.scrollY;
    const scrollbar = Math.max(0, window.innerWidth - html.clientWidth);
    const properties = ['position', 'top', 'left', 'right', 'width', 'overflow'] as const;
    const previous = properties.map(name => [name, body.style.getPropertyValue(name), body.style.getPropertyPriority(name)]);
    const bodyWasLocked = body.classList.contains('modal-open'), htmlWasLocked = html.classList.contains('modal-open');
    body.classList.add('modal-open'); html.classList.add('modal-open');
    // Fixed positioning also prevents background touch-scrolling on mobile.
    body.style.setProperty('position', 'fixed', 'important');
    body.style.setProperty('top', `${-y}px`, 'important');
    body.style.setProperty('left', `${-x}px`, 'important');
    body.style.setProperty('right', '0', 'important');
    body.style.setProperty('width', scrollbar ? `calc(100% - ${scrollbar}px)` : '100%', 'important');
    body.style.setProperty('overflow', 'hidden', 'important');
    unlock = () => {
      for (const [name, value, priority] of previous) {
        if (value) body.style.setProperty(name, value, priority); else body.style.removeProperty(name);
      }
      if (!bodyWasLocked) body.classList.remove('modal-open');
      if (!htmlWasLocked) html.classList.remove('modal-open');
      const behavior = html.style.getPropertyValue('scroll-behavior'), priority = html.style.getPropertyPriority('scroll-behavior');
      html.style.setProperty('scroll-behavior', 'auto', 'important');
      window.scrollTo(x, y);
      if (behavior) html.style.setProperty('scroll-behavior', behavior, priority); else html.style.removeProperty('scroll-behavior');
    };
  };
  const observer = new MutationObserver(update);
  observer.observe(body, { childList: true, subtree: true, attributes: true,
    attributeFilter: ['class', 'style', 'open', 'hidden', 'aria-hidden'] });
  update();
  return () => { observer.disconnect(); unlock?.(); };
}
