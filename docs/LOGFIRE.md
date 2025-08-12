## Logfire Configuration Guide

This project consolidates observability (logs, traces, metrics) to Logfire.

### What’s already wired
- Both Lambdas initialize Logfire at import time and forward standard Python logging (including Powertools Logger) to Logfire.
- Cross-Lambda tracing is enabled by injecting W3C trace context into SNS `MessageAttributes` (router) and extracting it in the processor.
- CloudWatch still receives JSON-structured logs via Lambda stdout.

### Configure credentials
- Set `LOGFIRE_TOKEN` via CDK context and pass it from GitHub Actions secrets at deploy time.

Recommended: create a secret in GitHub named `LOGFIRE_TOKEN`, then pass it to CDK in your deploy step:

```yaml
# .github/workflows/deploy.yml (snippet)
    - name: Deploy CDK
      run: cdk deploy --all --require-approval never -c logfire_token=${{ secrets.LOGFIRE_TOKEN }}
```

The CDK stack injects the token into the Lambda envs:
- `LOGFIRE_TOKEN`: taken from CDK context `logfire_token`.

### Other environment variables
These are set by the CDK stack and generally don’t need changes:
- `LOGFIRE_SERVICE_NAME`: logical service name (`unfurl-event-router`, `unfurl-processor`).
- `LOG_LEVEL` (optional): controls stdlib root logger level (e.g., `INFO`, `DEBUG`).

Optional (if you ever need sampling/cost control later):
- `LOGFIRE_SAMPLE_RATE`: float 0.0–1.0 (not set by default; no sampling).

### Where to change settings
- Infrastructure: `cdk/stacks/unfurl_service_stack.py` (env vars, token wiring, API Gateway logs/tracing disabled, Lambda X-Ray disabled).
- Router Lambda: `src/event_router/handler.py` (Logfire configure + logging bridge, SNS trace injection).
- Processor Lambda: `src/unfurl_processor/entrypoint.py` (Logfire configure + logging bridge, SNS trace extraction + top span).

### Verifying
- After deploy, generate a Slack `link_shared` event and confirm:
  - Logs appear in Logfire and CloudWatch.
  - A single trace spans the router and processor with scraper and Slack API sub-spans.

### Notes
- We removed Powertools Tracer/Metrics; Powertools Logger remains for structured JSON to CloudWatch.
- API Gateway execution logs/tracing are disabled to reduce noisy log groups.
- Lambda X-Ray is disabled; Logfire is the source of truth for traces.


