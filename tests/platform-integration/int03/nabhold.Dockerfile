# Full development/browser dependencies are intentional in this disposable
# test image. It is never a deployable production image.
FROM ghcr.io/baobab-platform/baobab-dev:1.4.4-frontend-e2e@sha256:eb9c401cea16c4f333c28b250dd455e505752dfc6d11e9779a182a02bc207213
USER root
WORKDIR /app
ARG LAB_UID
ARG LAB_GID
RUN apt-get update && apt-get install -y --no-install-recommends libnss3-tools \
 && rm -rf /var/lib/apt/lists/* \
 && if [ -d /root/.cache/ms-playwright ]; then mv /root/.cache/ms-playwright /opt/int03-playwright; chmod -R a+rX /opt/int03-playwright; fi
COPY . .
# Source includes .git: the estate's receipt independently requires a clean
# actual checkout. Credentials are a BuildKit secret, never COPY/ARG/ENV.
RUN --mount=type=secret,id=int03_npm_token,required=true \
    --mount=type=tmpfs,target=/tmp/npm-auth \
    sh -eu -c 'printf "//npm.pkg.github.com/:_authToken=%s\n" "$(cat /run/secrets/int03_npm_token)" > /tmp/npm-auth/.npmrc; NPM_CONFIG_USERCONFIG=/tmp/npm-auth/.npmrc pnpm install --frozen-lockfile'
RUN node -e 'const [m,n]=process.versions.node.split(".").map(Number);if(m!==24||n<19)process.exit(2)' \
 && test "$(pnpm --version)" = 11.24.0 \
 && git diff --exit-code && test -z "$(git status --porcelain --untracked-files=normal)" \
 && chown -R "${LAB_UID}:${LAB_GID}" /app
USER ${LAB_UID}:${LAB_GID}
