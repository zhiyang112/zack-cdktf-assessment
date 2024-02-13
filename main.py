#!/usr/bin/env python
import os
import subprocess
import sys
import os.path as Path
import json
from constructs import Construct
from cdktf import App, TerraformStack, TerraformAsset, AssetType, TerraformOutput

# providers
from cdktf_cdktf_provider_aws.provider import AwsProvider
from cdktf_cdktf_provider_local.provider import LocalProvider
from cdktf_cdktf_provider_aws.sns_topic import SnsTopic
from cdktf_cdktf_provider_aws.sns_topic_subscription import SnsTopicSubscription
from cdktf_cdktf_provider_aws.lambda_function import (
    LambdaFunction,
    LambdaFunctionEnvironment,
)
from cdktf_cdktf_provider_aws.lambda_function_event_invoke_config import (
    LambdaFunctionEventInvokeConfig,
)
from cdktf_cdktf_provider_aws.s3_bucket import S3Bucket
from cdktf_cdktf_provider_aws.s3_bucket_public_access_block import (
    S3BucketPublicAccessBlock,
)
from cdktf_cdktf_provider_aws.s3_bucket_notification import (
    S3BucketNotification,
    S3BucketNotificationTopic,
)
from cdktf_cdktf_provider_aws.ssm_parameter import SsmParameter
from cdktf_cdktf_provider_aws.s3_bucket_website_configuration import (
    S3BucketWebsiteConfiguration,
    S3BucketWebsiteConfigurationIndexDocument,
)
from cdktf_cdktf_provider_aws.s3_bucket_notification import (
    S3BucketNotificationLambdaFunction,
)

# resources
from cdktf import Token, TerraformStack
from cdktf_cdktf_provider_local.file import File
from cdktf_cdktf_provider_aws.lambda_function import (
    LambdaFunction,
    LambdaFunctionEnvironment,
    LambdaFunctionDeadLetterConfig,
)
from cdktf_cdktf_provider_aws.lambda_function_url import LambdaFunctionUrl


