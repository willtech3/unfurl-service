"""Unit tests for OpenTelemetry trace context helpers."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from src.observability.trace_context import extract_context_from_sns_event


def test_extract_context_from_sns_event_extracts_traceparent():
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    event = {
        "Records": [
            {
                "Sns": {
                    "MessageAttributes": {
                        "traceparent": {"Type": "String", "Value": traceparent}
                    }
                }
            }
        ]
    }

    ctx = extract_context_from_sns_event(event)
    span_ctx = trace.get_current_span(ctx).get_span_context()

    assert span_ctx.is_valid is True
    assert span_ctx.is_remote is True
    assert format(span_ctx.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert format(span_ctx.span_id, "016x") == "00f067aa0ba902b7"


def test_extract_context_from_sns_event_extracts_traceparent_from_stringvalue():
    traceparent = "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"
    event = {
        "Records": [
            {
                "Sns": {
                    "MessageAttributes": {
                        "traceparent": {
                            "DataType": "String",
                            "StringValue": traceparent,
                        }
                    }
                }
            }
        ]
    }

    ctx = extract_context_from_sns_event(event)
    span_ctx = trace.get_current_span(ctx).get_span_context()

    assert span_ctx.is_valid is True
    assert format(span_ctx.trace_id, "032x") == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert format(span_ctx.span_id, "016x") == "bbbbbbbbbbbbbbbb"


def test_extract_context_from_sns_event_returns_empty_context_on_invalid_shape():
    invalid_events = [
        None,
        {},
        {"Records": []},
        {"Records": [None]},
        {"Records": [{}]},
        {"Records": [{"Sns": None}]},
        {"Records": [{"Sns": {"MessageAttributes": None}}]},
        {"Records": [{"Sns": {"MessageAttributes": {"traceparent": "nope"}}}]},
    ]

    for evt in invalid_events:
        ctx = extract_context_from_sns_event(evt)  # type: ignore[arg-type]
        span_ctx = trace.get_current_span(ctx).get_span_context()
        assert span_ctx.is_valid is False


def test_extract_context_from_sns_event_does_not_inherit_current_context():
    provider = TracerProvider()
    tracer = provider.get_tracer(__name__)

    # No traceparent present in the SNS attributes.
    event = {
        "Records": [
            {
                "Sns": {
                    "MessageAttributes": {
                        "event_type": {"Type": "String", "Value": "link_shared"}
                    }
                }
            }
        ]
    }

    with tracer.start_as_current_span("current-span"):
        current_span_ctx = trace.get_current_span().get_span_context()
        assert current_span_ctx.is_valid is True

        extracted_ctx = extract_context_from_sns_event(event)
        extracted_span_ctx = trace.get_current_span(extracted_ctx).get_span_context()
        assert extracted_span_ctx.is_valid is False
