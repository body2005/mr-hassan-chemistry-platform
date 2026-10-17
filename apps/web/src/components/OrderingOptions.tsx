import { useRef, useState } from 'react';
import { ArrowDown, ArrowUp, GripVertical, Trash2 } from 'lucide-react';
import type { CourseOption } from '../types/quiz';
import { MAX_ORDERING_ITEMS, moveOrderingItem, newOrderingItem } from '../services/orderingQuestion';
import { useTranslation } from '../utils/i18n';
import { FormulaRenderer } from './FormulaRenderer';

export function OrderingOptions({ items, editable = false, disabled = false, onChange, onConfirm }: {
  items: CourseOption[]; editable?: boolean; disabled?: boolean;
  onChange: (items: CourseOption[]) => void; onConfirm?: () => void;
}) {
  const { t } = useTranslation();
  const list = useRef<HTMLOListElement>(null);
  const dragging = useRef<string | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const move = (key: string, to: number) => {
    const from = items.findIndex(item => item.key === key);
    const next = moveOrderingItem(items, from, to);
    if (next !== items) {
      onChange(next);
      setAnnouncement(t('lesson.orderMoved', { number: to + 1 }));
    }
  };
  const control = { minWidth: 44, minHeight: 44, padding: 8, borderRadius: 8,
    border: '1px solid var(--border-color-strong)', background: 'var(--bg-surface)', color: 'var(--text-main)', cursor: 'pointer' };
  return <div>
    <p>{t(editable ? 'lesson.orderTeacherHint' : 'lesson.orderStudentHint')}</p>
    <ol ref={list} aria-label={t('lesson.orderItems')}
      onPointerMove={event => {
        const key = dragging.current;
        if (!key) return;
        const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-order-key]');
        if (target && list.current?.contains(target)) {
          move(key, items.findIndex(candidate => candidate.key === target.dataset.orderKey));
        }
      }}
      onPointerUp={event => {
        dragging.current = null;
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={() => { dragging.current = null; }} onLostPointerCapture={() => { dragging.current = null; }}
      style={{ padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map((item, index) => <li key={item.key} data-order-key={item.key}
        style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, padding: 8, borderRadius: 9, border: '1px solid var(--border-color)', background: 'var(--bg-surface-secondary)' }}>
        <button type="button" disabled={disabled} aria-label={t('lesson.orderDrag', { number: index + 1 })}
          style={{ ...control, touchAction: 'none', cursor: 'grab' }}
          onPointerDown={event => {
            if (event.button !== 0) return;
            dragging.current = item.key;
            // Keep capture on the stationary list when React moves an item.
            list.current?.setPointerCapture(event.pointerId);
          }}
          onKeyDown={event => {
            if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
              event.preventDefault(); move(item.key, index + (event.key === 'ArrowUp' ? -1 : 1));
            }
          }}><GripVertical size={18} /></button>
        <span aria-hidden="true">{index + 1}.</span>
        {editable ? <input aria-label={t('lesson.orderItemText', { number: index + 1 })} value={item.text}
          maxLength={1000} disabled={disabled} placeholder={t('lesson.orderItemPlaceholder')}
          onChange={event => onChange(items.map(candidate => candidate.key === item.key ? { ...candidate, text: event.target.value } : candidate))}
          style={{ flex: '1 1 120px', minWidth: 0, padding: 10, borderRadius: 6, border: '1px solid var(--border-color-strong)', background: 'var(--bg-surface)', color: 'var(--text-main)', font: 'inherit' }} />
          : <div style={{ flex: '1 1 120px', minWidth: 0, overflowWrap: 'anywhere' }}><FormulaRenderer text={item.text} /></div>}
        <div style={{ display: 'flex', gap: 4 }}>
          <button type="button" style={control} disabled={disabled || index === 0} aria-label={t('lesson.orderUp', { number: index + 1 })} onClick={() => move(item.key, index - 1)}><ArrowUp size={16} /></button>
          <button type="button" style={control} disabled={disabled || index === items.length - 1} aria-label={t('lesson.orderDown', { number: index + 1 })} onClick={() => move(item.key, index + 1)}><ArrowDown size={16} /></button>
          {editable && <button type="button" style={control} disabled={disabled || items.length <= 2} aria-label={t('lesson.orderRemove', { number: index + 1 })}
            onClick={() => onChange(items.filter(candidate => candidate.key !== item.key))}><Trash2 size={16} /></button>}
        </div>
      </li>)}
    </ol>
    {editable && <button type="button" className="btn-secondary" disabled={disabled || items.length >= MAX_ORDERING_ITEMS}
      onClick={() => onChange([...items, newOrderingItem()])}>{t('lesson.orderAdd')}</button>}
    {onConfirm && <button type="button" className="btn-secondary" disabled={disabled} onClick={onConfirm}>{t('lesson.orderConfirm')}</button>}
    <span role="status" className="sr-only">{announcement}</span>
  </div>;
}
