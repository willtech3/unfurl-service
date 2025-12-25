from __future__ import annotations

from typing import Any, Dict

from opentelemetry.context import Context
from opentelemetry.propagate import extract


def extract_context_from_sns_event(event: Any) -> Context:
    """Extract W3C trace context from an SNS-triggered Lambda event.

    AWS SNS message attributes delivered to Lambda include keys like:
    - traceparent
    - tracestate
    - baggage (optional)
    """

    carrier: Dict[str, str] = {}

    try:
        if not isinstance(event, dict):
            return Context()

        records = event.get("Records")
        if not isinstance(records, list) or not records:
            return Context()

        record0 = records[0]
        if not isinstance(record0, dict):
            return Context()

        sns = record0.get("Sns")
        if not isinstance(sns, dict):
            return Context()

        attrs = sns.get("MessageAttributes", {})
        if not isinstance(attrs, dict):
            return Context()

        for key, value in attrs.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue

            raw = value.get("Value") or value.get("StringValue")
            if isinstance(raw, str) and raw:
                carrier[key] = raw

    except Exception:
        return Context()

    # Important: pass a fresh base Context() to prevent accidentally inheriting
    # a previously active context when no trace keys exist in `carrier`.
    return extract(carrier, context=Context())
