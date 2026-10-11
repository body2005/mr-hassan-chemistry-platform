import { expect, it } from 'vitest';
import { authTabHash, readAuthTab } from './authNavigation';

it('round trips only the public auth tab', () => {
  expect(readAuthTab(authTabHash('register'))).toBe('register');
  expect(readAuthTab(authTabHash('signin'))).toBe('signin');
});
it('does not revive a stale registration choice on plain or invalid auth routes', () => {
  expect(readAuthTab('#auth', 'register')).toBe('signin');
  expect(readAuthTab('#auth?tab=administrator', 'register')).toBe('signin');
  expect(readAuthTab('#landing?tab=register')).toBe('signin');
});
it('prioritizes reset links without storing or copying their token into tab navigation', () => {
  expect(readAuthTab('#auth?tab=register&reset_token=synthetic-token')).toBe('signin');
  expect(authTabHash('register')).toBe('#auth?tab=register');
});
