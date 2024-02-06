const path = require("path");
const execSync = require("child_process").execSync;

// read env from .env.local (cdktf writes outputs into this file)
const { error } = require("dotenv").config({
  path: path.resolve(__dirname, "..", ".env.local"),
});
if (error) {
  throw error;
}

execSync("awslocal s3 rm s3://$S3_BUCKET_FRONTEND --recursive");