def run_command(commands, cwd):
    """Run a list of commands."""
    try:
        for command in commands:
            subprocess.check_call(command, shell=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


def lambda_libs(lambda_dir):
    """Install requirements.txt to libs subfolder."""
    os_name = os.name

    # ref https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies
    if os_name == "Darwin":
        # MacOS specific commands
        commands = [
            "rm -rf libs",
            'docker run --platform linux/x86_64 -v "$PWD":/var/task public.ecr.aws/sam/build-python3.9 /bin/sh -c "pip install -r requirements.txt -t libs; exit"',
        ]
    else:
        # Other OS (assuming Linux) specific commands
        # commands = [
        #     "rmdir /s /q libs",
        #     "mkdir libs",
        #     "pip install -r requirements.txt -t libs --python-version 3.9 --no-deps",
        # ]
        commands = [
            "rm -rf libs && mkdir libs",
            "pip install -r requirements.txt -t libs --platform manylinux_2_28_x86_64 --python-version 3.9 --no-deps",
        ]
    run_command(commands, lambda_dir)


class BackendStack(TerraformStack):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)
        self.buckets = {}

        lambda_role = "arn:aws:iam::000000000000:role/lambda-role"
        AwsProvider(self, "Aws")

        # ✅ Create failed-resize SNS Topic and SNS Topic Subscription (email protocol)
        dlq_topic = SnsTopic(
            self,
            "failed-resize-topic",
            name="failed-resize-topic",
        )
        SnsTopicSubscription(
            self,
            "failed-resize-topic-sub",
            endpoint="my-email@example.com",
            protocol="email",
            topic_arn="arn:aws:sns:us-east-1:000000000000:failed-resize-topic",
        )

        # build lambdas/resize/libs folder
        # reference https://developer.hashicorp.com/terraform/cdktf/concepts/assets

        # ✅ Set resize lambda's dead_letter_config to failed-resize SNS Topic
        lambda_libs("lambdas/resize")
        resize_asset = TerraformAsset(
            self,
            "resize_asset",
            path=Path.join(os.getcwd(), "lambdas/resize"),
            type=AssetType.ARCHIVE,
        )
        resize_lambda_func = LambdaFunction(
            self,
            "resize_func_lambda",
            function_name="resize",
            runtime="python3.9",
            timeout=10,
            handler="handler.handler",
            role=lambda_role,
            filename=resize_asset.path,
            source_code_hash=resize_asset.asset_hash,
            environment=LambdaFunctionEnvironment(variables={"STAGE": "local"}),
            dead_letter_config={"target_arn": dlq_topic.arn},
        )
        LambdaFunctionEventInvokeConfig(
            self,
            f"resize_invoke",
            function_name=resize_lambda_func.function_name,
            maximum_event_age_in_seconds=300,
            maximum_retry_attempts=2,
            qualifier="$LATEST",
        )

        # ✅ Create S3 Buckets for ["images", "resized"]
        # ✅ Create SSM Parameters /localstack-thumbnail-app/buckets/["images", "resized"]
        # ✅ Set S3BucketNotification for images bucket to Trigger resize lambda on "s3:ObjectCreated:*"

        be_buckets = [
            {
                "name": "images",
                "configuration": {
                    "trigger": True,
                    "event": ["s3:ObjectCreated:*"],
                    "lambda_function_arn": resize_lambda_func.arn,
                },
            },
            {"name": "resized", "configuration": {"trigger": False}},
        ]

        # ✅ Set S3BucketNotification for images bucket to Trigger resize lambda on "s3:ObjectCreated:*"
        for bkt in be_buckets:
            # Create bucket
            bucket = S3Bucket(
                self,
                f"{bkt['name']}_bucket",
                bucket=f"localstack-thumbnails-app-{bkt['name']}",
            )
            # Create SSM Param store variable
            SsmParameter(
                self,
                f"{bkt['name']}_bucket_ssm",
                name=f"/localstack-thumbnail-app/buckets/{bkt['name']}",
                type="String",
                value=bucket.id,
            )
            # Create trigger
            if bkt["configuration"]["trigger"]:
                S3BucketNotification(
                    self,
                    f"{bkt['name']}_notification",
                    bucket=bucket.id,
                    lambda_function=[
                        S3BucketNotificationLambdaFunction(
                            events=bkt["configuration"]["event"],
                            lambda_function_arn=Token.as_string(
                                bkt["configuration"]["lambda_function_arn"]
                            ),
                        )
                    ],
                )

        # ✅ Create Lambda functions for resize, list and presign handlers
        # ✅ Set LambdaFunctionEventInvokeConfig

        functions = ["presign", "list"]
        for function_name in functions:
            asset = TerraformAsset(
                self,
                f"{function_name}_asset",
                path=Path.join(os.getcwd(), f"lambdas/{function_name}"),
                type=AssetType.ARCHIVE,
            )
            lambda_function = LambdaFunction(
                self,
                f"{function_name}_lambda",
                function_name=function_name,
                runtime="python3.9",
                timeout=10,
                handler="handler.handler",
                role=lambda_role,
                filename=asset.path,
                source_code_hash=asset.asset_hash,
                environment=LambdaFunctionEnvironment(variables={"STAGE": "local"}),
            )
            function_url = LambdaFunctionUrl(
                self,
                f"{function_name}_latest",
                function_name=lambda_function.function_name,
                authorization_type="NONE",
            )
            LambdaFunctionEventInvokeConfig(
                self,
                f"{function_name}_invoke",
                function_name=Token.as_string(lambda_function.function_name),
                maximum_event_age_in_seconds=300,
                maximum_retry_attempts=2,
                qualifier="$LATEST",
            )
            TerraformOutput(
                self,
                f"{function_name}_url",
                value=function_url.function_url,
            )


class FrontEndStack(TerraformStack):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)

        AwsProvider(self, "Aws")
        LocalProvider(self, "local")

        # ✅ Create S3 Buckets for "webapp"
        # ✅ Set S3BucketWebsiteConfiguration and s3 policy for PulblicRead
        fe_buckets = [
            {
                "name": "webapp",
                "config": {"block_public_access": False},
            }
        ]
        for bkt in fe_buckets:
            # Create bucket
            bucket = S3Bucket(
                self,
                f"{bkt['name']}_bucket",
                bucket=f"localstack-thumbnails-app-{bkt['name']}",
            )
            # Configure public access
            S3BucketPublicAccessBlock(
                self,
                f"{bkt['name']}_public_access",
                block_public_acls=bkt["config"]["block_public_access"],
                block_public_policy=bkt["config"]["block_public_access"],
                bucket=bucket.id,
            )
            S3BucketWebsiteConfiguration(
                self,
                f"{bkt['name']}_config",
                bucket=Token.as_string(bucket.id),
                index_document=S3BucketWebsiteConfigurationIndexDocument(
                    suffix="index.html"
                ),
            )

        # Write dotenv config for website deploy script
        File(
            self,
            "env",
            filename=Path.join(os.getcwd(), "website", ".env.local"),
            content=f"S3_BUCKET_FRONTEND={bucket.bucket}",
        )

        # output bucket Name
        TerraformOutput(
            self,
            "localstack_url",
            value=f"http://{bucket.bucket}.s3-website.localhost.localstack.cloud:4566",
        )


app = App()
BackendStack(app, "iac-assignment-backend")
FrontEndStack(app, "iac-assignment-frontend")

app.synth()
