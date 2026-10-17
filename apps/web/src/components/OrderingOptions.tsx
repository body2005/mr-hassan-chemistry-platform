import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from 'react';
import { createPortal } from 'react-dom';
import { ArrowDown, ArrowUp, GripVertical, Trash2 } from 'lucide-react';
import type { CourseOption } from '../types/quiz';
import { MAX_ORDERING_ITEMS, moveOrderingItem, newOrderingItem } from '../services/orderingQuestion';
import { useTranslation } from '../utils/i18n';
import { FormulaRenderer } from './FormulaRenderer';
import './OrderingOptions.css';

type Drag = { key: string; pointerId: number; x: number; y: number; rect: DOMRect; item: CourseOption; number: number; moved: boolean };
const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

export function OrderingOptions({ items, editable = false, teacher = false, disabled = false, onChange, onConfirm }: {
  items: CourseOption[]; editable?: boolean; teacher?: boolean; disabled?: boolean;
  onChange: (items: CourseOption[]) => void; onConfirm?: () => void;
}) {
  const { t } = useTranslation();
  const list = useRef<HTMLOListElement>(null);
  const dragging = useRef<Drag | null>(null);
  const ghost = useRef<HTMLDivElement>(null);
  const rows = useRef(new Map<string, HTMLLIElement>());
  const before = useRef<Map<string, DOMRect> | null>(null);
  const animations = useRef(new Map<string, Animation>());
  const dropAnimation = useRef<Animation | null>(null);
  const dropFrame = useRef<number | null>(null);
  const previewOrder = useRef<string[] | null>(null);
  const [lifted, setLifted] = useState<Drag | null>(null);
  const [preview, setPreview] = useState<string[] | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const visible = preview ? preview.map(key => items.find(item => item.key === key)).filter((item): item is CourseOption => !!item) : items;
  const snapshot = () => { before.current = new Map([...rows.current].map(([key, row]) => [key, row.getBoundingClientRect()])); };

  useLayoutEffect(() => {
    const positions = before.current;
    before.current = null;
    if (!positions) return;
    for (const [key, row] of rows.current) {
      animations.current.get(key)?.cancel();
      const old = positions.get(key);
      const next = row.getBoundingClientRect();
      if (!old || key === dragging.current?.key || reducedMotion() || !row.animate) continue;
      const dx = old.left - next.left, dy = old.top - next.top;
      if (dx || dy) animations.current.set(key, row.animate([
        { transform: `translate(${dx}px, ${dy}px)` }, { transform: 'translate(0, 0)' },
      ], { duration: 190, easing: 'cubic-bezier(.2,.8,.2,1)' }));
    }
  }, [items, preview]);

  useEffect(() => {
    const active = animations.current;
    return () => {
      active.forEach(animation => animation.cancel());
      if (dropFrame.current !== null) cancelAnimationFrame(dropFrame.current);
      if (dropAnimation.current) { dropAnimation.current.onfinish = null; dropAnimation.current.cancel(); }
    };
  }, []);

  const move = (key: string, to: number) => {
    if (disabled || lifted) return;
    const from = items.findIndex(item => item.key === key);
    const next = moveOrderingItem(items, from, to);
    if (next !== items) {
      snapshot();
      onChange(next);
      setAnnouncement(t('lesson.orderMoved', { number: to + 1 }));
    }
  };
  const startDrag = (event: PointerEvent<HTMLLIElement>, item: CourseOption, index: number) => {
    if (disabled || lifted || dragging.current || event.button !== 0) return;
    const target = event.target as HTMLElement;
    const handle = target.closest('[data-order-handle]');
    if (target.closest('input,textarea,select,button') && !handle) return;
    if (event.pointerType === 'touch' && !handle) return;
    event.preventDefault();
    const drag = { key: item.key, pointerId: event.pointerId, x: event.clientX, y: event.clientY,
      rect: event.currentTarget.getBoundingClientRect(), item, number: index + 1, moved: false };
    dragging.current = drag;
    previewOrder.current = items.map(option => option.key);
    setPreview(previewOrder.current);
    setLifted(drag);
    list.current?.focus({ preventScroll: true });
    list.current?.setPointerCapture(event.pointerId);
  };
  const finishDrag = (commit: boolean) => {
    const drag = dragging.current;
    if (!drag) return;
    dragging.current = null;
    if (list.current?.hasPointerCapture(drag.pointerId)) list.current.releasePointerCapture(drag.pointerId);
    const reset = () => {
      previewOrder.current = null;
      setPreview(null); setLifted(null); dropAnimation.current = null;
      rows.current.get(drag.key)?.querySelector<HTMLButtonElement>('[data-order-handle]')?.focus({ preventScroll: true });
    };
    if (!commit || disabled) { snapshot(); reset(); return; }
    const ordered = (previewOrder.current ?? items.map(item => item.key)).map(key => items.find(item => item.key === key)!).filter(Boolean);
    if (drag.moved) {
      onChange(ordered);
      setAnnouncement(t('lesson.orderMoved', { number: ordered.findIndex(item => item.key === drag.key) + 1 }));
    }
    if (ghost.current?.animate && !reducedMotion()) {
      // Wait for the final preview layout, including a move and release in one frame.
      dropFrame.current = requestAnimationFrame(() => {
        dropFrame.current = null;
        const destination = rows.current.get(drag.key)?.getBoundingClientRect();
        if (!destination || !ghost.current) { reset(); return; }
        const animation = ghost.current.animate([
          { transform: ghost.current.style.transform },
          { transform: `translate3d(${destination.left - drag.rect.left}px, ${destination.top - drag.rect.top}px, 0) scale(1) rotate(0deg)` },
        ], { duration: 160, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' });
        dropAnimation.current = animation;
        animation.onfinish = reset;
      });
    } else reset();
  };
  const control = { minWidth: 44, minHeight: 44, padding: 8, borderRadius: 8,
    border: '1px solid var(--border-color-strong)', background: 'var(--bg-surface)', color: 'var(--text-main)', cursor: 'pointer' };
  return <div>
    <p>{t(editable || teacher ? 'lesson.orderTeacherHint' : 'lesson.orderStudentHint')}</p>
    <ol ref={list} tabIndex={-1} aria-label={t('lesson.orderItems')} className={`ordering-list${lifted ? ' ordering-list--dragging' : ''}`}
      onKeyDown={event => { if (event.key === 'Escape' && dragging.current) { event.preventDefault(); finishDrag(false); } }}
      onPointerMove={event => {
        const drag = dragging.current;
        if (!drag || event.pointerId !== drag.pointerId) return;
        const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
        if (ghost.current) ghost.current.style.transform = `translate3d(${dx}px, ${dy}px, 0) scale(1.025) rotate(-1deg)`;
        const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-order-key]');
        if (target && list.current?.contains(target)) {
          const current = (previewOrder.current ?? items.map(item => item.key)).map(key => items.find(item => item.key === key)!);
          const to = current.findIndex(candidate => candidate.key === target.dataset.orderKey);
          const from = current.findIndex(candidate => candidate.key === drag.key);
          const rect = target.getBoundingClientRect();
          const center = drag.rect.top + dy + drag.rect.height / 2;
          if ((to > from && center >= rect.top + rect.height / 2) || (to < from && center <= rect.top + rect.height / 2)) {
            snapshot(); previewOrder.current = moveOrderingItem(current, from, to).map(item => item.key); setPreview(previewOrder.current);
          }
        }
      }}
      onPointerUp={event => {
        if (event.pointerId !== dragging.current?.pointerId) return;
        const target = document.elementFromPoint(event.clientX, event.clientY);
        finishDrag(!!target && !!list.current?.contains(target));
      }}
      onPointerCancel={event => { if (event.pointerId === dragging.current?.pointerId) finishDrag(false); }}
      onLostPointerCapture={event => { if (event.target === event.currentTarget && event.pointerId === dragging.current?.pointerId) finishDrag(false); }}
      style={{ padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
      {visible.map((item, index) => <li key={item.key} data-order-key={item.key}
        ref={row => { if (row) rows.current.set(item.key, row); else rows.current.delete(item.key); }}
        className={`ordering-item${lifted?.key === item.key ? ' ordering-item--placeholder' : ''}`}
        data-drop-label={t('lesson.orderDropHere')} aria-hidden={lifted?.key === item.key || undefined}
        onPointerDown={event => startDrag(event, item, index)}
        style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, padding: 8, borderRadius: 9, border: '1px solid var(--border-color)', background: 'var(--bg-surface-secondary)' }}>
        <button type="button" data-order-handle disabled={disabled} aria-label={t('lesson.orderDrag', { number: index + 1 })}
          style={{ ...control, touchAction: 'none', cursor: 'grab' }}
          onKeyDown={event => {
            if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
              event.preventDefault(); move(item.key, index + (event.key === 'ArrowUp' ? -1 : 1));
            }
          }}><GripVertical size={18} /></button>
        <span aria-hidden="true">{index + 1}.</span>
        {editable ? <input aria-label={t('lesson.orderItemText', { number: index + 1 })} value={item.text}
          maxLength={1000} disabled={disabled || !!lifted} placeholder={t('lesson.orderItemPlaceholder')}
          onChange={event => onChange(items.map(candidate => candidate.key === item.key ? { ...candidate, text: event.target.value } : candidate))}
          style={{ flex: '1 1 120px', minWidth: 0, padding: 10, borderRadius: 6, border: '1px solid var(--border-color-strong)', background: 'var(--bg-surface)', color: 'var(--text-main)', font: 'inherit' }} />
          : <div style={{ flex: '1 1 120px', minWidth: 0, overflowWrap: 'anywhere' }}><FormulaRenderer text={item.text} /></div>}
        <div style={{ display: 'flex', gap: 4 }}>
          <button type="button" style={control} disabled={disabled || !!lifted || index === 0} aria-label={t('lesson.orderUp', { number: index + 1 })} onClick={() => move(item.key, index - 1)}><ArrowUp size={16} /></button>
          <button type="button" style={control} disabled={disabled || !!lifted || index === items.length - 1} aria-label={t('lesson.orderDown', { number: index + 1 })} onClick={() => move(item.key, index + 1)}><ArrowDown size={16} /></button>
          {editable && <button type="button" style={control} disabled={disabled || !!lifted || items.length <= 2} aria-label={t('lesson.orderRemove', { number: index + 1 })}
            onClick={() => onChange(items.filter(candidate => candidate.key !== item.key))}><Trash2 size={16} /></button>}
        </div>
      </li>)}
    </ol>
    {editable && <button type="button" className="btn-secondary" disabled={disabled || !!lifted || items.length >= MAX_ORDERING_ITEMS}
      onClick={() => onChange([...items, newOrderingItem()])}>{t('lesson.orderAdd')}</button>}
    {onConfirm && <button type="button" className="btn-secondary" disabled={disabled || !!lifted} onClick={onConfirm}>{t('lesson.orderConfirm')}</button>}
    <span role="status" className="sr-only">{announcement}</span>
    {lifted && createPortal(<div ref={ghost} className="ordering-drag-ghost" aria-hidden="true" dir="auto"
      style={{ left: lifted.rect.left, top: lifted.rect.top, width: lifted.rect.width, minHeight: lifted.rect.height,
        transform: 'translate3d(0, 0, 0) scale(1.025) rotate(-1deg)' }}>
      <GripVertical size={20} /><span>{lifted.number}.</span><div><FormulaRenderer text={lifted.item.text || t('lesson.orderItemPlaceholder')} /></div>
    </div>, document.body)}
  </div>;
}
