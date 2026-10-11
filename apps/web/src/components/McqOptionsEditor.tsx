import { Trash2 } from 'lucide-react';
import type { GeneratedQuestion } from '../types/quiz';
import { MAX_MCQ_OPTIONS } from '../services/mcqOptions';
import { formatChemicalFormula } from '../utils/formulaUtils';
import { FormulaRenderer } from './FormulaRenderer';

interface Props {
  question: GeneratedQuestion;
  editing: boolean;
  onText: (id: number, key: string, text: string) => void;
  onCorrect: (id: number, key: string) => void;
  onAdd: (id: number) => void;
  onRemove: (id: number, key: string) => void;
  onInitialize: () => void;
}

/** Presentation/editing only. Keys, answer validation and publication stay in their own services. */
export function McqOptionsEditor({ question: q, editing, onText, onCorrect, onAdd, onRemove, onInitialize }: Props) {
  const options = q.options || [];
  if (!options.length) return <div style={{ marginBottom: '12px' }}>
    <button type="button" onClick={onInitialize} style={{ padding: '6px 12px', borderRadius: '6px',
      border: '1px dashed #059669', background: '#ecfdf5', color: '#065f46', fontSize: '12px', fontWeight: 700, cursor: 'pointer' }}>
      + إضافة خيارات السؤال (أ، ب، ج، د)
    </button>
  </div>;
  return <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
    {options.map(opt => <div key={opt.key} style={{ padding: '8px 12px', borderRadius: '8px',
      border: opt.is_correct ? '1.5px solid #059669' : '1px solid var(--border-color)',
      background: opt.is_correct ? 'var(--bg-accent, #ecfdf5)' : 'var(--bg-surface-secondary, #ffffff)',
      fontSize: '13px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
        <button type="button" onClick={() => onCorrect(q.id, opt.key)}
          aria-label={`تعيين الخيار ${opt.key} إجابة صحيحة للسؤال ${q.id}`} aria-pressed={opt.is_correct}
          title="اضغط لتعيين هذا الخيار كإجابة صحيحة"
          style={{ width: '22px', height: '22px', borderRadius: '50%',
            border: opt.is_correct ? '2px solid #059669' : '2px solid var(--border-color-strong)',
            background: opt.is_correct ? '#059669' : 'transparent', color: 'white', display: 'flex',
            alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0, fontSize: '11px', fontWeight: 900 }}>
          {opt.is_correct ? '✓' : ''}
        </button>
        <span style={{ fontWeight: 800, color: 'var(--text-main)', minWidth: '22px' }}>({opt.key})</span>
        {editing ? <div style={{ flex: 1, display: 'flex', gap: '6px', alignItems: 'center' }}>
          <input type="text" value={opt.text} aria-label={`نص الخيار ${opt.key} للسؤال ${q.id}`}
            onChange={e => onText(q.id, opt.key, e.target.value)} placeholder="نص الخيار..."
            onPaste={e => {
              e.preventDefault();
              const text = e.clipboardData.getData('text/plain');
              if (!text) return;
              const input = e.currentTarget;
              onText(q.id, opt.key, opt.text.slice(0, input.selectionStart || 0)
                + formatChemicalFormula(text) + opt.text.slice(input.selectionEnd || 0));
            }}
            onBlur={e => {
              const formatted = formatChemicalFormula(e.target.value);
              if (formatted !== e.target.value) onText(q.id, opt.key, formatted);
            }}
            style={{ flex: 1, padding: '4px 8px', border: '1px solid var(--border-color-strong)',
              borderRadius: '6px', fontSize: '13px', background: 'var(--bg-surface)', color: 'var(--text-main)' }} />
        </div> : <span style={{ color: 'var(--text-main)', fontWeight: opt.is_correct ? 700 : 500 }}>
          <FormulaRenderer inline text={opt.text} />
        </span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {opt.is_correct && <span style={{ color: 'var(--text-main)', fontWeight: 800, fontSize: '11px' }}>الإجابة الصحيحة</span>}
        {editing && options.length > 2 && <button type="button" onClick={() => onRemove(q.id, opt.key)}
          aria-label={`حذف الخيار ${opt.key} للسؤال ${q.id}`} title="حذف هذا الخيار"
          style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer', padding: '2px' }}>
          <Trash2 size={12} />
        </button>}
      </div>
    </div>)}
    {editing && options.length < MAX_MCQ_OPTIONS && <button type="button" onClick={() => onAdd(q.id)}
      style={{ alignSelf: 'flex-start', padding: '4px 10px', borderRadius: '6px', border: '1px dashed #059669',
        background: '#ecfdf5', color: '#065f46', fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}>
      + إضافة خيار جديد
    </button>}
  </div>;
}
