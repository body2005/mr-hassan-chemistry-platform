import { useTranslation } from '../utils/i18n';

/** The value comes from the student's saved progress, never a timer. */
export function LessonWatchProgress({ percent, unavailable = false }: { percent?: number; unavailable?: boolean }) {
  const { t } = useTranslation();
  const value = typeof percent === 'number' && Number.isFinite(percent) ? Math.min(100, Math.max(0, Math.round(percent))) : undefined;
  return <div className="lesson-card-watch-progress">
    <div><span>{t('lesson.watchedLabel')}</span>
      <strong>{unavailable ? t('lesson.watchedUnavailable') : value === undefined ? t('lesson.watchedLoading') : `${value}%`}</strong></div>
    {value !== undefined && !unavailable && <div role="progressbar" aria-label={t('lesson.watchedLabel')}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} className="lesson-card-watch-track">
      <span style={{ width: `${value}%` }} />
    </div>}
  </div>;
}
