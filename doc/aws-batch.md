# Running Nextstrain builds on AWS Batch

The Nextstrain CLI supports launching pathogen builds on [AWS Batch][] from
your own computer.  No local computational infrastructure is required when
running on AWS Batch, and jobs have access to computers with very large CPU and
memory allocations if necessary.  Some configuration of Batch in your AWS
account is required, but only as an initial, one-time step.  See below for
details.

Launching Nextstrain builds on Batch from your computer is done using the
`--aws-batch` flag to `nextstrain build`, for example:

    nextstrain build --aws-batch zika-tutorial/

This uploads the [`zika-tutorial/` directory][] to S3, submits the
Batch job, monitors the job status, streams the job logs to your terminal, and
downloads build results back to the `zika-tutorial/` directory.

The interface aims to be very similar to that of local builds (either
containerized with Docker or native), so the `nextstrain build` command stays
in the foreground and result files are written back directly to the local build
directory.

[AWS Batch]: https://aws.amazon.com/batch/
[`zika-tutorial/` directory]: https://github.com/nextstrain/zika-tutorial

### Requesting resources

By default AWS Batch jobs request 4 vCPUs and 7200MB of memory. Generally, when
running Snamemake, the `--jobs` option should be matched to the requested number
of vCPUs. These defaults can be overridden by specifying `--aws-batch-cpus` and
`--aws-batch-memory`, for instance `--aws-batch-cpus=8` and
`--aws-batch-memory=14800`.

## Configuration on your computer

### AWS credentials

Your computer must be configured with credentials to access AWS.

