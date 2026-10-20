/** Only the existing consumer launcher runs. No fake IAM, CP or session store. */
import { execFileSync, spawn } from 'node:child_process';
import { mkdirSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
const mode = process.argv[2];
// Export ONLY a fixed lifecycle label; callback URLs, cookies, browser output
// and private configuration must never reach CI or an evidence artifact.
let failurePhase = 'ENTRY';
try {
  if (!['dev', 'test'].includes(mode) || process.argv.length !== 3) throw Error();
  // Chromium uses NSS independently of Node's extra roots. No ignore flags.
  const home = process.env.HOME;
  mkdirSync(join(home, '.pki/nssdb'), { recursive: true, mode: 0o700 });
  failurePhase = 'CONFIG';
  const { loadIntegrationEnvironment } = await import('/app/scripts/integration/config.ts');
  const env = loadIntegrationEnvironment();
  failurePhase = 'CA_TRUST';
  execFileSync('certutil', ['-N', '--empty-password', '-d', `sql:${home}/.pki/nssdb`], { stdio: 'ignore' });
  execFileSync('certutil', ['-A', '-d', `sql:${home}/.pki/nssdb`, '-n', 'int03-run-ca', '-t', 'C,,', '-i', env.NODE_EXTRA_CA_CERTS], { stdio: 'ignore' });
  failurePhase = 'BROWSER_DISCOVERY';
  const roots = ['/root/.cache/ms-playwright', '/ms-playwright', '/opt/playwright', '/opt/int03-playwright'];
  function browser(dir) {
    try {
      for (const child of readdirSync(dir, { withFileTypes: true })) {
        if (child.isFile() && ['chrome', 'headless_shell'].includes(child.name)) return join(dir, child.name);
        if (child.isDirectory()) { const found = browser(join(dir, child.name)); if (found) return found; }
      }
    } catch { /* Search only known image-owned browser locations. */ }
  }
  const executable = roots.map(browser).find(Boolean);
  if (!executable) throw Error();
  env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = executable;
  // Node's root bundle is read when THIS child starts, before OIDC requests.
  failurePhase = 'CHILD_LAUNCH';
  const child = spawn('node', ['--experimental-strip-types', 'scripts/integration/run.mjs', mode], {
    cwd: '/app', env, stdio: ['ignore', 'ignore', 'ignore'], shell: false,
  });
  for (const signal of ['SIGTERM', 'SIGINT']) process.once(signal, () => child.kill(signal));
  child.once('error', () => { console.error('INT03_CONSUMER_FAILURE=CHILD_LAUNCH'); process.exitCode = 2; });
  child.once('exit', code => {
    process.exitCode = code === 0 ? 0 : 2;
    if (mode === 'test') {
      // Output only the consumer's sanitized receipt; never browser diagnostics.
      try {
        const runs = readdirSync('/app/.integration').filter(n => /^identity-smoke-/.test(n));
        if (runs.length !== 1) throw Error();
        const raw = readFileSync(`/app/.integration/${runs[0]}/completed/receipt.json`);
        if (raw.length > 16384) throw Error();
        process.stdout.write(raw);
      } catch { console.error('INT03_CONSUMER_FAILURE=RECEIPT_UNAVAILABLE'); process.exitCode = 2; }
    }
    if (code !== 0) console.error('INT03_CONSUMER_FAILURE=CHILD_NONZERO');
  });
} catch {
  console.error(`INT03_CONSUMER_FAILURE=${failurePhase}`);
  process.exitCode = 2;
}
