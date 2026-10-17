import type { CourseOption } from '../types/quiz';

export const MAX_ORDERING_ITEMS = 26;
export function newOrderingItem(text = ''): CourseOption {
  return { key: crypto.randomUUID(), text, is_correct: false };
}

/** Resolve both editor key sequences and published text sequences, including repeated text. */
export function resolveOrderingItems<T extends { key?: string; text: string }>(items: T[], answer?: string | null): T[] | null {
  if (!answer) return null;
  const keys = answer.split(',');
  if (keys.length === items.length && new Set(keys).size === items.length && keys.every(key => items.some(item => item.key === key))) {
    return keys.map(key => items.find(item => item.key === key)!);
  }
  try {
    const texts: unknown = JSON.parse(answer);
    if (!Array.isArray(texts) || texts.length !== items.length || texts.some(text => typeof text !== 'string')) return null;
    const remaining = [...items];
    const ordered: T[] = [];
    for (const text of texts) {
      const index = remaining.findIndex(item => item.text === text);
      if (index < 0) return null;
      ordered.push(...remaining.splice(index, 1));
    }
    return ordered;
  } catch { return null; }
}

export function validOrderingItems(items: { key?: string; text: string }[]): boolean {
  return items.length >= 2 && items.length <= MAX_ORDERING_ITEMS
    && items.every(item => typeof item.key === 'string' && !!item.key && !item.key.includes(',') && !!item.text.trim() && item.text.length <= 1000)
    && new Set(items.map(item => item.key)).size === items.length;
}

export function moveOrderingItem<T>(items: T[], from: number, to: number): T[] {
  if (from < 0 || to < 0 || from >= items.length || to >= items.length || from === to) return items;
  const result = [...items];
  const [item] = result.splice(from, 1);
  result.splice(to, 0, item);
  return result;
}

export function orderingAnswer(items: { text: string }[]): string {
  return JSON.stringify(items.map(item => item.text));
}

export function displayOrderingAnswer(answer: string): string {
  try {
    const items: unknown = JSON.parse(answer);
    if (Array.isArray(items) && items.every(item => typeof item === 'string')) return items.map((text, index) => `${index + 1}. ${text}`).join('\n');
  } catch { /* Legacy text answers remain readable. */ }
  return answer;
}