Credentials can be provided via the [standard AWS environment variables](https://boto3.readthedocs.io/en/latest/guide/configuration.html#environment-variables)

    export AWS_ACCESS_KEY_ID=...
    export AWS_SECRET_ACCESS_KEY=...

or in the [`~/.aws/credentials` file](https://boto3.readthedocs.io/en/latest/guide/configuration.html#shared-credentials-file)

    [default]
    aws_access_key_id=...
    aws_secret_access_key=...

The credentials file is useful because it does not require you to `export` the
environment variables in every terminal where you want to use AWS.

### AWS region

If you plan to use an AWS region other than `us-east-1`, then you'll want to
set your selected region as a default, either via [the environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#environment-variable-configuration)

    export AWS_DEFAULT_REGION=...

or in the [`~/.aws/config` file](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#configuration-file)

    [default]
    region=...

Again, the latter option is useful because it does not require you to remember
to `export` the environment variable.

### Nextstrain CLI configuration

The Nextstrain CLI's AWS Batch support must be told, at a minimum, the name of
your S3 bucket (which you'll create below).

You can do this by putting your bucket name in an environment variable

    export NEXTSTRAIN_AWS_BATCH_S3_BUCKET=...

or in the `~/.nextstrain/config` file

    [aws-batch]
    s3-bucket = ...

or passing the `--aws-batch-s3-bucket=...` option to `nextstrain build`.

# Setting up AWS to run Nextstrain builds

The rest of this document describes the one-time AWS configuration necessary to
run Nextstrain builds on AWS Batch.  It assumes you have an existing AWS
account and are familiar with the AWS web console.  You'll need to be the AWS
account owner or their delegated administrator to complete these setup tasks.

**You do not need to read this document if you're using someone else's AWS
account and they have already set it up for you to support Nextstrain jobs.**


## S3

Create a new private bucket with a name of your choosing in the [S3 web
console](https://console.aws.amazon.com/s3).  This document will use the name
`nextstrain-jobs`, but you will have to choose something else.  (S3 bucket
names must be globally unique.)

You may set any bucket options you want, but the bucket should be private and
inaccessible to the public (which is the default).

Note that the Nextstrain CLI will **not** remove what it uploaded to the bucket
after each run.  You must add a [lifecycle retention policy][] to the bucket
which expires (deletes) objects 30 days after creation so that you don't
continue to pay for their storage.  You may use a shorter (or longer) lifetime,
but Amazon's prorated billing uses a minimum duration of one month.

[lifecycle retention policy]: https://docs.aws.amazon.com/AmazonS3/latest/user-guide/create-lifecycle.html


## IAM

The easiest place to create the necessary policies, role, and group is the [IAM
web console](https://console.aws.amazon.com/iam).

### Policies

Create three policies using the policy documents below.  You can paste these
into the JSON editor in the web console.

#### NextstrainJobsAccessToBatch

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "batch:DescribeJobQueues",
                "batch:TerminateJob",
                "batch:DescribeJobs",
                "batch:CancelJob",
                "batch:SubmitJob",
                "batch:DescribeJobDefinitions"
            ],
            "Resource": "*"
        }
    ]
}
```

#### NextstrainJobsAccessToBucket

You must replace `nextstrain-jobs` in the policy document below with your own
S3 bucket name.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::nextstrain-jobs/*",
                "arn:aws:s3:::nextstrain-jobs"
            ]
        }
    ]
}
```

#### NextstrainJobsAccessToLogs

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "logs:GetLogEvents",
                "logs:FilterLogEvents",
                "logs:DeleteLogStream"
            ],
            "Resource": [
                "arn:aws:logs:*:*:log-group:/aws/batch/job",
                "arn:aws:logs:*:*:log-group:/aws/batch/job:log-stream:*"
            ]
        }
    ]
}
```

### Roles

A role is required to allow the Batch jobs to access S3.  The code running
inside of each job will have access to this role to talk to AWS services.

When creating the role in the web console, choose _AWS service_ as the type of
trusted entity, the _Elastic Container Service_ as the specific trusted
service, and the _Elastic Container Service Task_ as the use case.  Attach the
_NextstrainJobsAccessToBucket_ policy you created above.  Finally, give the
role a name and description of your choosing.

### Group

If your AWS account will be used by other people to run jobs, you should create
an IAM group to give those users the necessary permissions.

Create a group with a name of your choosing and attach to it all three policies
you created above.  Any users you add to this group will be able to use their
own credentials to launch Nextstrain jobs.


## Batch

If you're not familiar with AWS Batch, first familiarize yourself with [what it
is][], and then use the [getting started guide][] and [AWS Batch wizard][] to
setup the job definition, compute environment, and job queue described below.

[what it is]: https://docs.aws.amazon.com/batch/latest/userguide/what-is-batch.html
[getting started guide]: https://docs.aws.amazon.com/batch/latest/userguide/Batch_GetStarted.html
[AWS Batch wizard]: https://console.aws.amazon.com/batch/home#/wizard

### Job definition

Create a new job definition with the name `nextstrain-job`.  If you use a
different name, you'll need to use the `--aws-batch-job` option to `nextstrain
build`, set the `NEXTSTRAIN_AWS_BATCH_JOB` environment variable, or set `job`
in the `[aws-batch]` section of `~/.nextstrain/config`.

Choose the job role _NextstrainJobsRole_, which you just created in the IAM
roles section above.

Specify the container image `nextstrain/base:latest` and an empty command.
(In the wizard, delete the pre-filled command, leaving the JSON result as an
empty array (`[]`).)

Select the number of desired vCPUs and amount of memory you'd like each
Nextstrain build job to have access to.

Set the retry attempts to _1_ and the execution timeout to _14400_ seconds (4
hours).  The timeout ensures that broken, never-ending jobs will be terminated
after 4 hours instead of racking up EC2 costs.  Adjust it if necessary for your
builds.

No job parameters or job environment variables are required.

### Compute environment

Create a _managed_ compute environment with a name of your choosing.

Adjust the compute resources to meet your build requirements, taking into
account the intensity of your builds and the number of concurrent builds you
expect to run.  The wizard defaults are a reasonable starting point, and you
can adjust many of the resources at a later time.

Make sure to set the minimum number of vCPUs to _0_ so that you won't incur EC2
costs when no jobs are running.

### Job queue

Create a job queue named `nextstrain-job-queue`.  If you use a different name,
you'll need to use the `--aws-batch-queue` option to `nextstrain build`, set
the `NEXTSTRAIN_AWS_BATCH_QUEUE` environment variable, or set `queue` in the
`[aws-batch]` section of `~/.nextstrain/config`.

If you're not using the wizard, make sure you connect the job queue to the
compute environment you created above.


## CloudWatch Logs

AWS Batch jobs automatically send the output of each job to individual log
streams in the `/aws/batch/job` log group.  This log group won't exist until
you run your first Batch job, but you can create it yourself before then.

Note that the Nextstrain CLI will **not** remove the job's log stream after
each run.  You must adjust the [log retention policy][] for the
`/aws/batch/job` log group to expire log events after 30 days so that you don't
continue to pay for their storage.  You may use a shorter (or longer) lifetime,
but Amazon's prorated billing uses a minimum duration of one month.

[log retention policy]: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html#SettingLogRetention


## Security

A full analysis of the security implications of the above configuration depends
on your existing AWS resources and specific use cases.  As such, it is beyond
the scope of this document.

However, there are a few things to keep in mind:

* The policies and configuration are intended to support a **trusted set of
  users working in good faith**.  While the above configuration limits access
  to jobs using IAM policies, it does not prevent job users from interfering
  with each other's jobs if they desire to do so.

* Users who can submit jobs can run arbitrary code on EC2 instances you pay
  for.  They can write arbitrary data to your designated S3 bucket.  Make
  sure you trust your users.  Do not allow public job submission.

* Jobs are given a limited IAM role to access your designated S3 bucket, but
  jobs with malicious intent may be able to elevate their privileges beyond
  that and access other AWS services.  For more details, see the note titled
  "Important" on the ["IAM Roles for Tasks" documentation page][task-iam-roles].
  AWS Batch jobs run in containers using `host`-mode networking, which prevents
  blocking this privilege escalation.

* The Batch compute cluster runs as EC2 instances in a network security group
  with access to your private EC2 subnets.  If you're running other EC2
  instances, you may wish to isolate your Batch cluster in a separate security
  group and subnet.


[task-iam-roles]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html
