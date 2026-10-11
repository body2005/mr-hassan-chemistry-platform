import { expect, it } from 'vitest';
import { SourceMapConsumer, type MappingItem } from 'source-map-js';

function indexedMap(line: number) {
  return { version: '3', sources: [], names: [], mappings: '', sections: [{
    offset: { line, column: 0 },
    map: { version: '3', sources: ['input.js'], names: [], mappings: 'AAAA' },
  }] };
}

it('rejects hostile indexed section offsets before source-map amplification', () => {
  // Constructor-only check is bounded even if the dependency regresses: do
  // not serialize the hostile map or execute its billion-line expansion.
  expect(() => new SourceMapConsumer(indexedMap(100_000_000)))
    .toThrow('Section offset line must not exceed');
});

it('retains normal indexed source-map mappings after the security update', () => {
  const consumer = new SourceMapConsumer(indexedMap(1));
  const mappings: MappingItem[] = [];
  consumer.eachMapping(mapping => mappings.push(mapping));
  expect(mappings).toEqual([{ source: 'input.js', generatedLine: 2,
    generatedColumn: 0, originalLine: 1, originalColumn: 0, name: null }]);
});
