const path = require('path');
const execSync = require('child_process').execSync;

// read env from .env.local (cdktf writes outputs into this file)
const { error } = require('dotenv').config({path: path.resolve(__dirname, '..', '.env.local')});
if (error) {
    throw error;
} 

// use aws cli because it is way better at syncing and there are no good js libraries that can do a s3 sync
execSync('awslocal s3 sync site/ s3://$S3_BUCKET_FRONTEND --delete --acl public-read')
