# Narrow DEV-11 disposable trace-export probe. No enterprise service identity.
# Dependencies are pinned; future image SHA custody is a separate DEV-10 gate.
FROM python:3.14.0-slim
RUN pip install --no-cache-dir --disable-pip-version-check \
    opentelemetry-api==1.38.0 \
    opentelemetry-sdk==1.38.0 \
    opentelemetry-exporter-otlp-proto-http==1.38.0
USER 65532:65532
WORKDIR /work
ENTRYPOINT ["python", "-B"]
