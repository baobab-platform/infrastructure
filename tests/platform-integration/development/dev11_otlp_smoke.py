"""Real OpenTelemetry Python SDK exporter smoke, not a fake Jaeger projection.

Runs ONLY against the disposable DEV-11 collector. Does not impersonate IAM,
CP, Trade or ERP, and is not counted as L4-OPS-01 native service acceptance.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-private-trace-id", required=True)
    args = parser.parse_args()
    provider = TracerProvider(resource=Resource.create({
        "service.name": "dev11-telemetry-probe",
        "service.namespace": "baobab",
        "deployment.environment.name": "development",
    }))
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces",
                         timeout=10)))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("baobab.dev11.qualification")
    with tracer.start_as_current_span("dev11.smoke.root") as root:
        trace_id = format(root.get_span_context().trace_id, "032x")
        with tracer.start_as_current_span("dev11.smoke.child") as child:
            child.set_attribute("baobab.dev11.test_profile", "LOCAL_COLLECTOR_ONLY")
    if not provider.force_flush(timeout_millis=20000):
        raise RuntimeError("DEV11_REAL_OTLP_EXPORT_FAILED")
    provider.shutdown()
    # Kept ONLY on the run-owned disposable Docker volume; never upload raw IDs.
    Path(args.output_private_trace_id).write_text(trace_id + "\n")

if __name__ == "__main__":
    main()
