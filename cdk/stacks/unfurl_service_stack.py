from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_logs as logs,
    aws_secretsmanager as sm,
    aws_sqs as sqs,
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

        # Lambda layer for shared dependencies
        deps_layer = lambda_.LayerVersion(
            self,
            "DepsLayer",
            code=lambda_.Code.from_asset("lambda_layers/deps"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Shared dependencies for unfurl service",
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

        # Unfurl processor Lambda function
        unfurl_processor = lambda_.Function(
            self,
            "UnfurlProcessor",
            function_name=f"unfurl-processor-{env_name}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("src/unfurl_processor"),
            environment={
                "CACHE_TABLE_NAME": cache_table.table_name,
                "SLACK_SECRET_NAME": slack_secret.secret_name,
                "CACHE_TTL_HOURS": "24",
                "LOG_LEVEL": "INFO",
            },
            timeout=Duration.seconds(30),
            memory_size=512,
            reserved_concurrent_executions=20,
            layers=[deps_layer],
            log_retention=logs.RetentionDays.ONE_WEEK,
            tracing=lambda_.Tracing.ACTIVE,
        )

        # Grant permissions to unfurl processor
        cache_table.grant_read_write_data(unfurl_processor)
        slack_secret.grant_read(unfurl_processor)

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
