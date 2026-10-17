/** Closed-vocabulary browser observations for failed real-issuer navigation.
 * Never serialize URLs, page text, input values, headers or browser storage:
 * any of those may carry authorization codes or the MFA enrollment secret.
 * Classify the final page, after Playwright's bounded wait has actually failed,
 * rather than assuming the initial DOM is still the page under diagnosis.
 */
export function locationClass(raw) {
  const url = new URL(raw);
  const host = url.origin === 'https://iam.int02.test' ? 'IAM'
    : url.origin === 'https://human.int02.test' ? 'RP' : 'OTHER';
  const path = url.pathname.startsWith('/realms/baobab/protocol/openid-connect/auth') ? 'AUTHORIZE'
    : url.pathname.startsWith('/realms/baobab/login-actions/') ? 'ACTION'
    : url.pathname === '/callback' ? 'CALLBACK' : 'OTHER';
  return {host, path};
}

export async function pageDiagnostics(page) {
  const location = locationClass(page.url());
  const dom = await page.evaluate(() => {
    const count = selector => Math.min(9, document.querySelectorAll(selector).length);
    const type = document.contentType === 'text/html' ? 'HTML'
      : document.contentType === 'application/json' ? 'JSON' : 'OTHER';
    // Use fixed boolean markers, never the surrounding untrusted text.
    const text = document.body?.innerText?.toLowerCase() ?? '';
    const marker = text.includes('cookie not found') ? 'COOKIE_MISSING'
      : text.includes('update account information') ? 'PROFILE_REQUIRED'
      : text.includes('invalid parameter') ? 'INVALID_PARAMETER'
      : text.includes('we are sorry') ? 'ISSUER_ERROR'
      : text.includes('select your organization') ? 'ORGANISATION_SELECTION'
      : 'NONE';
    return {type, marker, forms:count('form'), inputs:count('input'),
      username:count('input[name="username"]'), password:count('input[name="password"]'),
      totp:count('input[name="totp"]'), otp:count('input[name="otp"]'),
      body:document.body ? (text.length ? 'TEXT' : 'EMPTY') : 'ABSENT'};
  });
  return {...location, ...dom};
}
