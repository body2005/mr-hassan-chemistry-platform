import type { APIRequest } from '@playwright/test';
import { expect } from './qaTest';

/** CLI test contexts model the browser's cookie + double-submit CSRF policy. */
export async function cookieApi(request: APIRequest, email: string, password: string) {
  const baseURL = `${process.env.QA_BASE_URL || 'http://127.0.0.1:18080'}/api/v1/`;
  const options = { baseURL, ignoreHTTPSErrors: process.env.QA_LOCAL_TLS === 'true' };
  const loginContext = await request.newContext(options);
  try {
    const response = await loginContext.post('auth/login', {data:{email, password, institution_slug:'demo'}});
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).not.toHaveProperty('token');
    const state = await loginContext.storageState();
    const access = state.cookies.find(c => c.name === 'matgar_session');
    const csrf = state.cookies.find(c => c.name === 'matgar_csrf');
    expect(access?.httpOnly).toBe(true);
    expect(csrf?.value).toBeTruthy();
    return {context: await request.newContext({...options, storageState:state,
      extraHTTPHeaders:{'X-CSRF-Token':csrf!.value}}), id:body.user.id as string};
  } finally { await loginContext.dispose(); }
}
