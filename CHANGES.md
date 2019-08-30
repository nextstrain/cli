# __NEXT__


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
