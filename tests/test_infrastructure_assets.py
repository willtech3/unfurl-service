import os

import pytest

aws_cdk = pytest.importorskip("aws_cdk")
from aws_cdk import App
from aws_cdk.assertions import Match, Template

from cdk.stacks.unfurl_service_stack import UnfurlServiceStack

RUN_CDK_TESTS = os.getenv("RUN_CDK_TESTS", "false").lower() == "true"

pytestmark = pytest.mark.skipif(
    not RUN_CDK_TESTS, reason="CDK tests require RUN_CDK_TESTS=true"
)


@pytest.fixture(scope="module")
def template() -> Template:
    app = App(context={"env": "dev", "skip_asset_bundling": True})
    stack = UnfurlServiceStack(app, "UnfurlServiceTest")
    return Template.from_stack(stack)


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


def test_assets_bucket_is_public(template: Template) -> None:
    template.resource_count_is("AWS::S3::BucketPolicy", 1)
    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": Match.object_like(
                {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
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
