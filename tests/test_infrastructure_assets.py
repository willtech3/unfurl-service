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
        "BlockPublicAcls": False,
        "BlockPublicPolicy": False,
        "IgnorePublicAcls": False,
        "RestrictPublicBuckets": False,
    }


@pytest.fixture(scope="module")
def match(template_and_match):
    _, match = template_and_match
    return match


def test_assets_bucket_is_public_during_migration(
    template: Template, match: Match
) -> None:
    """During the phased migration the bucket still grants public read so old
    direct-S3 URLs in existing Slack messages keep resolving. The follow-up
    PR after the lifecycle window will remove this statement."""
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
                                    "Principal": {"AWS": "*"},
                                }
                            )
                        ]
                    )
                }
            )
        },
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
    """Bucket policy must include a CloudFront service-principal grant (OAC).

    During the phased migration this statement coexists with the public-read
    statement from `public_read_access=True`; after lockdown only this grant
    will remain.
    """
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
