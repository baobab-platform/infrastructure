import { randomBytes, timingSafeEqual, createHmac } from 'node:crypto';
import * as oidc from 'openid-client';
import { createRemoteJWKSet, jwtVerify } from 'jose';

export const issuer = 'https://iam.int02.test/realms/baobab';
export const origin = 'https://human.int02.test';
export const clientId = 'l4-int02-admin';
export const redirectUri = origin + '/callback';
export const opaque = () => randomBytes(32).toString('base64url');
export function equal(a, b) {
  return typeof a === 'string' && typeof b === 'string' && a.length === b.length &&
    timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
// Keep the accepted issuer/endpoints fixed. Discovery cannot redirect a
// client credential to a foreign host. This configuration is an RP, never an
// issuer, and verifies the real Keycloak signature using its current JWKS.
export async function configuration(secret) {
  const res = await fetch(issuer + '/.well-known/openid-configuration', { redirect: 'error' });
  if (!res.ok) throw Error('discovery');
  const meta = await res.json();
  if (meta.issuer !== issuer || !meta.code_challenge_methods_supported?.includes('S256')) throw Error('discovery');
  for (const field of ['authorization_endpoint', 'token_endpoint', 'jwks_uri']) {
    if (new URL(meta[field]).origin !== new URL(issuer).origin) throw Error('origin');
  }
  const config = new oidc.Configuration({ issuer,
    authorization_endpoint: meta.authorization_endpoint, token_endpoint: meta.token_endpoint,
    jwks_uri: meta.jwks_uri }, clientId, { id_token_signed_response_alg: 'RS256' }, oidc.ClientSecretBasic(secret));
  oidc.enableNonRepudiationChecks(config);
  config.timeout = 8;
  return { config, keys: createRemoteJWKSet(new URL(meta.jwks_uri)) };
}
export function begin(config) {
  const transaction = { state: opaque(), nonce: opaque(), verifier: oidc.randomPKCECodeVerifier(), expires: Date.now() + 60000 };
  return oidc.calculatePKCECodeChallenge(transaction.verifier).then(challenge => ({ transaction,
    url: oidc.buildAuthorizationUrl(config, { response_type: 'code', scope: 'openid', redirect_uri: redirectUri,
      state: transaction.state, nonce: transaction.nonce, code_challenge: challenge, code_challenge_method: 'S256' }) }));
}
export function validateCallback(url, transaction) {
  if (!transaction || transaction.expires <= Date.now() || url.origin + url.pathname !== redirectUri || url.hash ||
      url.searchParams.getAll('code').length !== 1 || !url.searchParams.get('code') ||
      url.searchParams.getAll('state').length !== 1 || !equal(url.searchParams.get('state'), transaction.state) ||
      url.searchParams.has('error')) throw Error('callback');
}
export async function verifyIdToken(token, keys, options = {}) {
  return jwtVerify(token, keys, { algorithms: ['RS256'], issuer, audience: clientId, ...options });
}
export async function exchange(config, keys, url, transaction) {
  validateCallback(url, transaction);
  const tokens = await oidc.authorizationCodeGrant(config, url, { pkceCodeVerifier: transaction.verifier,
    expectedState: transaction.state, expectedNonce: transaction.nonce, idTokenExpected: true });
  await verifyIdToken(tokens.id_token, keys);
  if (!tokens.access_token || tokens.token_type?.toLowerCase() !== 'bearer') throw Error('token');
  return tokens;
}

// RFC 6238 for the disposable authenticator only. The realm's committed
// policy is HmacSHA1 / six digits / 30 seconds. The secret is obtained from
// the REAL Keycloak enrolment form and never persisted or published.
export function totp(secret, seconds = Math.floor(Date.now()/1000), digits = 6) {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(seconds/30)));
  const digest = createHmac('sha1', secret).update(counter).digest();
  const offset = digest[digest.length-1] & 15;
  return ((digest.readUInt32BE(offset) & 0x7fffffff) % (10 ** digits)).toString().padStart(digits,'0');
}
