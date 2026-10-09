import { useEffect, useState } from 'react';
import { courseService } from './lmsService';
import type { CatalogGrade } from './catalogState';
import type { Course } from '../types/lms';

type CatalogResult = { courses: Course[]; pages: number; total: number };
type Snapshot = CatalogResult & { key: string; error: 'rate' | 'unavailable' | null };

/** Public-only, paginated reads. No user cache, automatic retry or stale results. */
export function usePublicCatalog(query: string, grade: CatalogGrade, enabled: boolean) {
  const normalized = query.normalize('NFKC').trim().slice(0, 100);
  const filterKey = JSON.stringify([normalized, grade]);
  const [selection, setSelection] = useState({ filterKey, page: 1 });
  const page = selection.filterKey === filterKey ? selection.page : 1;
  const [retry, setRetry] = useState(0);
  const key = JSON.stringify([filterKey, page, retry]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void courseService.getPublicCatalogPage(page, normalized, grade, controller.signal).then(result => {
        if (active) setSnapshot({ ...result, key, error: null });
      }).catch(error => {
        if (active) setSnapshot({ key, courses: [], total: 0, pages: 0,
          error: error?.status === 429 ? 'rate' : 'unavailable' });
      });
    }, 300);
    return () => { active = false; window.clearTimeout(timer); controller.abort(); };
  }, [enabled, normalized, grade, page, key]);
  const current = snapshot?.key === key ? snapshot : null;
  return {
    courses: current?.courses ?? [], total: current?.total ?? 0, pages: current?.pages ?? 0,
    page, loading: enabled && !current, error: current?.error ?? null,
    retry: () => setRetry(value => value + 1),
    setPage: (next: number) => setSelection({ filterKey, page: next }),
  };
}
