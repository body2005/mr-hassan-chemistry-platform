import { useTranslation } from '../utils/i18n';

/** Presentation of server-provided dates only; never grants access to content. */
export function ScheduleBadges({ startsAt, endsAt }: { startsAt?: string | null; endsAt?: string | null }) {
  const { t, lang } = useTranslation();
  const start = startsAt ? Date.parse(startsAt) : NaN;
  const end = endsAt ? Date.parse(endsAt) : NaN;
  const format = (value: number) => new Date(value).toLocaleString(lang === 'ar' ? 'ar-EG' : 'en-GB', { timeZone: 'Africa/Cairo', dateStyle: 'medium', timeStyle: 'short' });
  if (!Number.isFinite(start) && !Number.isFinite(end)) return null;
  const minutes = Math.ceil((end - start) / 60000);
  return <div className="schedule-badges">
    {Number.isFinite(start) && <div><span>{t('lesson.scheduledPublish')}</span><time dateTime={new Date(start).toISOString()}>{format(start)}</time></div>}
    {Number.isFinite(end) && <div><span>{t('lesson.scheduledEnd')}</span><time dateTime={new Date(end).toISOString()}>{format(end)}</time>
      {Number.isFinite(minutes) && minutes > 0 && <small>{t('lesson.scheduledWindow')}: {new Intl.NumberFormat(lang).format(Math.floor(minutes / 60))}{lang === 'ar' ? ' س' : ' h'} {minutes % 60 ? `${new Intl.NumberFormat(lang).format(minutes % 60)} ${lang === 'ar' ? 'د' : 'min'}` : ''}</small>}
    </div>}
  </div>;
}
