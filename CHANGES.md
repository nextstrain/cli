# __NEXT__


# 3.0.1 (12 February 2021)

Hotfix for a missing transitive dependency on s3fs via fsspec, which caused
`nextstrain build --aws-batch` invocations to fail when s3fs was not installed.


# 3.0.0 (11 February 2021)

The minimum Python version for installing the Nextstrain CLI itself is now 3.6.

## Features

* build: Uploads and downloads for remote AWS Batch builds are now streamed
  without the use of temporary local files.  This halves the local storage
  overhead needed and also speeds up the transfer of large builds since:

   1. Uploading can start immediately without first writing the whole archive locally
   2. Unmodified files do not need to be downloaded, just their metadata

* build: The results of remote builds may now be selectively downloaded (or not
  downloaded at all).  Two new `nextstrain build` options are available:

      --download <pattern>
      --no-download

  The former may be given multiple times and specifies patterns to match
  against build dir files which were modified by the remote build.  The
  latter skips downloading results entirely, which is useful if all you
  care about are the logs (such as when re-attaching to a build or when a
  build uploads results itself elsewhere).  The default is still to
  download every modified file.

  Currently this functionality is limited to AWS Batch (`--aws-batch`) builds,
  as it is the only remote environment supported.

## Bug fixes

* build: Python bytecode files (`__pycache__` and `*.pyc`) are no longer
  uploaded or downloaded from remote builds on AWS Batch.

* build: Log messages about individual file uploads/downloads to AWS Batch are
  now printed _before_ each operation, instead _after_, so you can see what
  files are taking a while instead of being in the dark until it completes.

* remote download: A better error message is now produced when a prefix-less
  `s3://` URL is provided without the `--recursively` option.

## Documentation

* Clarify how remote builds on AWS Batch acquire AWS credentials.

* Fix broken links into AWS documentation for boto3.

