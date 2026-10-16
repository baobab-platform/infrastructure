import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPair, SignJWT } from 'jose';
import { validateCallback, verifyIdToken, redirectUri, issuer, clientId, totp } from './protocol.mjs';
test('callback rejects expiry, state, duplicate parameters and wrong callback before exchange', () => {
  const tx = { state: 'expected', expires: Date.now() + 60000 };
  validateCallback(new URL(redirectUri + '?state=expected&code=real'), tx);
  for (const url of [redirectUri + '?state=wrong&code=real', redirectUri + '?state=expected&code=real&code=again',
    redirectUri + '?state=expected&state=expected&code=real', redirectUri + '/other?state=expected&code=real',
    redirectUri + '?state=expected&code=real#error']) assert.throws(() => validateCallback(new URL(url), tx));
  assert.throws(() => validateCallback(new URL(redirectUri + '?state=expected&code=real'), { ...tx, expires: 0 }));
});
test('maintained JWT validator independently rejects bad signature, issuer, audience and expiry', async () => {
  const pair = await generateKeyPair('RS256');
  const other = await generateKeyPair('RS256');
  const sign = key => new SignJWT({}).setProtectedHeader({alg:'RS256'}).setIssuer(issuer).setAudience(clientId)
    .setSubject('test').setIssuedAt().setExpirationTime('1m').sign(key);
  const token = await sign(pair.privateKey);
  await verifyIdToken(token, pair.publicKey);
  await assert.rejects(verifyIdToken(await sign(other.privateKey), pair.publicKey));
  await assert.rejects(verifyIdToken(token, pair.publicKey, {issuer:'https://wrong.invalid'}));
  await assert.rejects(verifyIdToken(token, pair.publicKey, {audience:'wrong'}));
  await assert.rejects(verifyIdToken(token, pair.publicKey, {currentDate:new Date(Date.now()+120000)}));
});

test('disposable authenticator matches RFC 6238 SHA1 vectors', () => {
  const secret = Buffer.from('12345678901234567890');
  for (const [time,expected] of [[59,'94287082'],[1111111109,'07081804'],[1111111111,'14050471'],[1234567890,'89005924'],[2000000000,'69279037'],[20000000000,'65353130']]) {
    assert.equal(totp(secret,time,8),expected);
  }
});
