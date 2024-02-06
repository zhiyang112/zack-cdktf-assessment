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

# resources
from cdktf_cdktf_provider_local.file import File
from cdktf_cdktf_provider_aws.lambda_function import LambdaFunction, LambdaFunctionEnvironment, LambdaFunctionDeadLetterConfig
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
    os_name = os.uname().sysname
    
    # ref https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies
    if os_name == "Darwin":
        # MacOS specific commands
        commands = [
            "rm -rf libs",
            'docker run --platform linux/x86_64 -v "$PWD":/var/task public.ecr.aws/sam/build-python3.9 /bin/sh -c "pip install -r requirements.txt -t libs; exit"',
        ]
    else:
        # Other OS (assuming Linux) specific commands
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

        # TODO: Create S3 Buckets for ["images", "resized"]

        # TODO: Create SSM Parameters /localstack-thumbnail-app/buckets/["images", "resized"]

        # TODO: Create failed-resize SNS Topic and SNS Topic Subscription (email protocol)

        # build lambdas/resize/libs folder
        # reference https://developer.hashicorp.com/terraform/cdktf/concepts/assets
        lambda_libs("lambdas/resize")
        resize_asset = TerraformAsset(self, "resize_asset",
            path = Path.join(os.getcwd(), "lambdas/resize"),
            type = AssetType.ARCHIVE,
        )

        # TODO: Create Lambda functions for resize, list and presign handlers
        
        # TODO: Set resize lambda's dead_letter_config to failed-resize SNS Topic
        
        # TODO: Set LambdaFunctionEventInvokeConfig

        # TODO: Set S3BucketNotification for images bucket to Trigger resize lambda on "s3:ObjectCreated:*"
        
        functions=["presign", "list"]
        for function_name in functions:
            asset = TerraformAsset(self, f"{function_name}_asset",
                path = Path.join(os.getcwd(), f"lambdas/{function_name}"),
                type = AssetType.ARCHIVE,
            )
            lambda_function = LambdaFunction(self, f"{function_name}_lambda",
                function_name = function_name,
                runtime = "python3.9",
                timeout = 10,
                handler = "handler.handler",
                role = lambda_role,
                filename = asset.path,
                source_code_hash = asset.asset_hash,
                environment =  LambdaFunctionEnvironment(
                    variables = {"STAGE":"local"}
                )
            )
            function_url = LambdaFunctionUrl(self, f"{function_name}_latest",
                function_name=lambda_function.function_name,
                authorization_type="NONE"
            )
            TerraformOutput(self, f"{function_name}_url",
                value = function_url.function_url,
            )

class FrontEndStack(TerraformStack):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)

        AwsProvider(self, "Aws")
        LocalProvider(self, "local")

        # TODO: Create S3 Buckets for "webapp"

        # TODO: Set S3BucketWebsiteConfiguration and s3 policy for PulblicRead

        # Write dotenv config for website deploy script
        File(self, "env",
            filename = Path.join(os.getcwd(), "website", ".env.local"),
            content = f"S3_BUCKET_FRONTEND={bucket.bucket}"
        )

        # output bucket Name
        TerraformOutput(self, "localstack_url",
            value = f"http://{bucket.bucket}.s3-website.localhost.localstack.cloud:4566",
        )

app = App()
BackendStack(app, "iac-assignment-backend")
FrontEndStack(app, "iac-assignment-frontend")

app.synth()
