# Browser and OIDC relying-party probe; only synthetic identities exist here.
# Node is pinned independently of the product IAM and CP images.
FROM node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund \
 && npx playwright install --with-deps chromium \
 && apt-get update && apt-get install -y --no-install-recommends libnss3-tools \
 && rm -rf /var/lib/apt/lists/* \
 && chmod -R a+rX /root/.cache/ms-playwright \
 && mv /root/.cache/ms-playwright /opt/playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
COPY *.mjs ./
# Browser trust is installed into this disposable user's NSS database at
# startup. Neither ignoreHTTPSErrors nor a certificate bypass is permitted.
USER node
ENTRYPOINT ["/bin/sh", "-ec", "mkdir -p /home/node/.pki/nssdb; certutil -N --empty-password -d sql:/home/node/.pki/nssdb; certutil -A -d sql:/home/node/.pki/nssdb -n int02-run-ca -t C,, -i /run/l4-tls/ca.pem; exec node server.mjs"]
