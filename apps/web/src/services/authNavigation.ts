export type AuthTab = 'signin' | 'register';

// Only the public tab choice belongs in navigation state, never form values.
export function readAuthTab(hash: string, fallback: AuthTab = 'signin'): AuthTab {
  const [route, query = ''] = hash.split('?', 2);
  if (route.toLowerCase() !== '#auth') return fallback;
  const params = new URLSearchParams(query);
  if (params.has('reset_token')) return 'signin';
  const tab = params.get('tab');
  return tab === 'register' || tab === 'signin' ? tab : 'signin';
}

export function authTabHash(tab: AuthTab): string {
  return `#auth?tab=${tab}`;
}
