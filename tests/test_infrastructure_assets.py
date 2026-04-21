from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from aws_cdk.assertions import Match, Template

RUN_CDK_TESTS = os.getenv("RUN_CDK_TESTS", "false").lower() == "true"

pytestmark = pytest.mark.skipif(
    not RUN_CDK_TESTS,
    reason="CDK tests require RUN_CDK_TESTS=true",
)

if RUN_CDK_TESTS:
    pytest.importorskip("aws_cdk")


@pytest.fixture(scope="module")
def template_and_match():
    from aws_cdk import App
    from aws_cdk.assertions import Match, Template

    from cdk.stacks.unfurl_service_stack import UnfurlServiceStack

    app = App(context={"env": "dev", "skip_asset_bundling": True})
    stack = UnfurlServiceStack(app, "UnfurlServiceTest")
    return Template.from_stack(stack), Match


@pytest.fixture(scope="module")
def template(template_and_match):
    template, _ = template_and_match
    return template


def test_assets_bucket_configuration(template: Template) -> None:
    buckets = template.find_resources("AWS::S3::Bucket")
    assert buckets, "Expected an S3 bucket to be defined"

    bucket = next(iter(buckets.values()))["Properties"]
    assert bucket.get("BucketName") == "unfurl-assets-dev"
    assert bucket.get("LifecycleConfiguration") == {
        "Rules": [
            {
                "ExpirationInDays": 30,
                "Status": "Enabled",
            }
        ]
    }
    assert bucket.get("PublicAccessBlockConfiguration") == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }


@pytest.fixture(scope="module")
def match(template_and_match):
    _, match = template_and_match
    return match


def test_assets_bucket_is_private(template: Template, match: Match) -> None:
    """Bucket policy grants access only to CloudFront via OAC, never to `*`."""
    policies = template.find_resources("AWS::S3::BucketPolicy")
    for policy in policies.values():
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        for statement in statements:
            principal = statement.get("Principal", {})
            if principal.get("AWS") == "*":
                raise AssertionError(
                    "Assets bucket policy must not grant access to Principal AWS:*"
                )


def test_cloudfront_distribution_uses_oac(template: Template, match: Match) -> None:
    template.resource_count_is("AWS::CloudFront::Distribution", 1)
    template.resource_count_is("AWS::CloudFront::OriginAccessControl", 1)
    template.has_resource_properties(
        "AWS::CloudFront::OriginAccessControl",
        {
            "OriginAccessControlConfig": match.object_like(
                {
                    "OriginAccessControlOriginType": "s3",
                    "SigningBehavior": "always",
                    "SigningProtocol": "sigv4",
                }
            )
        },
    )
    template.has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": match.object_like(
                {
                    "Enabled": True,
                    "DefaultCacheBehavior": match.object_like(
                        {"ViewerProtocolPolicy": "redirect-to-https"}
                    ),
                }
            )
        },
    )


def test_assets_bucket_policy_grants_cloudfront(
    template: Template, match: Match
) -> None:
    """The only bucket-policy statement should allow CloudFront service principal."""
    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": match.object_like(
                {
                    "Statement": match.array_with(
                        [
                            match.object_like(
                                {
                                    "Action": "s3:GetObject",
                                    "Effect": "Allow",
                                    "Principal": {
                                        "Service": "cloudfront.amazonaws.com"
                                    },
                                }
                            )
                        ]
                    )
                }
            )
        },
    )


def test_unfurl_processor_env_includes_assets_bucket(template: Template) -> None:
    bucket_id = next(iter(template.find_resources("AWS::S3::Bucket")))
    functions = template.find_resources(
        "AWS::Lambda::Function",
        {"Properties": {"FunctionName": "unfurl-processor"}},
    )
    assert functions, "Expected unfurl processor Lambda to be defined"

    function_props = next(iter(functions.values()))["Properties"]
    variables = function_props.get("Environment", {}).get("Variables", {})
    assert variables.get("ASSETS_BUCKET_NAME") == {"Ref": bucket_id}

    public_base_url = variables.get("ASSETS_PUBLIC_BASE_URL")
    assert (
        public_base_url is not None
    ), "Expected ASSETS_PUBLIC_BASE_URL env var on unfurl processor"
    # CDK builds the URL via Fn::Join referencing the distribution's domain name.
    assert isinstance(public_base_url, dict) and "Fn::Join" in public_base_url, (
        f"Expected ASSETS_PUBLIC_BASE_URL to reference the CloudFront domain, "
        f"got {public_base_url!r}"
    )
