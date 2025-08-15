# CloudWatch Metrics (Deprecated)

This service has consolidated metrics to Logfire. Custom CloudWatch metric
emission (PutMetricData) has been removed from the code and IAM policies.

Refer to `docs/LOGFIRE.md` for current observability guidance and to the
centralized instruments in `src/observability/metrics.py`.
