# Integration laboratory image for the integration Codespace AND the INT-02
# CI job (ADR-SHARED-036 s6.3: one image for both executors). Pinned by digest.
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39

# The base image ships a Yarn apt source whose signing key is no longer
# available, so `apt-get update` fails and every apt-based dev container
# feature (docker-outside-of-docker here) fails to install - observed in CI
# with NO_PUBKEY 62D54FD4003F6525. Nothing in this laboratory uses Yarn; the
# installed binary is untouched, only the broken package source is removed.
RUN rm -f /etc/apt/sources.list.d/yarn.list
