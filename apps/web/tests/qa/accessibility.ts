import AxeBuilder from '@axe-core/playwright';
import type { Page, TestInfo } from '@playwright/test';
import { expect } from '@playwright/test';

export async function assertAccessible(page: Page, info: TestInfo, state: string) {
  // Measure the settled UI, not transient opacity during modal fade-in. Never
  // wait for infinite loading/spinner animations or exclude axe rules/nodes.
  await page.evaluate(async () => {
    await Promise.all(document.getAnimations().filter(animation => {
      const iterations = animation.effect?.getTiming().iterations;
      return iterations !== Infinity;
    }).map(animation => animation.finished.catch(() => undefined)));
  });
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  await info.attach(state + '-axe.json', { body: JSON.stringify(result), contentType: 'application/json' });
  expect(result.violations.map(violation => ({ id: violation.id, impact: violation.impact,
    nodes: violation.nodes.map(node => ({ target: node.target, summary: node.failureSummary })) })), state).toEqual([]);
}