* Switch to our [Nextstrain theme for
  Sphinx](https://github.com/nextstrain/sphinx-theme)

* Some documentation has been shuffled around to better fit within the larger
  [docs.nextstrain.org](https://docs.nextstrain.org) effort.  Redirects were
  put into place for any moved RTD URLs.

## Development

* Various improvements to the Read The Docs and Sphinx setup.

* Upgrade locked Pipenv development environment.

* Fix type checking failures under newer versions of mypy.



# 2.0.0.post1 (15 June 2020)

## Documentation

* The AWS Batch documentation and 2.0.0 release notes (below) now include
  information about the additional necessity of granting users the ability to
  `iam:PassRole` for the role used by Batch jobs.


# 2.0.0 (2 June 2020)

## Features

* build: The AWS Batch runner now supports overriding the image hardcoded in
  the Batch job definition.  Use the `--image` command-line option, the
  `NEXTSTRAIN_DOCKER_IMAGE` environment variable, or the `docker.image` config
  setting.  This means that both `--docker` and `--aws-batch` builds will now
  use the same container image, increasing reproducibility and customizability.

  This is a **potentially-breaking change**, as it requires your AWS IAM users
  are allowed to perform the `batch:RegisterJobDefinition` action and
  `iam:PassRole` for the your configured job role (typically
  _NextstrainJobsRole_).  The [example _NextstrainJobsAccessToBatch_ IAM
  policy](doc/aws-batch.md#nextstrainjobsaccesstobatch) in the [AWS Batch
  docs](doc/aws-batch.md) is updated to reflect these new privileges.

* build: The new `--cpus` and `--memory` options allow limits to be specified
  for containerized (Docker, AWS Batch) builds.  These both automatically
  inform Snakemake's resource scheduler and the AWS Batch instance size
  selection.  If your builds use Snakemake-based workflows, using these new
  options is better than specifying `--cores …` or `--resources mem_mb=…`
  directly.

* version: Verbose output now includes the "native" versions of Augur and
  Auspice, if available.

## Bug fixes

* view: Auspice v2 dataset JSONs are now detected and included in the list of
  available datasets message printed to the console.

* view: Auspice v1 datasets are now only listed if both the tree and meta JSON
  files exist.  Previously, incomplete datasets with only the tree JSON were
  listed.

## Documentation

* The README now documents known issues with Windows.

## Development

* Pipenv is now used to provide an easier and more consistent development
  environment.

* pytest is now used to run mypy, flake8, and doctests.


# 1.16.7 (20 May 2020)

## Bug fixes

* AWS Batch builds are now more resilient in the face of transient network or
  client errors when uploading the build directory and following build logs.
  Thanks Tony Tung!

# 1.16.6 (20 May 2020)

## Bug fixes

* The previous release did not pass mypy's type checks due to a technicality;
  mypy has now been placated.

## Documentation

* check-setup: Success or failure is (hopefully) more clearly messaged now.
  This was muddied over time by adding support for the native and AWS Batch
  runners, and we've seen several support requests because of confusion here.

* Installation instructions in the README now document all supported computing
  environments, or "runners".  Pipx is also mentioned as a nice alternative to
  Pip.

* Detaching from AWS Batch builds with `--detach` and Control-Z is now
  mentioned in the AWS Batch documentation.

* A direct reference to the AWS Batch User Guide on memory management details
  was added, because AWS docs can be hard to navigate.

* The units documented to be used by the `--aws-batch-memory` option are now
  correct.

* Runner-selection options (`--docker`, `--native`, `--aws-batch`) are now in
  their own option group to reduce clutter among the help output.  They are
  only visible with `--help-all` now, like development options.  With the use
  of `nextstrain check-setup --set-default` now emphasized, these options need
  not be as prominent.

* The top-level description in `nextstrain --help` output now says more than
  three words.  :D

# 1.16.5 (22 April 2020)

## Features

* build: AWS Batch jobs now require Ctrl-C to be pressed twice _within 10s_ to
  cancel a job.  This is an additional guard on top of 1.16.4's change so that
  if you accidentally press Ctrl-C once you can't accidentally press it again
  30 minutes later and ruin your build.

# 1.16.4 (22 April 2020)

## Features

* build: AWS Batch jobs now require Ctrl-C to be pressed twice to cancel the
  job.  This guards a potentially unwanted action from being used accidentally
  by requiring confirmation with a second Ctrl-C.

* build: AWS Batch jobs now report the current job status when re-attaching.
  Previously the current job status was never reported, only the next status
  transition.  For a PENDING or RUNNING job, it might be some time to the next
  transition.

# 1.16.3 (22 April 2020)

## Features

* build: AWS Batch jobs now include more detail about why the container exited
  when available.  This surfaces useful messages like "OutOfMemoryError:
  Container killed due to memory usage" in addition to the exit status.

## Documentation

* check-setup: Describe how `--set-default` chooses an environment. Thanks Mary
  Larrousse!

## Bug fixes

* Fix missing import in our gzip utilities which could cause a runtime error
  (NameError) when running `nextstrain remote download` on S3 objects with a
  `Content-Encoding` header set to a value other than `gzip` or `deflate`.
  This circumstance is unlikely, but not impossible.

## Development

* Use Flake8 for static runtime safety and correctness checks


# 1.16.2 (16 March 2020)

## Bug fixes

* deploy/remote upload: Some files, but not all, were being truncated during
  upload due to a bug in gzip compression handling.  Now the whole file makes
  it to its destination.  More details in
  [#62](https://github.com/nextstrain/cli/pull/63).

* build: The default arguments for `snakemake` are no longer used if a
  different program to run is specified with `--exec`.


# 1.16.1 (25 February 2020)

## Documentation

* Update README to include the latest usage information, which mentions the new
  `remote` command.


# 1.16.0 (25 February 2020)

## Features

* The `deploy` command is now an alias for the `remote upload` command.

* The new `remote list`, `remote download`, and `remote delete` commands allow
  listing, downloading, and deleting remote datasets and narratives which were
  uploaded using `deploy` / `remote upload`.  Currently only direct s3://
  destinations are supported, but its anticipated that Nextstrain Groups will
  be supported as first-class destinations in the future.

## Bug fixes

* deploy/remote upload: Invalid credentials are now properly caught and messaged about.

* deploy/remote upload: Files are now deployed/uploaded using streaming
  compression instead of buffering the whole file in memory first.


# 1.15.0 (18 February 2020)

## Features

* Environment variables for [AWS
  credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#environment-variables)
  (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN`) are
  now passed through to builds.  This lets builds which use data on S3 to work
  transparently, for example.

* Environment variables for [ID3C](https://github.com/seattleflu/id3c)
  (`ID3C_URL`, `ID3C_USERNAME`, and `ID3C_PASSWORD`) are now passed through to
  builds.  This lets Seattle Flu Study builds which use data in an ID3C
  instance to work transparently.


# 1.14.0 (24 September 2019)

_No changes since 1.14.0b1, described below._


# 1.14.0b1 (17 September 2019)

## Features

* The `build` command now supports detaching from and re-attaching to builds
  run on AWS Batch (`--aws-batch`).

  This adds a feature we've wanted from the beginning of the CLI.  By starting
  the build with `--detach`, a remote job is submitted and the command
  necessary to `--attach` to the job later is printed.  This command includes
  the job id and can be used as many times as desired, including while the
  remote job is running or after it has completed.  It will even work on other
  computers or for other people, although you may need to modify the local
  build path to a directory of your choosing.  The directory may be empty, in
  which case all build context will be restored there from the remote job.

  AWS Batch builds may also be interactively detached by pressing Control-Z.
  Normally this would suspend a Unix process (which could then be resumed with
  `fg` or `bg` or SIGCONT), but in the same spirit, `nextstrain build` will
  detach from the remote job instead and exit the local process.  This also
  parallels nicely with our existing Control-C job cancellation support.

  There are currently no facilities to track job state locally or list
  outstanding jobs, but these features may be added later if it seems they'd be
  useful.  As it stands with this new feature, one pattern for launching
  multiple detached jobs and picking them up later is:

      # Loop over several `nextstrain build` commands, appending the last
      # line to a shell script.
      nextstrain build --aws-batch --detach build-a/ | tail -n1 | tee -a pickup-jobs.sh
      nextstrain build --aws-batch --detach build-b/ | tail -n1 | tee -a pickup-jobs.sh
      …

      # Then, sometime later:
      bash pickup-jobs.sh

* The `--aws-batch` runner for the `build` command no longer requires
  permission to perform the globally-scoped AWS IAM action
  `s3:ListAllMyBuckets`.  Instead, it uses the `HEAD <bucket>` S3 API which
  requires either `s3:ListBucket`, which can be scoped to specific buckets in
  IAM grants, or `s3:HeadBucket`, which is globally-scoped but does not reveal
  bucket names.  More details on these IAM actions are in the
  [S3 documentation](https://docs.aws.amazon.com/AmazonS3/latest/dev/using-with-s3-actions.html#using-with-s3-actions-related-to-buckets).


# 1.13.0 (10 September 2019)

## Features

* The `deploy` command no longer requires permission to perform the
  globally-scoped AWS IAM action `s3:ListAllMyBuckets`.  Instead, it uses the
  `HEAD <bucket>` S3 API which requires either `s3:ListBucket`, which can be
  scoped to specific buckets in IAM grants, or `s3:HeadBucket`, which is
  globally-scoped but does not reveal bucket names.  More details on these IAM
  actions are in the [S3 documentation](https://docs.aws.amazon.com/AmazonS3/latest/dev/using-with-s3-actions.html#using-with-s3-actions-related-to-buckets).


# 1.12.0 (5 September 2019)

## Features

* The `deploy` command now supports files other than JSON data files, such as
  Markdown narratives, by setting the correct content type on upload.


# 1.11.2 (3 September 2019)

## Bug fixes

* This release fixes a regression in the `view` command which caused
  "connection reset" or "empty response" errors.  The regression only affected
  versions 1.11.0 and 1.11.1 of the Nextstrain CLI when used with Auspice 1.38.0
  via the `nextstrain/base:build-20190828T223744Z` image.  Thanks to Thomas
  Adams for the excellent bug report!


# 1.11.1 (30 August 2019)

## Bug fixes

* The `check-setup` command no longer errors when Docker isn't installed.


# 1.11.0 (30 August 2019)

## Features

* The `view` command now supports `--native` flag to run in the native ambient
  environment.

* The `check-setup` command now supports a `--set-default` flag to save the
  first supported environment to the Nextstrain CLI's config file.  This means
  that you don't have to specify `--native` (or `--aws-batch`) every time if
  you don't have/want Docker support.

## Bug fixes

* The `--verbose` flag to the `version` command will no longer cause the Docker
  image to be downloaded when it isn't available locally.

## Documentation

* Describe the somewhat annoying process of how to increase the disk space
  available to AWS Batch jobs in the AWS Web Console.


# 1.10.2 (23 August 2019)

## Bug fixes

* The [environment variables used by Augur](https://nextstrain-augur.readthedocs.io/en/stable/envvars.html)
  are now passed through to --docker and --aws-batch builds.


# 1.10.1 (26 March 2019)

## Features

* The `view` command now sports a `--port` option to use an alternate port for
  the viewer.


# 1.10.0 (22 February 2019)

## Features

* Add ability to specify vCPU and memory when running AWS Batch jobs via
  `--aws-batch-cpus` and `--aws-batch-memory` or via specification in
  `~/.nextstrain/config` or via environment variables
  `NEXTSTRAIN_AWS_BATCH_CPUS` and `NEXTSTRAIN_AWS_BATCH_MEMORY`. This requires
  corresponding proper setup of compute environment in AWS Batch console.

# 1.9.1 (11 February 2019)

## Features

* Restore the modification times of files when unzipping results from an AWS
  Batch run.  This allows Snakemake's dependency resolution to properly
  determine file staleness, which in turn allows local builds to continue where
  AWS Batch builds leave off (e.g.  running the bulk of the computation on AWS
  Batch and then iterating on subsequent trivial steps locally).


# 1.9.0 (8 February 2019)

## Features

* Builds run on AWS Batch no longer delete the build dir zip file from S3 or
  the job log stream from CloudWatch, making it easier to debug and
  troubleshoot Batch builds.  The Batch setup documentation is updated to note
  that the previously suggested retention policies are now the only thing
  preventing runaway data storage costs (and thus a must).

## Bug fixes

* Declare missing dep on setuptools, used via `pkg_resources` by the
  `check-setup` and `update` commands.  setuptools nearly always exists already
  on Python installs, especially when nextstrain-cli is installed using pip,
  but nearly always is not always.

## Development

* Static type checking now passes again thanks to a work around for a mypy bug
  related to namespace packages.


# 1.8.1 (21 January 2019)

## Features

* The `check-setup` command now tests if the local Docker image is new enough
  for this version of the CLI.


# 1.8.0 (18 January 2019)

## Bug fixes

* Docker images between `build-20190115T232255Z` and `build-20190116T000613Z`
  (inclusive) broke the `nextstrain view` command.  It is fixed in this version
  of the CLI, 1.8.0, in tandem with new images, starting with
  `build-20190119T045444Z`.  If your `view` command is broken, running
  `nextstrain update` and following the instructions to upgrade to version
  1.8.0 of the CLI should resolve the issue.

* AWS Batch builds now avoid uploading files matching `environment*` in the
  build directory, as such files are commonly used for storing sensitive
  environment values.


# 1.7.3 (28 December 2018)

## Features

* The automatic check for newer versions of the CLI, which happens on the
  `update` and `check-setup` commands, now produces a better,
  more-likely-to-work suggested invocation of pip to perform the upgrade.


# 1.7.2 (28 December 2018)

## Features

* The `build` command now runs `snakemake` with the `--printshellcmds` option
  for improved log output.

## Bug fixes

* User-provided paths are now resolved strictly—they must exist—on both Python
  3.5 and ≥3.6, not just 3.5.  This discrepancy was unlikely to result in any
  noticeable problems because of other existence checks which were performed.
  Nevertheless, the change is good housekeeping and helps ensure robustness.

* The `update` command no longer errors on Python 3.6.0 and 3.6.1 when the
  `~/.nextstrain/` does not exist (for example, when upgrading from CLI
  versions before 1.7.0).  [#37](https://github.com/nextstrain/cli/issues/37)

## Development

* Continuous integration testing now includes a much fuller range of Python
  versions in order to more quickly catch bugs like the one affecting `update`
  above.

* Continuous integration testing switched to running the
  [zika-tutorial](https://github.com/nextstrain/zika-tutorial), a simplified
  build more suitable for our needs.


# 1.7.1 (5 December 2018)

## Bug fixes

* The `shell` command no longer throws an unexpected exception about a missing
  `warn()` function when a non-existent build directory is given.  The
  user-friendly error is printed instead, as expected.


# 1.7.0 (26 November 2018)

## Features

* Builds can now be run remotely on [AWS Batch](https://aws.amazon.com/batch/)
  by passing the `--aws-batch` flag to the `build` command.  See `nextstrain
  build --help` for more information.  Setup required to support this is
  documented in [`doc/aws-batch.md`](doc/aws-batch.md).

* The `update` command now pulls down new images by their `build-*` tag instead
  of tracking the mutable `latest` tag.  Our build tags are, most importantly,
  not updated after creation and thus are suitable references for reproducible
  runs.  The output of `nextstrain version --verbose` now includes the specific
  build tag.

* The `check-setup` command now tests the amount of memory available to
  containers and warns if it less than 2GB.  This is particularly important on
  Windows and macOS where Linux containers are run inside a VM on the host.
  The VM may have limited memory allocated to it, leading to out-of-memory
  errors in builds.

## Documentation

* Installation instructions in the README are now more detailed.

* A big picture overview of where the CLI fits into the Nextstrain ecosystem is
  included in the README for situating newcomers.

* The README now refers to Docker Desktop, the new name for Docker Community
  Edition.


# 1.6.1 (25 September 2018)

## Features

* The `shell` command announces you're entering the build environment, prints
  information about mapped volumes, and describes how to leave the environment.


# 1.6.0 (18 September 2018)

## Bug fixes

* On Windows, fix an issue where the `build` and `shell` commands spawn the
  `docker run` process but also immediately return the user to the
  command-line.  For `shell`, the situation was weirder still because the user
  ended up with _two_ command prompts (cmd.exe and bash) but only one appeared
  to win when reading from the shared stdin.


# 1.5.0 (4 September 2018)

## Features

* The `build` command now supports a `--native` flag to run the build outside
  of any container image, that is, within the ambient environment.  That
  environment might be provided by conda or a cluster module system or custom
  installs or some other thing.  Docker remains the default, although it
  may be explicitly specified with `--docker`.  Other runners are planned for
  the future.  The idea is that the cli as a user-facing tool for Nextstrain is
  separate from a containerized Nextstrain environment (although the two work
  well together).

* The `build`, `view`, and `shell` commands now show an abbreviated set of
  common options when passed `--help`.  The full set of options is available
  using `--help-all`.  The idea is to make the initial output more approachable.

## Development

* The README now describes how to annotate the type of variable and use other
  typing features in a way that's compatible with Python 3.5

* Package metadata for PyPi is slightly improved.


# 1.4.1 (11 August 2018)

## Documentation

* Minor updates to README and command help strings


# 1.4.0 (9 August 2018)

## Features

* A new `shell` command launches an interactive shell (bash) inside the build
  environment, which is useful for running ad-hoc commands and debugging.


# 1.3.0 (9 August 2018)

## Features

* The `update` command now prunes old Docker images after downloading new ones.
  This functionality relies on our new, labeled images.  Older images will have
  to be manually pruned as a one-time step.  See `docker image prune` for more
  information.  Note that locally built images which are tagged
  nextstrain/base:latest will be pruned when `update` is run.  Protect such
  images by giving them an additional tag.

* The versions of the Docker image and individual Nextstrain components in the
  image are shown when the `version` command is run with the `--verbose` flag.


# 1.2.0 (1 August 2018)

## Features

* A new `deploy` command supports uploading data files to S3, allowing the
  complete pathogen build lifecycle to happen using this package.

* The `check-setup` and `update` commands now check if the CLI itself is out of
  date and could be updated.

## Documentation

* Brief descriptions of the changes in each release are now kept in the
  `CHANGES.md` file.  You're reading it!

## Development

* Describe basic development practices for this package in the README.

* Commit to [semantic versioning](https://semver.org), which I'd been
  neglecting previously when bumping versions.

* Static type checking is now supported for a small fraction of the source code
  and runs clean under mypy.  This is included in Travis CI testing.  The goal
  is to add more type annotations going forward.
