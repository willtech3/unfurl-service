from __future__ import annotations

import os

import pytest

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


def test_assets_bucket_is_public(template: Template, match: Match) -> None:
    template.resource_count_is("AWS::S3::BucketPolicy", 1)
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
