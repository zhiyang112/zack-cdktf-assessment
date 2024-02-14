#!/usr/bin/env python
import os
import os.path as Path
from constructs import Construct
from cdktf import App, TerraformStack, TerraformOutput

# providers
from cdktf_cdktf_provider_aws.provider import AwsProvider
from cdktf_cdktf_provider_local.provider import LocalProvider


from cdktf_cdktf_provider_aws.s3_bucket import S3Bucket
from cdktf_cdktf_provider_aws.s3_bucket_public_access_block import (
    S3BucketPublicAccessBlock,
)

from cdktf_cdktf_provider_aws.s3_bucket_website_configuration import (
    S3BucketWebsiteConfiguration,
    S3BucketWebsiteConfigurationIndexDocument,
)

# resources
from cdktf import Token, TerraformStack
from cdktf_cdktf_provider_local.file import File


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
FrontEndStack(app, "iac-assignment-frontend")

app.synth()
