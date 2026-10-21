/** Actual HTTP probes; no token, principal or positive content-auth simulation. */
import assert from 'node:assert/strict';
const mode = process.argv[2];
assert(['healthy', 'database-down'].includes(mode));
assert.equal(process.env.CMS_PROBE_BASE, 'http://cms:3000');
const base = process.env.CMS_PROBE_BASE;
async function request(path, init) {
  const response = await fetch(base + path, { ...init, redirect: 'error', signal: AbortSignal.timeout(20000) });
  const raw = await response.text();
  assert(Buffer.byteLength(raw) <= 16384);
  return { response, body: raw ? JSON.parse(raw) : null };
}
try {
  const live = await request('/api/health/live');
  assert.equal(live.response.status, 200);
  assert.equal(live.body.status, 'alive');
  const ready = await request('/api/health/ready');
  const database = ready.body.dependencies.find(item => item.name === 'database');
  assert.equal(database.critical, true);
  assert.equal(database.status, mode === 'healthy' ? 'ok' : 'unavailable');
  assert.equal(ready.response.status, mode === 'healthy' ? 200 : 503);
  if (mode === 'healthy') {
    for (const authorization of [undefined, 'Basic malformed', 'Bearer token extra']) {
      const denied = await request('/v1/content/resolve', { method: 'POST',
        headers: { 'content-type': 'application/json', ...(authorization ? { authorization } : {}) }, body: '{}' });
      assert.equal(denied.response.status, 401);
      assert.equal(denied.body.code, 'AUTHENTICATION_REQUIRED');
      assert.equal(denied.response.headers.get('cache-control'), 'no-store');
    }
    // No issuer/validator is configured in this component lane. A syntactically
    // present, unissued string cannot demonstrate wrong-audience/credential proof.
    const unavailable = await request('/v1/content/resolve', { method: 'POST',
      headers: { authorization: 'Bearer unissued-component-negative', 'content-type': 'application/json' }, body: '{}' });
    assert.equal(unavailable.response.status, 503);
    assert.equal(unavailable.body.code, 'CONTENT_CONTEXT_UNAVAILABLE');
  }
  process.stdout.write(JSON.stringify({ schema: 'int03.cms.http-probe.v1', mode, passed: true,
    node: process.version, evidence_class: 'ACTUAL_CMS_COMPONENT_ONLY', identities_created: false,
    connected_qualification: false }) + '\n');
} catch {
  // Do not retain HTTP bodies, dependency errors, arbitrary routes or credentials.
  process.stderr.write('CMS_COMPONENT_HTTP_PROBE_FAILED\n');
  process.exitCode = 1;
}
