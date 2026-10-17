import { expect, it } from 'vitest';
import { displayOrderingAnswer, moveOrderingItem, orderingAnswer, resolveOrderingItems, validOrderingItems } from './orderingQuestion';

const items = [{ key: 'one', text: 'H₂O, water', is_correct: false }, { key: 'two', text: 'تبريد', is_correct: false }];
it('round trips teacher keys and student text containing commas and Unicode', () => {
  const correct = resolveOrderingItems(items, 'two,one')!;
  const submitted = orderingAnswer(correct);
  expect(resolveOrderingItems(items, submitted)).toEqual(correct);
  expect(submitted).toBe('["تبريد","H₂O, water"]');
  expect(displayOrderingAnswer(submitted)).toBe('1. تبريد\n2. H₂O, water');
  expect(orderingAnswer(items)).not.toBe(submitted);
});
it('rejects missing, repeated, unknown identities and empty item texts', () => {
  expect(validOrderingItems(items)).toBe(true);
  for (const answer of ['one', 'one,one', 'one,other', '["تبريد"]', '["تبريد",7]']) expect(resolveOrderingItems(items, answer)).toBeNull();
  expect(validOrderingItems([{ ...items[0], text: ' ' }, items[1]])).toBe(false);
  expect(validOrderingItems([items[0], items[0]])).toBe(false);
  expect(validOrderingItems([items[0]])).toBe(false);
  expect(moveOrderingItem(items, 0, -1)).toBe(items);
});
it('resolves repeated text without losing an item and preserves legacy text results', () => {
  const repeated = [{ key: 'a', text: 'Same' }, { key: 'b', text: 'Same' }, { key: 'c', text: 'Other' }];
  expect(resolveOrderingItems(repeated, '["Same","Other","Same"]')?.map(item => item.key)).toEqual(['a', 'c', 'b']);
  expect(displayOrderingAnswer('2,1,3')).toBe('2,1,3');
});
