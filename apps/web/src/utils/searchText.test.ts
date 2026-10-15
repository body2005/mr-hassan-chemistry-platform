import { expect, it } from 'vitest';
import { searchText } from './searchText';

it.each(['أسئلة', 'إسئلة', 'آسئلة', 'ٱسئلة', 'ا\u0654سئلة'])('matches the alef variant %s with plain alef', title => {
  expect(searchText(title)).toBe(searchText('اسئلة'));
});
it('matches Arabic diacritics and English case without changing the original title', () => {
  const original = '  أَسْئِلَة Chemistry  ';
  expect(searchText(original)).toBe('اسئلة chemistry');
  expect(original).toBe('  أَسْئِلَة Chemistry  ');
});
