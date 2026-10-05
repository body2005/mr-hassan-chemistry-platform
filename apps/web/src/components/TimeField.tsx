import { useId, useState, type CSSProperties } from 'react';
import { clockParts, clockValue } from '../services/clockField';

export function TimeField({ value, onChange, onBlur, label, error = false }: {
  value: string; onChange: (value: string) => void; onBlur: () => void; label: string; error?: boolean;
}) {
  const parts = clockParts(value);
  const [open, setOpen] = useState<'hour' | 'minute' | null>(null);
  const id = useId();
  const field: CSSProperties = { width: '2.7em', minWidth: 0, textAlign: 'center', font: 'inherit',
    border: 0, borderRadius: 6, background: 'var(--bg-surface)', color: 'var(--text-main)', padding: '6px 2px' };
  const update = (key: 'hour' | 'minute', raw: string) => {
    const digits = raw.replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 1632))
      .replace(/[۰-۹]/g, d => String(d.charCodeAt(0) - 1776)).replace(/\D/g, '').slice(0, 2);
    onChange(clockValue({ ...parts, [key]: digits }));
    setOpen(null);
  };
  return <div style={{ position: 'relative', minWidth: 0 }} onKeyDown={e => { if (e.key === 'Escape') setOpen(null); }}
    onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) { setOpen(null); onBlur(); } }}>
    <div role="group" aria-label={label} dir="ltr" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: 48, gap: 4, padding: '2px 6px', boxSizing: 'border-box', borderRadius: 9,
      border: error || parts.invalid ? '1.5px solid #ef4444' : '1px solid var(--border-color-strong)',
      fontSize: 20, fontWeight: 700, background: 'var(--bg-surface)', color: 'var(--text-main)' }}>
      {(['hour', 'minute'] as const).map((key, index) => <span key={key} style={{ display: 'contents' }}>
        {index === 1 && <span aria-hidden="true">:</span>}
        <input aria-label={`${key === 'hour' ? 'ساعة' : 'دقيقة'} ${label}`} inputMode="numeric" maxLength={2}
          placeholder="00" value={parts[key]} style={field} aria-invalid={parts.invalid || error}
          role="combobox" aria-expanded={open === key} aria-controls={`${id}-${key}`} autoComplete="off"
          onFocus={e => { setOpen(key); e.currentTarget.select(); }} onClick={() => setOpen(key)}
          onChange={e => update(key, e.target.value)} onBlur={() => {
            if (parts[key] && !parts.invalid) onChange(clockValue({ ...parts, [key]: parts[key].padStart(2, '0') }));
          }} />
      </span>)}
      <select aria-label={`فترة ${label}`} value={parts.period} style={{ ...field, width: '2.9em', cursor: 'pointer' }}
        onChange={e => onChange(clockValue({ ...parts, period: e.target.value as 'ص' | 'م' }))} onFocus={() => setOpen(null)}>
        <option value="ص">ص</option><option value="م">م</option>
      </select>
    </div>
    {parts.invalid && <div role="alert" style={{ color: '#ef4444', fontSize: 13 }}>وقت غير صالح: {value} — اختر ساعة من 01 إلى 12 ودقيقة من 00 إلى 59.</div>}
    {open && <div id={`${id}-${open}`} role="listbox" aria-label={`اختيارات ${open === 'hour' ? 'الساعة' : 'الدقيقة'} ${label}`}
      dir="ltr" style={{ marginTop: 4, maxHeight: 210,
        overflowY: 'auto', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 4, padding: 8, borderRadius: 9,
        border: '1px solid var(--border-color-strong)', background: 'var(--bg-surface)', boxShadow: '0 8px 24px #0004' }}>
      {Array.from({ length: open === 'hour' ? 12 : 60 }, (_, i) => String(open === 'hour' ? i + 1 : i).padStart(2, '0')).map(option =>
        <button key={option} type="button" role="option" aria-selected={parts[open].padStart(2, '0') === option}
          style={{ ...field, width: '100%', fontSize: 17, cursor: 'pointer', border: '1px solid var(--border-color-strong)' }}
          onClick={() => { onChange(clockValue({ ...parts, [open]: option })); setOpen(null); }}>{option}</button>)}
    </div>}
  </div>;
}
