from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    BundlingOptions,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_apigateway as apigw,
    aws_logs as logs,
    aws_secretsmanager as sm,
    aws_sqs as sqs,
    aws_ecr_assets as ecr_assets,
)
from constructs import Construct


class UnfurlServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Environment name
        env_name = self.node.try_get_context("env") or "dev"

        # DynamoDB table for caching unfurled data
        cache_table = dynamodb.Table(
            self,
            "UnfurlCache",
            table_name=f"unfurl-cache-{env_name}",
            partition_key=dynamodb.Attribute(
                name="url", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
            point_in_time_recovery=True,
        )

        # DynamoDB table for deduplication (prevent concurrent processing)
        deduplication_table = dynamodb.Table(
            self,
            "UnfurlDeduplication",
            table_name=f"unfurl-deduplication-{env_name}",
            partition_key=dynamodb.Attribute(
                name="url", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # SNS topic for async processing
        unfurl_topic = sns.Topic(
            self,
            "UnfurlTopic",
            topic_name=f"unfurl-events-{env_name}",
            display_name="Instagram Unfurl Events",
        )

        # Secrets references
        slack_secret = sm.Secret.from_secret_name_v2(
            self, "SlackSecret", "unfurl-service/slack"
        )

        # Lambda layer for Event Router dependencies
        deps_layer = lambda_.LayerVersion(
            self,
            "EventRouterDeps",
            code=lambda_.Code.from_asset(
                ".",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        " && ".join(
                            [
                                "pip install --no-cache-dir --platform linux_aarch64 "
                                "--target /asset-output/python/ --only-binary=:all: "
                                "-r requirements-event-router.txt || "
                                "pip install --no-cache-dir --target /asset-output/python/ "
                                "-r requirements-event-router.txt",
                                "find /asset-output -type f -name '*.pyc' -delete || true",
                                "find /asset-output -type d -name '__pycache__' -exec rm -rf {} + || true",
                                "find /asset-output -type f -name '*.so' -exec strip {} + || true",
                                "ls -la /asset-output/python/ || true",
                                "python -c \"import sys; sys.path.insert(0, '/asset-output/python'); import aws_xray_sdk; print('✅ aws-xray-sdk installed successfully')\" || echo '❌ aws-xray-sdk import failed'",
                            ]
                        ),
                    ],
                ),
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Event router dependencies with ARM64 support",
        )

        # Event router Lambda function
        event_router = lambda_.Function(
            self,
            "EventRouter",
            function_name=f"unfurl-event-router-{env_name}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("src/event_router"),
            environment={
                "SNS_TOPIC_ARN": unfurl_topic.topic_arn,
                "SLACK_SECRET_NAME": slack_secret.secret_name,
                "LOG_LEVEL": "INFO",
            },
            timeout=Duration.seconds(10),
            memory_size=256,
            reserved_concurrent_executions=10,
            layers=[deps_layer],
            log_retention=logs.RetentionDays.ONE_WEEK,
            tracing=lambda_.Tracing.ACTIVE,
        )

        # Grant permissions to event router
        slack_secret.grant_read(event_router)
        unfurl_topic.grant_publish(event_router)

        # Unfurl processor Lambda function (container-based)
        # Single optimized deployment approach
        unfurl_processor = lambda_.Function(
            self,
            "UnfurlProcessor",
            function_name=f"unfurl-processor-{env_name}-v2",
            runtime=lambda_.Runtime.FROM_IMAGE,
            architecture=lambda_.Architecture.ARM_64,
            handler=lambda_.Handler.FROM_IMAGE,
            code=lambda_.Code.from_asset_image(
                directory=".",
                platform=ecr_assets.Platform.LINUX_ARM64,
                build_args={
                    "DOCKER_BUILDKIT": "1",
                    "BUILDKIT_INLINE_CACHE": "1",
                },
                # Exclude everything except essential files for faster upload
                exclude=[
                    "cdk.out",
                    "cdk-deploy-out",
                    "node_modules",
                    ".git",
                    "__pycache__",
                    "*.pyc",
                    ".pytest_cache",
                    ".venv",
                    "*.md",
                    "docs/",
                    "tests/",
                    ".github/",
                    "*.log",
                    "*.tmp",
                    ".DS_Store",
                    "response.json",
                    "test-payload.json",
                    ".dockerignore.bak",
                    "Dockerfile.base",
                    "Dockerfile.fast",
                ],
            ),
            environment={
                "CACHE_TABLE_NAME": cache_table.table_name,
                "DEDUPLICATION_TABLE_NAME": deduplication_table.table_name,
                "SLACK_SECRET_NAME": slack_secret.secret_name,
                "CACHE_TTL_HOURS": "72",
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_METRICS_NAMESPACE": f"UnfurlService/{env_name}",
                "POWERTOOLS_SERVICE_NAME": "unfurl-processor",
                "PLAYWRIGHT_BROWSERS_PATH": "/var/task/playwright-browsers",
            },
            timeout=Duration.minutes(5),  # Increased for Playwright browser startup
            memory_size=1024,  # Increased for browser automation
            reserved_concurrent_executions=10,  # Reduced due to higher memory usage
            log_retention=logs.RetentionDays.ONE_WEEK,
            tracing=lambda_.Tracing.ACTIVE,
        )

        # Grant permissions to unfurl processor
        cache_table.grant_read_write_data(unfurl_processor)
        deduplication_table.grant_read_write_data(unfurl_processor)
        slack_secret.grant_read(unfurl_processor)

        # Video Proxy Lambda for Slack Video Block support
        video_proxy = lambda_.Function(
            self,
            "VideoProxy",
            function_name=f"video-proxy-{env_name}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="unfurl_processor.video_proxy.lambda_handler",
            code=lambda_.Code.from_asset_image(
                directory=".",
                file="Dockerfile",
                exclude=[
                    "*.pyc",
                    "__pycache__",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".coverage",
                    "htmlcov/",
                    "cdk.out/",
                    ".venv/",
                    ".git/",
                    "*.md",
                    "docs/",
                    "tests/",
                    ".github/",
                    "*.log",
                    "*.tmp",
                    ".DS_Store",
                    "response.json",
                    "test-payload.json",
                    ".dockerignore.bak",
                    "Dockerfile.base",
                    "Dockerfile.fast",
                ],
                cmd=["unfurl_processor.video_proxy.lambda_handler"],
            ),
            environment={
                "CACHE_TABLE_NAME": cache_table.table_name,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_METRICS_NAMESPACE": f"UnfurlService/{env_name}",
                "POWERTOOLS_SERVICE_NAME": "video-proxy",
            },
            timeout=Duration.seconds(30),
            memory_size=256,
            reserved_concurrent_executions=50,
            log_retention=logs.RetentionDays.ONE_WEEK,
            tracing=lambda_.Tracing.ACTIVE,
        )

        # Grant video proxy read access to cache table
        cache_table.grant_read_write_data(video_proxy)

        # Update unfurl processor environment with video proxy endpoint
        unfurl_processor.add_environment(
            "VIDEO_PROXY_BASE_URL", 
            f"https://{api.rest_api_id}.execute-api.{self.region}.amazonaws.com/prod"
        )

        # Dead Letter Queue for failed Lambda invocations
        dlq = sqs.Queue(
            self,
            "UnfurlDLQ",
            queue_name=f"unfurl-dlq-{env_name}",
            retention_period=Duration.days(14),
        )

        unfurl_topic.add_subscription(
            sns_subs.LambdaSubscription(
                unfurl_processor,
                dead_letter_queue=dlq,
            )
        )

        # API Gateway for Slack events
        api = apigw.RestApi(
            self,
            "UnfurlApi",
            rest_api_name=f"unfurl-service-{env_name}",
            description="API for Slack event subscriptions",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
                tracing_enabled=True,
                throttling_rate_limit=100,
                throttling_burst_limit=200,
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=["https://slack.com"],
                allow_methods=["POST"],
                allow_headers=[
                    "Content-Type",
                    "X-Slack-Signature",
                    "X-Slack-Request-Timestamp",
                ],
            ),
        )

        # Slack events endpoint
        slack_resource = api.root.add_resource("slack")
        events_resource = slack_resource.add_resource("events")

        # Add method with Lambda integration
        events_resource.add_method(
            "POST",
            apigw.LambdaIntegration(
                event_router,
                proxy=True,
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={"application/json": ""},
                    )
                ],
            ),
            method_responses=[apigw.MethodResponse(status_code="200")],
        )

        # Video proxy endpoint for Slack Video Block support
        video_resource = api.root.add_resource("video")
        video_url_resource = video_resource.add_resource("{video_url}")
        
        video_url_resource.add_method(
            "GET",
            apigw.LambdaIntegration(
                video_proxy,
                proxy=True,
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={"text/html": ""},
                    )
                ],
            ),
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Content-Type": True,
                        "method.response.header.X-Frame-Options": True,
                    },
                )
            ],
        )

        # CloudWatch Alarms
        event_router.metric_errors().create_alarm(
            self,
            "EventRouterErrors",
            alarm_name=f"unfurl-event-router-errors-{env_name}",
            threshold=5,
            evaluation_periods=2,
            alarm_description="Event router Lambda errors",
        )

        unfurl_processor.metric_errors().create_alarm(
            self,
            "UnfurlProcessorErrors",
            alarm_name=f"unfurl-processor-errors-{env_name}",
            threshold=10,
            evaluation_periods=2,
            alarm_description="Unfurl processor Lambda errors",
        )

        # Outputs
        self.api_url = api.url
        self.slack_webhook_url = f"{api.url}slack/events"
