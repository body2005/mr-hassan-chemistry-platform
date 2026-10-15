import { Settings } from 'lucide-react';
import { displaySizes, setDisplaySize, useDisplaySize } from '../services/displaySize';

export function DisplaySettings({ lang }: { lang: 'ar' | 'en' }) {
  const size = useDisplaySize();
  const label = lang === 'ar' ? 'حجم الكلام' : 'Text size';
  return <details className="display-settings">
    <summary className="icon-btn" aria-label={lang === 'ar' ? 'إعدادات العرض' : 'Display settings'} title={lang === 'ar' ? 'إعدادات العرض' : 'Display settings'}><Settings size={18} /></summary>
    <div className="display-settings-panel">
      <label>{label}<select value={size} onChange={event => setDisplaySize(Number(event.target.value))}>
        {displaySizes.map(value => <option key={value} value={value}>{value}%{value === 100 ? (lang === 'ar' ? ' — افتراضي' : ' — Default') : ''}</option>)}
      </select></label>
      <p>{lang === 'ar' ? 'يُطبّق على الموقع كله، مع تكبير العناصر لتناسب الخط.' : 'Applies across the site, scaling controls with the text.'}</p>
    </div>
  </details>;
}
