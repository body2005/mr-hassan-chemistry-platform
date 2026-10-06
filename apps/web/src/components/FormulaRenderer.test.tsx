import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import katex from 'katex';
import { FormulaRenderer } from './FormulaRenderer';
afterEach(() => { vi.restoreAllMocks(); });
it('escapes untrusted text when KaTeX actually throws, not only parse errors', () => {
  vi.spyOn(katex, 'renderToString').mockImplementation(() => { throw new Error('Forced rendering failure'); });
  const html = renderToStaticMarkup(React.createElement(FormulaRenderer, {text:'$<img src=x onerror=alert(1)>$'}));
  const element = document.createElement('div'); element.innerHTML = html;
  expect(element.querySelector('img')).toBeNull();
  expect(element.querySelector('[onerror]')).toBeNull();
  expect(element.textContent).toContain('<img');
});
