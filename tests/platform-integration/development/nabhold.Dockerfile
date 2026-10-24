# Disposable integration image, never a production artifact.
FROM ghcr.io/baobab-platform/baobab-dev:1.4.4-frontend-e2e@sha256:eb9c401cea16c4f333c28b250dd455e505752dfc6d11e9779a182a02bc207213
USER root
WORKDIR /app
ARG LAB_UID
ARG LAB_GID
COPY . .
COPY --from=nabhold_git . /app/.git
RUN --mount=type=secret,id=npm_token,required=true --mount=type=tmpfs,target=/tmp/npm-auth \
    sh -eu -c 'printf "//npm.pkg.github.com/:_authToken=%s\n" "$(cat /run/secrets/npm_token)" > /tmp/npm-auth/.npmrc; NPM_CONFIG_USERCONFIG=/tmp/npm-auth/.npmrc pnpm install --frozen-lockfile'
RUN chown -R "${LAB_UID}:${LAB_GID}" /app
USER ${LAB_UID}:${LAB_GID}
ENV NEXT_TELEMETRY_DISABLED=1
CMD ["pnpm","dev","--hostname","0.0.0.0","--port","3000"]
