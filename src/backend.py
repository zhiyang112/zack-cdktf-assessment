#!/usr/bin/env python
import os
import os.path as Path
from constructs import Construct
from cdktf import TerraformStack, TerraformAsset, AssetType, TerraformOutput

# providers
from cdktf_cdktf_provider_aws.provider import AwsProvider
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
from cdktf_cdktf_provider_aws.s3_bucket_notification import (
    S3BucketNotification,
)
from cdktf_cdktf_provider_aws.ssm_parameter import SsmParameter
from cdktf_cdktf_provider_aws.s3_bucket_notification import (
    S3BucketNotificationLambdaFunction,
)

# resources
from cdktf import Token, TerraformStack
from cdktf_cdktf_provider_aws.lambda_function import (
    LambdaFunction,
    LambdaFunctionEnvironment,
)
from cdktf_cdktf_provider_aws.lambda_function_url import LambdaFunctionUrl
from utils.utils import lambda_libs


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
            topic_arn=dlq_topic.arn,
            depends_on=[dlq_topic],
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
            "example",
            function_name=Token.as_string(resize_lambda_func.function_name),
            maximum_event_age_in_seconds=3600,
            maximum_retry_attempts=0,
        )

        # ✅ Create S3 Buckets for ["images", "resized"]
        # ✅ Create SSM Parameters /localstack-thumbnail-app/buckets/["images", "resized"]
        # ✅ Set S3BucketNotification for images bucket to Trigger resize lambda on "s3:ObjectCreated:*"

        be_buckets = [
            {
                "name": "images",
                "configuration": {
                    "trigger": True,
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
                    depends_on=[bucket],
                    lambda_function=[
                        S3BucketNotificationLambdaFunction(
                            events=["s3:ObjectCreated:*"],
                            lambda_function_arn=bkt["configuration"][
                                "lambda_function_arn"
                            ],
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
