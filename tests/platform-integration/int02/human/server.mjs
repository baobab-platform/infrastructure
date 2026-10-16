/** Disposable INT-02 RP and browser executor. No product issuer or authority
 * is simulated. Only boolean observations leave /proof; credentials, codes,
 * cookies and signed tokens stay in process memory and die with the service.
 * /token is available only to the private Python probe using a per-run secret.
 */
import http from 'node:http';
import { chromium } from 'playwright';
import { configuration, begin, exchange, validateCallback, verifyIdToken, opaque, equal, issuer, origin, redirectUri } from './protocol.mjs';
const secret = process.env.L4_TEST_ADMIN_CLIENT_SECRET;
const password = process.env.L4_TEST_USER_PASSWORD;
const attempts = new Map();
let settings, latest, proofRunning = false, mode = 'normal', lastExchange, stage = 'startup', failureClass = 'none', failureCode = 'none';
function reply(res, status, value) { res.writeHead(status, {'content-type':'application/json','cache-control':'no-store'}); res.end(JSON.stringify(value)); }
function cookie(req) { return req.headers.cookie?.split('; ').find(v=>v.startsWith('attempt='))?.slice(8); }
async function rejected(fn) { try { await fn(); return false; } catch { return true; } }
async function proof() {
  const checks = {};
  // Chromium is confined to this disposable, private network. Trust the run
  // CA through NSS, without ignoring HTTPS errors. The container has no
  // privileged capabilities; Chromium's sandbox cannot nest in every CI
  // runner, so process isolation is supplied by Docker for this test only.
  stage = 'browser_launch';
  const browser = await chromium.launch({headless:true, args:['--no-sandbox','--disable-dev-shm-usage']});
  async function login(which) {
    mode = which; stage = 'login_' + which;
    const context = await browser.newContext({ignoreHTTPSErrors:false});
    const page = await context.newPage();
    try {
      stage = 'login_' + which + '_visit';
      await page.goto(origin + '/login', {timeout:30000});
      stage = 'login_' + which + '_form';
      await page.locator('#username').fill('l4-int02-human');
      await page.locator('#password').fill(password);
      stage = 'login_' + which + '_submit';
      await Promise.all([page.waitForURL(origin + '/callback?**', {timeout:30000}), page.locator('#kc-login').click()]);
      stage = 'login_' + which + '_result';
      const response = await page.locator('body').innerText();
      return JSON.parse(response).accepted === true;
    } finally { await context.close(); }
  }
  try {
    checks.iam01_code_pkce_positive = await login('normal');
    if (!checks.iam01_code_pkce_positive) { stage = 'callback_exchange'; throw Error('callback'); }
    const positive = latest;
    const exchangeInput = lastExchange;
    checks.iam01_signed_id_token = !!(await verifyIdToken(positive.id_token, settings.keys));
    // Replay the SAME real Keycloak authorization code, with its original
    // verifier. A fresh login would not prove single-use code enforcement.
    checks.iam01_code_replay_denied = await rejected(()=>exchange(settings.config, settings.keys, exchangeInput.url, exchangeInput.transaction));
    const repeated = await fetch(exchangeInput.url, {redirect:'error', headers:{cookie:'attempt='+exchangeInput.handle}});
    checks.iam01_state_replay_denied = repeated.status === 401;
    for (const [which, name] of [['state','iam01_wrong_state_denied'],['nonce','iam01_wrong_nonce_denied'],['pkce','iam01_wrong_pkce_denied']]) {
      checks[name] = !(await login(which));
    }
    // These negatives reuse a REAL issuer-signed ID token. Override the
    // validator expectation (or time), not the claim: invalidating a signature
    // while changing iss/exp would conflate three distinct security checks.
    const token = positive.id_token;
    const parts = token.split('.');
    const signature = Buffer.from(parts[2],'base64url'); signature[0] ^= 1;
    checks.iam01_forged_signature_denied = await rejected(()=>verifyIdToken(parts.slice(0,2).join('.')+'.'+signature.toString('base64url'),settings.keys));
    checks.iam01_wrong_issuer_denied = await rejected(()=>verifyIdToken(token,settings.keys,{issuer:issuer+'/wrong'}));
    checks.iam01_wrong_audience_denied = await rejected(()=>verifyIdToken(token,settings.keys,{audience:'wrong-rp'}));
    const {payload} = await verifyIdToken(token,settings.keys);
    checks.iam01_expired_token_denied = await rejected(()=>verifyIdToken(token,settings.keys,{currentDate:new Date((payload.exp+1)*1000)}));
    const {transaction, url} = await begin(settings.config);
    url.searchParams.set('redirect_uri',origin+'/unregistered-callback');
    const bad = await fetch(url,{redirect:'manual'});
    checks.iam01_unregistered_callback_denied = bad.status === 400 && !bad.headers.get('location');
    checks.iam01_callback_path_denied = await rejected(()=>validateCallback(new URL(origin+'/wrong?code=x&state='+transaction.state),transaction));
    // Keep only the positive access token for CP's independent identity and
    // effective-authority checks. No ID/refresh token or browser cookie leaves.
    latest = {access_token:positive.access_token};
    return {checks};
  } finally { await browser.close(); }
}
const server = http.createServer(async(req,res)=>{
  try {
    const url = new URL(req.url,origin);
    if (url.pathname === '/readyz') return reply(res,200,{ready:true});
    if (url.pathname === '/proof' || url.pathname === '/token') {
      if (!equal(req.headers.authorization,'Bearer '+secret)) return reply(res,401,{});
      if (url.pathname === '/token') return reply(res,latest?.access_token?200:503,{access_token:latest?.access_token});
      if (proofRunning) return reply(res,409,{});
      proofRunning = true;
      stage = 'discovery';
      settings = await configuration(secret);
      return reply(res,200,await proof());
    }
    if (url.pathname === '/login') {
      const {transaction,url:authorization} = await begin(settings.config);
      const handle = opaque();
      // Fault injection changes only the RP's retained expected tuple, not
      // Keycloak's signed response. It cannot influence product IAM/CP policy.
      if (mode === 'state') transaction.state = opaque();
      if (mode === 'nonce') transaction.nonce = opaque();
      if (mode === 'pkce') transaction.verifier = opaque();
      attempts.set(handle,transaction);
      res.writeHead(303,{location:authorization.href,'set-cookie':`attempt=${handle}; Path=/; HttpOnly; Secure; SameSite=Lax`, 'cache-control':'no-store'});
      return res.end();
    }
    if (url.pathname === '/callback') {
      const handle = cookie(req), transaction = attempts.get(handle);
      // Consume before any validation/exchange, including error callbacks.
      attempts.delete(handle);
      res.setHeader('set-cookie','attempt=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0');
      if (!transaction) return reply(res,401,{accepted:false});
      try {
        latest = await exchange(settings.config, settings.keys, url, transaction);
        lastExchange = {url,transaction,handle};
        return reply(res,200,{accepted:true});
      } catch (error) { failureClass = /^[A-Za-z]{1,40}$/.test(error.constructor?.name) ? error.constructor.name : 'Other'; failureCode = /^[A-Z_]{1,48}$/.test(error.code) ? error.code : 'OTHER'; return reply(res,401,{accepted:false}); }
    }
    reply(res,404,{});
  } catch (error) { if (failureClass === 'none') failureClass = /^[A-Za-z]{1,40}$/.test(error.constructor?.name) ? error.constructor.name : 'Other'; reply(res,500,{error:'HUMAN_PROOF_FAILED',stage,failureClass,failureCode}); }
});
server.listen(8080,'0.0.0.0');
