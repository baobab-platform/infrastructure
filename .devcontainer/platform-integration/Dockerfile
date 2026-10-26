# Integration laboratory image for the integration Codespace AND the INT-02
# CI job (ADR-SHARED-036 s6.3: one image for both executors). Pinned by digest.
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39

# The base image ships a Yarn apt source whose signing key is no longer
# available, so `apt-get update` fails and every apt-based dev container
# feature (docker-outside-of-docker here) fails to install - observed in CI
# with NO_PUBKEY 62D54FD4003F6525. Nothing in this laboratory uses Yarn; the
# installed binary is untouched, only the broken package source is removed.
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Run as the image's non-root user (remoteUser in devcontainer.json). The
# Dev Containers CLI installs features in its own build stage as root.
# Existing canonical registry parser, also used by platform-int03 source CI.
# Install once in the shared image so Actions and Codespaces use the same port.
# DEV-14/15 invokes the *real* Shared canonical validator inside this
# same Codespaces/Actions lab. Match Shared's pinned Foundation test
# dependencies, rather than trusting an accidentally preinstalled jsonschema.
RUN python3 -m pip install --no-cache-dir \
    PyYAML==6.0.3 \
    check-jsonschema==0.38.0 \
    rfc3339-validator==0.1.4 \
    rfc3986-validator==0.1.1

USER vscode
