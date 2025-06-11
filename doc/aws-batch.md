# Nextstrain CLI and AWS

## Running Nextstrain builds on AWS Batch

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

The interface aims to be very similar to that of local builds (run in the
Docker, Conda, Singularity, or ambient runtimes), so the `nextstrain build`
command stays in the foreground and result files are written back directly to
the local build directory.  Alternatively, you can specify the `--detach`
option to run AWS Batch builds in the background once they're submitted.  The
Nextstrain CLI will tell you how to reattach to the build later to view the
logs and download the results.  If you forget to use the `--detach` option, you
can press Control-Z to detach at any point once the build is submitted.

[AWS Batch]: https://aws.amazon.com/batch/
[`zika-tutorial/` directory]: https://github.com/nextstrain/zika-tutorial

### Using and requesting resources

By default, each AWS Batch job will have available to it the number of vCPUs
and amount of memory configured in your [job definition](#job-definition).  To
take full advantage of multiple CPUs available, [Snakemake's `--jobs` (or
`-j`)](https://snakemake.readthedocs.io/en/stable/executing/cli.html#all-options)
option should generally be matched to the configured number of vCPUs.  Using
`nextstrain build`'s `--cpus` and `--memory` options will both scale the Batch
instance size and inform Snakemake's resource scheduler for you.

The resources configured in the job definition can be overridden on a per-build
basis using the `--cpus` and/or `--memory` options, for example:

    nextstrain build --aws-batch --cpus=8 --memory=14gib zika-tutorial/

Alternatively, default resource overrides can be set via the
`~/.nextstrain/config` file:

    [aws-batch]
    cpus = ...
    memory = ...

Or via the environment variables `NEXTSTRAIN_AWS_BATCH_CPUS` and
`NEXTSTRAIN_AWS_BATCH_MEMORY`.

When using config or environment variables, however, note that Snakemake's
resource scheduler will not be automatically informed.  This means you should
include `--jobs=…` yourself (and possibly `--resources=mem_mb=…`) as an extra
argument to Snakemake.

Note that requesting more CPUs or memory than available in a compute
environment will result in a job that is queued but is never started.

If requesting c5 instances the following amounts of CPU and memory are
available within the container:

instance type | vCPUs | memory
------------- | ----- | ------
c5-xlarge     | 4     | 7400
c5-2xlarge    | 8     | 15200
c5-4xlarge    | 16    | 31000

Refer to [Compute Resource Memory Management](https://docs.aws.amazon.com/batch/latest/userguide/memory-management.html)
in the AWS Batch User Guide for more detailed information on container memory.

### Configuration on your computer

#### AWS credentials

Your computer must be configured with credentials to access AWS.

Credentials can be provided via the [standard AWS environment variables](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#environment-variables)

    export AWS_ACCESS_KEY_ID=...
    export AWS_SECRET_ACCESS_KEY=...

or in the [`~/.aws/credentials` file](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#shared-credentials-file)

    [default]
    aws_access_key_id=...
    aws_secret_access_key=...

The credentials file is useful because it does not require you to `export` the
environment variables in every terminal where you want to use AWS.

#### AWS region

If you plan to use an AWS region other than `us-east-1`, then you'll want to
set your selected region as a default, either via [the environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables)

    export AWS_DEFAULT_REGION=...

or in the [`~/.aws/config` file](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-a-configuration-file)

    [default]
    region=...

Again, the latter option is useful because it does not require you to remember
to `export` the environment variable.

#### Nextstrain CLI configuration

The Nextstrain CLI's AWS Batch support must be told, at a minimum, the name of
your S3 bucket (which you'll create below).

You can do this by putting your bucket name in an environment variable

    export NEXTSTRAIN_AWS_BATCH_S3_BUCKET=...

or in the `~/.nextstrain/config` file

    [aws-batch]
    s3-bucket = ...

or passing the `--aws-batch-s3-bucket=...` option to `nextstrain build`.

## Setting up AWS to run Nextstrain builds

The rest of this document describes the one-time AWS configuration necessary to
run Nextstrain builds on AWS Batch.  It assumes you have an existing AWS
account and are familiar with the AWS web console.  You'll need to be the AWS
account owner or their delegated administrator to complete these setup tasks.

**You do not need to read this document if you're using someone else's AWS
account and they have already set it up for you to support Nextstrain jobs.**


### S3

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


### IAM

The easiest place to create the necessary policies, role, and group is the [IAM
web console](https://console.aws.amazon.com/iam).

#### Policies

Create three policies using the policy documents below.  You can paste these
into the JSON editor in the web console.

##### NextstrainJobsAccessToBatch

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
                "batch:DescribeJobDefinitions",
                "batch:RegisterJobDefinition"
            ],
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::*:role/NextstrainJobsRole"
        }
    ]
}
```

##### NextstrainJobsAccessToBucket

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

##### NextstrainJobsAccessToLogs

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

#### Roles

A role is required to allow the Batch jobs to access S3.  The code running
inside of each job will have access to this role (via the EC2 instance
metadata) to talk to AWS services.

When creating the role in the web console, choose _AWS service_ as the type of
trusted entity, the _Elastic Container Service_ as the specific trusted
service, and the _Elastic Container Service Task_ as the use case.  Attach the
_NextstrainJobsAccessToBucket_ policy you created above.  Finally, give the
role a name and description of your choosing.  This document assumes the role
 name is _NextstrainJobsRole_.

Most AWS libraries and utilities (e.g. the `aws` command) will automatically
use the instance role by default unless you've customized the credential
provider.  Note that if you have AWS credentials set in environment variables
on the local computer when running `nextstrain build --aws-batch`, then those
will be passed into the job, where they'll be used instead of the role by most
libraries and utilities.  If this is undesirable, you can unset the environment
variables when launching builds or provision your local credentials via the
standard files instead of environment variables.


#### Group

If your AWS account will be used by other people to run jobs, you should create
an IAM group to give those users the necessary permissions.

Create a group with a name of your choosing and attach to it all three policies
you created above.  Any users you add to this group will be able to use their
own credentials to launch Nextstrain jobs.


### Batch

If you're not familiar with AWS Batch, first familiarize yourself with [what it
is][], and then use the [getting started guide][] and [AWS Batch wizard][] to
setup the job definition, compute environment, and job queue described below.

[what it is]: https://docs.aws.amazon.com/batch/latest/userguide/what-is-batch.html
[getting started guide]: https://docs.aws.amazon.com/batch/latest/userguide/Batch_GetStarted.html
[AWS Batch wizard]: https://console.aws.amazon.com/batch/home#/wizard

#### Job and orchestration type

Choose _Amazon Elastic Compute Cloud (Amazon EC2)_ as the orchestration type.

#### Compute environment

Create a _managed_ compute environment with a name of your choosing.

Choose _ecsInstanceRole_ as the instance role.

Adjust the compute resources to meet your build requirements, taking into
account the intensity of your builds and the number of concurrent builds you
expect to run.  The wizard defaults are a reasonable starting point, and you
can adjust many of the resources at a later time.

Make sure to set the minimum number of vCPUs to _0_ so that you won't incur EC2
costs when no jobs are running.

Choose a VPC, subnet, and security group that has access to the internet.

#### Job queue

Create a job queue named `nextstrain-job-queue`.  If you use a different name,
you'll need to use the `--aws-batch-queue` option to `nextstrain build`, set
the `NEXTSTRAIN_AWS_BATCH_QUEUE` environment variable, or set `queue` in the
`[aws-batch]` section of `~/.nextstrain/config`.

If you're not using the wizard, make sure you connect the job queue to the
compute environment you created above.


#### Job definition

Create a new job definition with the name `nextstrain-job`.  If you use a
different name, you'll need to use the `--aws-batch-job` option to `nextstrain
build`, set the `NEXTSTRAIN_AWS_BATCH_JOB` environment variable, or set `job`
in the `[aws-batch]` section of `~/.nextstrain/config`.

Set the execution timeout to _14400_ seconds (4 hours).  The timeout ensures
that broken, never-ending jobs will be terminated after 4 hours instead of
racking up EC2 costs.  Adjust it if necessary for your builds.

Specify the container image `nextstrain/base:latest` and an empty command.
(In the wizard, delete the pre-filled command, leaving the JSON result as an
empty array (`[]`).)

Do not choose any execution role. For the job role, choose _NextstrainJobsRole_
which you just created in the IAM roles section above.

Select the number of desired vCPUs and amount of memory you'd like each
Nextstrain build job to have access to.

No job parameters or job environment variables are required.

### Job

If you're using the wizard, the last step is to submit a job. Give it any name.

### CloudWatch Logs

AWS Batch jobs automatically send the output of each job to individual log
streams in the `/aws/batch/job` log group.  This log group won't exist until
you run your first Batch job, but you can create it yourself before then.

Note that the Nextstrain CLI will **not** remove the job's log stream after
each run.  You must adjust the [log retention policy][] for the
`/aws/batch/job` log group to expire log events after 30 days so that you don't
continue to pay for their storage.  You may use a shorter (or longer) lifetime,
but Amazon's prorated billing uses a minimum duration of one month.

[log retention policy]: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html#SttingLogRetention


### Disk space for your jobs

_The following applies to Batch compute environments using Amazon Linux 2 (AL2)
[ECS-optimized AMIs][], which is the default for new compute environments.  If
you're using older compute environments with Amazon Linux 1 (AL1) AMIs, either
upgrade or see previous versions of this document.  If you're using custom
AMIs, you can probably find your own way._

By default, your Batch jobs will have access to ~28 GiB of shared space.  This
is enough for many Nextstrain builds, but the [SARS-CoV-2 build][] is the
notable exception.  Your own builds may require more disk space as well.

Configuring more space requires a little bit of setup.  It also helps to
understand that Batch uses [ECS][] to run containers on clusters of [EC2][]
servers.

Each EC2 instance in an ECS cluster has, by default, a single **30 GiB** root
volume which is **shared by all the containers/jobs running on that instance**.
The default size of this volume is set by the [AWS-managed ECS-optimized
machine images (AMIs)][ami-storage] used by Batch.  The operating system and
base software is on the same volume, so usable space for your containers/job is
slightly less, around **28 GiB**.

There are several approaches to give your Batch jobs more disk, but the
simplest is to increase the size of the root volume using a custom EC2 _[launch
template][]_ that you associate with a new Batch compute environment.

It's quickest to [create the launch template][create-launch-template] using the
AWS Console, although you can also do it on the command-line.

First, add to the launch template an EBS storage volume with the device name
`/dev/xvda`, volume size you want (e.g. 200 GiB), and a volume type of `gp3`.
Make sure that the volume is marked for deletion on instance termination, or
you'll end up paying for old volumes indefinitely!  This sets the size of the
shared volume available to all containers on a single EC2 instance.

Next, under the "Advanced details" section, make sure that "EBS-optimized
instance" is enabled.

Create the launch template and note its id or name.

Finally, create a new Batch compute environment that uses your launch template
and associate that new compute environment with your Batch job queue.  Note
that you'll need to create a new compute environment even if your existing
compute environment is set to use the `$Latest` version of an existing launch
template you modified as above.  Compute environments set to use the `$Latest`
version of a launch template are frozen to the latest template version that
exists at the time the environment was created, per [AWS Batch
documentation][compute environment launch template].  For this reason, it's
recommended to use an explicit version number instead of `$Latest` so that you
can easily see what version a compute environment is using (instead of having
to correlate compute environment and launch template version creation times).

To check if it worked, create an empty directory on your computer, make a
Snakefile containing the rule below, and run it on AWS Batch using the
Nextstrain CLI:

    rule df:
        shell: "/bin/df -h /"

If all goes well, you should see that the container has access to more space!

#### Alternative: NVMe SSD instance storage

Some EC2 instance families, such as `c5d`, provide host-local NVMe SSD instance
storage devices for a moderate increased cost.  These may be faster and/or
cheaper for your latency, throughput, and IOPS needs.

If you intend to use such instances for your Batch jobs, you'll need to add the
following user data blob to your launch template to configure them:

    Content-Type: multipart/mixed; boundary="==BOUNDARY=="
    MIME-Version: 1.0
    
    --==BOUNDARY==
    Content-Type: text/cloud-boothook; charset="us-ascii"
    
    #!/bin/bash
    # Use the local NVMe instance storage devices for Docker images and containers.
    set -euo pipefail -x
    
    # Only run this whole script once.
    if [[ "${1:-}" != init ]]; then
        exec cloud-init-per once nvme-storage \
            "$0" init
    fi
    
    yum install -y nvme-cli jq lvm2
    
    declare -a instance_devices ebs_devices
    
    instance_devices=($(
        nvme list -o json | jq -r '
              .Devices[]
            | select(.ModelNumber == "Amazon EC2 NVMe Instance Storage")
            | .DevicePath
        '
    ))
    
    ebs_devices=($(
          nvme list -o json \
        | jq -r '
              .Devices[]
            | select(.ModelNumber == "Amazon Elastic Block Store")
            | .DevicePath
        ' \
        | grep -Ff <(
            lsblk --json --path /dev/nvme?n? | jq -r '
                  .blockdevices[]
                | select((.children | length == 0) and (.mountpoint == null))
                | .name
            '
        )
    ))
    
    if [[ ${#instance_devices[@]} -gt 0 || ${#ebs_devices[@]} -gt 0 ]]; then
        # Create VG.  set +u locally to work around Bash 4.2's behaviour with
        # empty arrays (fixed in 4.4).
        (set +u; vgcreate nvme-storage "${instance_devices[@]}" "${ebs_devices[@]}")
    
        # Allow LVM to settle and VG to appear before trying to create LV
        sleep 5
    
        # Create LV for Docker.  Create + extend when both instance and EBS
        # devices are present so that instance devices are allocated PEs (and
        # thus used) first.
        if [[ ${#instance_devices[@]} -gt 0 && ${#ebs_devices[@]} -gt 0 ]]; then
            lvcreate --extents 100%PVS --name docker nvme-storage "${instance_devices[@]}"
            lvextend nvme-storage/docker "${ebs_devices[@]}"
        else
            lvcreate --name nvme-storage/docker --extents 100%VG
        fi
    
        # Format ext4 with zero reserved blocks for root
        mkfs -t ext4 -m 0 /dev/nvme-storage/docker
    
        # Add to fstab so it mounts at subsequent boots
        >>/etc/fstab echo "/dev/nvme-storage/docker /var/lib/docker ext4 defaults 0 0"
    
        # Mount it for this boot
        mount /dev/nvme-storage/docker
    fi
    
    --==BOUNDARY==--

This uses the [cloud-init user data format][] to setup each EC2 instance (ECS
node) on first boot.  Every instance storage device (if any) is added to an LVM
local storage pool, which is then used as the backing disk by Docker.

If instance storage for a given instance size is not quite enough for your jobs
when matching CPU/memory requirements, you can include additional SSD-backed
EBS volumes in your launch template.  These are picked up by the user data
setup above and used only when instance storage is exhausted (or not present).

The ECS documentation includes more information about [specifying options for
the ECS Docker daemon][ecs-docker-options].  If you want to set other options
in your launch template you may, but make sure you understand [Batch's support
for them][batch-launch-template].

#### Alternative: EFS

Using [EFS volumes][] for Batch jobs is enticing as there's no need to predict
required disk sizes, but it's more expensive and has more complex initial setup
considerations.  For example, job definitions must provide EFS volumes to
Docker to be mounted into containers and something must deal with deleting data
which only needs to be ephemeral so as not to incur increasing costs.


[SARS-CoV-2 build]: https://github.com/nextstrain/ncov
[ECS]: https://aws.amazon.com/ecs/
[EC2]: https://aws.amazon.com/ec2/
[ECS-optimized AMIs]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-optimized_AMI.html
[ami-storage]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-optimized_AMI.html
[launch template]: https://docs.aws.amazon.com/batch/latest/userguide/launch-templates.html
[create-launch-template]: https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#LaunchTemplates:
[batch-launch-template]: https://docs.aws.amazon.com/batch/latest/userguide/launch-templates.html
[cloud-init user data format]: https://cloudinit.readthedocs.io/en/latest/topics/format.html
[ecs-docker-options]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/bootstrap_container_instance.html#bootstrap_docker_daemon
[compute environment launch template]: https://docs.aws.amazon.com/batch/latest/userguide/create-compute-environment-managed-ec2.html
[EFS volumes]: https://docs.aws.amazon.com/batch/latest/userguide/efs-volumes.html


### Security

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
