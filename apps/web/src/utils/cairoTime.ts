const zone = 'Africa/Cairo';
export function requireUpcomingTime(iso: string | null, existing?: string | null): void {
  if (!iso || (existing && Date.parse(iso) === Date.parse(existing))) return;
  if (Date.parse(iso) < Math.floor(Date.now() / 60_000) * 60_000) {
    throw new Error('لا يمكن اختيار موعد جدولة في الماضي؛ اختر الوقت الحالي أو موعدًا لاحقًا.');
  }
}
export function cairoLocalValue(iso: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(iso));
  const p = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
export function cairoToUtc(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) throw new Error('حدد تاريخ ووقت النشر بتوقيت مصر.');
  const wall = Date.parse(`${value}:00Z`);
  let instant = wall;
  for (let i = 0; i < 3; i++) {
    const represented = Date.parse(`${cairoLocalValue(new Date(instant).toISOString())}:00Z`);
    instant += wall - represented;
  }
  const iso = new Date(instant).toISOString();
  if (cairoLocalValue(iso) !== value) throw new Error('هذا الوقت غير متاح بسبب تغيير التوقيت الصيفي؛ اختر وقتًا آخر.');
  return iso;
}
