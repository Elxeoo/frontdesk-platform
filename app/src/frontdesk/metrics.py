"""HTTP metrics with OpenTelemetry, exported in the Prometheus format (platform contract C4-C6).

The FastAPI instrumentation records `http.server.request.duration`; Prometheus sees it as
`http_server_request_duration_seconds`. Views keep that histogram to the three labels the
contract names, fix its buckets, and drop the request and response size histograms, which nothing
uses. `http_server_active_requests` stays: a cheap gauge of in-flight requests per method.
"""

from __future__ import annotations

import os

# The instrumentation reads this once, on first use: it must be set before that happens.
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")

from fastapi import FastAPI
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import DropAggregation, ExplicitBucketHistogramAggregation, View
from prometheus_client import CollectorRegistry

# OpenTelemetry's recommended boundaries for request duration; 0.5 s is the latency objective.
DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
LABELS = frozenset({"http.request.method", "http.route", "http.response.status_code"})
# Matched against the full URL, host included: anchor the path so a crafted Host header or a
# route like /api/rooms/metrics cannot hide real traffic from the SLI.
NOT_TRAFFIC = r"^https?://[^/]+/(healthz|readyz|metrics)/?$"


def instrument(app: FastAPI) -> CollectorRegistry:
    """Instrument `app` and return the registry that `/metrics` serves."""
    registry = CollectorRegistry()
    reader = PrometheusMetricReader(
        disable_target_info=True, scope_info_enabled=False, registry=registry
    )
    provider = MeterProvider(
        metric_readers=[reader],
        views=[
            View(
                instrument_name="http.server.request.duration",
                attribute_keys=set(LABELS),
                aggregation=ExplicitBucketHistogramAggregation(boundaries=DURATION_BUCKETS),
            ),
            View(instrument_name="http.server.request.body.size", aggregation=DropAggregation()),
            View(instrument_name="http.server.response.body.size", aggregation=DropAggregation()),
        ],
    )
    FastAPIInstrumentor.instrument_app(
        app, meter_provider=provider, excluded_urls=NOT_TRAFFIC, exclude_spans=["receive", "send"]
    )
    return registry
