// DO NOT EDIT. Code generated by 'cdktf convert' - Please report bugs at https://cdk.tf/bug
import { TerraformStack, Token, TerraformOutput} from "cdktf";
import { Construct } from "constructs";
import { AwsProvider } from "../.gen/providers/aws/provider";
import { LocalProvider } from "../.gen/providers/local/provider";
import { ArchiveProvider } from "../.gen/providers/archive/provider"
/*
 * Provider bindings are generated by running `cdktf get`.
 * See https://cdk.tf/provider-generation for more details.
 */
import { DataArchiveFile } from "../.gen/providers/archive/data-archive-file";
import { S3Bucket } from "../.gen/providers/aws/s3-bucket";
import { SnsTopic } from "../.gen/providers/aws/sns-topic";
import { SnsTopicSubscription } from "../.gen/providers/aws/sns-topic-subscription";
import { LambdaFunction } from "../.gen/providers/aws/lambda-function";
import { LambdaFunctionEventInvokeConfig } from "../.gen/providers/aws/lambda-function-event-invoke-config";
import { SsmParameter } from "../.gen/providers/aws/ssm-parameter";
import { S3BucketNotification } from "../.gen/providers/aws/s3-bucket-notification";
import { LambdaFunctionUrl } from "../.gen/providers/aws/lambda-function-url";

export class BackendStack extends TerraformStack {
  constructor(scope: Construct, name: string) {
    super(scope, name);

    const lambda_role: string = "arn:aws:iam::000000000000:role/lambda-role"
    new AwsProvider(this, "aws", { region: "eu-central-1" });
    new LocalProvider(this, "local");
    new ArchiveProvider(this, "archive");

    // Creating dlq topic and subscription for lambda function dlq config
    let dlq_topic = new SnsTopic(this, "failed-resize-topic", {
        name: "failed-resize-topic",
      });
    new SnsTopicSubscription(this, "failed-resize-topic-sub", {
        endpoint: "my-email@example.com",
        protocol: "email",
        topicArn: dlq_topic.arn,
      });

    const resize_asset = new DataArchiveFile(this, "resize_asset", {
        outputPath: "resize_asset.zip",
        sourceFile: "lambda/resize",
        type: "zip",
      });

    let resize_lambda_func = new LambdaFunction(this, "resize_func_lambda", {
        functionName: "resize",
        runtime: "python3.9",
        timeout: 10,
        handler: "handler.handler",
        role: lambda_role,
        filename: resize_asset.outputPath,
        sourceCodeHash: Token.asString(resize_asset.outputBase64Sha256),
      })
    new LambdaFunctionEventInvokeConfig(this, "example", {
        functionName: resize_lambda_func.functionName,
        maximumEventAgeInSeconds:3600,
        maximumRetryAttempts:0
    })

    let be_buckets = [
        {
            "name": "images",
            "configuration": {
                "trigger": true,
                "lambda_function_arn": resize_lambda_func.arn
            }
        },
        {
            "name": "resized", "configuration": {"trigger": false}
        }
    ]

    for (let bkt of be_buckets) {
        let bucket = new S3Bucket(this, `${bkt["name"]}_bucket`, {
            bucket: `localstack-thumbnails-app-${bkt["name"]}`,
          });
        new SsmParameter(this, `${bkt["name"]}_bucket_ssm`, {
            name: `/localstack-thumbnail-app/buckets/${bkt["name"]}`,
            type: "String",
            value: bucket.id,
          });
        if (bkt["configuration"]){
            new S3BucketNotification(this, `${bkt["name"]}_notification`,{
                bucket:bucket.id,
                dependsOn:[bucket],
                lambdaFunction: [
                    {
                        events: ["s3:ObjectCreated:*"],
                        lambdaFunctionArn: bkt["configuration"]["lambda_function_arn"]
                    }
                ]

            })
        }
    }

    let functions: string[] = ["presign", "list"]

    for (let func in functions) {
        let func_asset = new DataArchiveFile(this, `${func}_asset`, {
            outputPath: `${func}_asset.zip`,
            sourceFile: `lambda/${func}`,
            type: "zip",
          });
    
        let lambda_function = new LambdaFunction(this, `${func}_func_lambda`, {
            functionName: func,
            runtime: "python3.9",
            timeout: 10,
            handler: "handler.handler",
            role: lambda_role,
            filename: func_asset.outputPath,
            sourceCodeHash: Token.asString(func_asset.outputBase64Sha256),
          })
        let function_url = new LambdaFunctionUrl(this, `${func}_latest`, {
            functionName:lambda_function.functionName,
            authorizationType: "NONE"
        })
        new LambdaFunctionEventInvokeConfig(this, `${func}_incoke`, {
            functionName: lambda_function.functionName,
            maximumEventAgeInSeconds:3600,
            maximumRetryAttempts:2,
            qualifier:"$LATEST"
        })
        new TerraformOutput(this, `${func}_url`, {
            value:function_url.functionUrl
        })
    }
}}
