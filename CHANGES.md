This is the changelog for Nextstrain CLI.  All notable changes in a release
will be documented in this file.

This changelog is intended for _humans_ and follows many of the principles from
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

Versions for this project follow the [Semantic Versioning
rules](https://semver.org/spec/v2.0.0.html).  Each heading below is a version
released to [PyPI](https://pypi.org/project/nextstrain-cli/) and the date it
was released.


# 7.1.0 (22 June 2023)

## Improvements

* Commands that use a runtime (`nextstrain build`, `nextstrain shell`, and
  `nextstrain view`) now support two new options for setting or passing thru
  environment variables into the runtime environment:

      --env <name>[=<value>]
      --envdir <path>

  When either of these options are given, the default behaviour of
  automatically passing thru several "well-known" environment variables is
  disabled.  That is, the following "well-known" environment variables are only
  automatically passed thru when the new `--env` and `--envdir` options are
  _not_ used:

    - `AUGUR_RECURSION_LIMIT`
    - `AUGUR_MINIFY_JSON`
    - `AWS_ACCESS_KEY_ID`
    - `AWS_SECRET_ACCESS_KEY`
    - `AWS_SESSION_TOKEN`
    - `ID3C_URL`
    - `ID3C_USERNAME`
    - `ID3C_PASSWORD`
    - `RETHINK_HOST`
    - `RETHINK_AUTH_KEY`

  Pass these variables explicitly via `--env` or `--envdir` if you need them in
  combination with other `--env` or `--envdir` usage.  For more usage details,
  use the `--help-all` flag of any of those commands, e.g. `nextstrain build
  --help-all`.
  ([#289](https://github.com/nextstrain/cli/pull/289))

* Environment variables are now passed to the Docker and AWS Batch runtimes via
  more secure means when the container image in use is new enough to support it
  (`nextstrain/base:build-20230613T204512Z` and newer).  This ensures the env
  values aren't visible in the container's config (e.g. via `docker inspect`,
  `aws batch describe-jobs`, the AWS web console).  If you're using an older
  image, you can update it with `nextstrain update docker`.

  For Docker, environment variables are written to an internal and temporary
  envdir directory visible only to the current user which is deleted
  immediately after use at container start.

  For AWS Batch, environment variables are written to a ZIP archive on S3,
  alongside but separate from the ZIP archive of the build dir.  This env
  archive is deleted from S3 immediately after use at container start.

  Both of these approaches minimize the amount of time environment variable
  values exist outside of memory, persisted to storage (disk, S3).
  ([#289](https://github.com/nextstrain/cli/pull/289))

## Bug fixes

* `nextstrain view` now waits (up to 10s) for Auspice to start responding
  before automatically opening it in the browser.  This should eliminate the
  previous behaviour of sometimes opening the browser too soon.
  ([#291](https://github.com/nextstrain/cli/pull/291))


# 7.0.1 (31 May 2023)

## Bug fixes

* `nextstrain update` for the Conda runtime no longer reports an "invalid
  version" error.  This was a regression introduced in 7.0.0.
  ([#286](https://github.com/nextstrain/cli/pull/286))


# 7.0.0 (26 May 2023)

This release is mostly a bug fix release for our Conda and Singularity
runtimes.  However, it contains a **potentially-breaking change** for existing
usages of the Singularity runtime: **the minimum required Singularity version
has changed from 2.6.0 to 3.0.0**.  This change was required for a critical bug
fix.  If you do not use the Singularity runtime, there are no
potentially-breaking changes in this release.

## Improvements

* `nextstrain shell` now notes which runtime is being entered in its initial
  messaging to establish more context for the user (and for developers when
  troubleshooting).
  ([#283][])

* The Singularity runtime now checks for the minimum required Singularity
  version (3.0.0 with this release) during `nextstrain check-setup`.
  ([#283][])

## Bug fixes

* Setup and upgrade of the Conda runtime now only uses stable "main" channel
  releases when determining the latest release version, as intended.
  Previously, testing and development releases could be selected if they were
  newer than the last stable release.  Additionally, if there are multiple
  builds for a release version, the highest numbered build (i.e. newest) is now
  used instead of the lowest.
  ([#280](https://github.com/nextstrain/cli/pull/280))

* The Singularity runtime now works with our container runtime images from
  `build-20230411T103027Z` onwards.  The Snakemake upgrade in that image
  version resulted in "read-only file system" errors which referenced the
  user's home directory.  Those errors are now fixed.
  ([#283][])

* The prompt for `nextstrain shell`—a stylized variant of the Nextstrain
  wordmark—now works when using the Singularity runtime regardless of
  Singularity version.  Previously Singularity's default prompt of
  `Singularity> ` overrode ours when using Singularity versions ≥3.5.3.
  ([#283][])

* More robust command-line processing is used for the Singularity runtime on
  Singularity versions ≥3.10.0.  Singularity's early (and unexpected)
  evaluation of arguments that look like (but aren't) shell variable
  substitutions is disabled.
  ([#283][])

## Development

* The command lines and environment overrides of many (but not all) process
  invocations are now logged when `NEXTSTRAIN_DEBUG` is enabled.
  ([#283][])


[#283]: https://github.com/nextstrain/cli/pull/283


# 6.2.1 (24 March 2023)

## Bug fixes

* We've fixed and future-proofed a compatibility bug with a third-party library
  that can occur under very specific conditions when `nextstrain build` submits
  AWS Batch jobs.
  ([#261](https://github.com/nextstrain/cli/pull/261))

* The update process for the Conda runtime is now more robust and less likely
  to get stuck at an old version.
  ([#266](https://github.com/nextstrain/cli/pull/266))


# 6.2.0 (28 February 2023)

## Improvements

* `nextstrain build --aws-batch --attach …` no longer offers to cancel (via
  Control-C) or detach (via Control-Z) from the job if it's already complete.
  Instead, Control-C will exit the program without delay and without trying to
  cancel the job.
  ([#253][])

* `nextstrain build` now supports a `--no-logs` option to suppress the fetching
  and printing of job logs when attaching to a completed AWS Batch build.  As
  log fetching can often take longer than a selective download of the results
  (i.e. via `--download`), this is a time (and terminal scrollback) saver when
  all you want are a few of the results files.
  ([#253][])

[#253]: https://github.com/nextstrain/cli/pull/253

## Bug fixes

* An error message that's printed by `nextstrain remote upload` when unknown
  files are given for upload to destinations on nextstrain.org now properly
  includes the actual list of unknown files instead of the placeholder
  `{files}`.
  ([#260](https://github.com/nextstrain/cli/pull/260))

* When running on Python ≥3.10, the `--help` output of `nextstrain build`,
  `nextstrain view`, and `nextstrain shell` once again shows just the most
  common options.  All options are still shown with `--help-all`.  A regression
  since Python 3.10 meant that `--help` acted the same as `--help-all` before
  this fix.  This affected any installation on Python ≥3.10, including
  standalone installations, since the standalone binaries bundle Python 3.10.
  ([#259](https://github.com/nextstrain/cli/pull/259))


# 6.1.0.post1 (18 January 2023)

## Documentation

* Minor improvements to the way we list and describe our computing platforms.


# 6.1.0 (18 January 2023)

## Improvements

* We've added a new Singularity runtime based on our existing Docker runtime.

  Singularity is a container system freely-available for Linux platforms.  It
  is commonly available on institutional HPC systems as an alternative to
  Docker, which is often not supported on such systems.  When you use
  Singularity with the Nextstrain CLI, you don't need to install any other
  Nextstrain software dependencies as validated versions are already bundled
  into a container image by the Nextstrain team.

  Run `nextstrain setup singularity` to get started.
  ([#248](https://github.com/nextstrain/cli/pull/248))


# 6.0.3 (17 January 2023)

## Improvements

* The output of `nextstrain check-setup` for the Conda runtime will now hint
  about running `nextstrain setup conda` first if the runtime seems supported
  but not yet set up.
  ([#250][])

## Documentation

* Documentation and `--help` output now standardizes on the term _runtime_ to
  describe the various ways Nextstrain CLI provides access to the Nextstrain
  software tools.  Previously we used a mix of _build environment_, _runner_,
  and _runtime_ in user-facing messages.  This brings Nextstrain CLI in line
  with the rest of our documentation.
  ([#250][])

* The installation documentation now includes the standalone installer as well
  as installing from Bioconda.  It now covers all the ways our releases are
  distributed.
  ([#250][])

* The output of `nextstrain --help` now notes how to find command-specific
  usage info and our online documentation.
  ([#250][])

* An out-of-date description in `nextstrain build --help` has been revised and
  updated.
  ([#250][])

## Development

* A new [glossary page in our documentation](https://docs.nextstrain.org/projects/cli/page/glossary/)
  will help keep our shared understanding of terms straight.
  ([#250][])

* Links to our online documention in the `--help` output of commands will now
  omit any [local part](https://peps.python.org/pep-0440/#local-version-identifiers),
  e.g. `+git`, of the running CLI version.  This makes links correct even when
  running development builds.
  ([#250][])

[#250]: https://github.com/nextstrain/cli/pull/250


# 6.0.2 (3 January 2023)

_See also changes in 6.0.1 which was an unreleased version._

## Bug fixes

* A new deprecation warning from the `cryptography` module (version 39) when
  running on Python 3.6 is now suppressed as it's just noise to an end user.
  This probably moves us closer to dropping 3.6 support ourselves, but it's not
  so onerous yet.
  ([#246](https://github.com/nextstrain/cli/issues/246))


# 6.0.1 (3 January 2023)

_Unreleased due to [test failures](https://github.com/nextstrain/cli/issues/245). Changes first released as part of 6.0.2._

## Improvements

* The standalone installation archives used by the standalone installer will
  now work on even older Linux distributions:

  |distro       |now    |was    |
  |-------------|-------|-------|
  |Ubuntu       |14\.04 |18\.04 |
  |Debian       |8      |10     |
  |RHEL/CentOS  |7      |8      |
  |Fedora       |19     |28     |
  |OpenSUSE     |12\.3  |15\.3  |

  If you've previously encountered errors like the following:

      /lib64/libc.so.6: version `GLIBC_2.27' not found (required by […]/.nextstrain/cli-standalone/nextstrain)

  when using the standalone installer (or standalone archives directly), i.e.:

      curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/linux | bash

  then this change should resolve that error!  The new minimum required glibc
  version is 2.17 (was 2.27 previously).
  ([#243](https://github.com/nextstrain/cli/pull/243))

## Bug fixes

* The automatic opening of a browser tab (or window) by `nextstrain view`—a
  feature introduced in the last release (6.0.0)—now also works for standalone
  installations.
  ([#244](https://github.com/nextstrain/cli/pull/244))


# 6.0.0 (13 December 2022)

This release contains a **potentially-breaking change** for existing usages of
`nextstrain view`, though we expect the change to impact very few usages.  The
change is described below.

## Improvements

* `nextstrain view` now supports viewing narratives, as was always intended.
  Previously the launched Auspice would either show baked in test narratives or
  no narratives at all, depending on the Auspice version in the runtime.
  ([#240][])

* `nextstrain view` now supports being given more kinds of paths, including
  paths to a specific dataset or narrative file and paths to directories
  containing _auspice/_ and/or _narratives/_ subdirectories.

  This is a **potentially-breaking change**, as `nextstrain view <dir>` will
  now prefer to show datasets from _`<dir>`/auspice/_ if that subdirectory
  exists.  Previously it would only ever look for datasets in the given
  _`<dir>`_.  We expect this to change behaviour for very few usages as it only
  affects situations where _`<dir>`_ contains both datasets and an _auspice/_
  directory.

  See `nextstrain view --help` for more details on the kinds of paths
  supported.
  ([#240][])

* `nextstrain view` now automatically opens Auspice in a new browser tab (or
  window) by default when possible.

  If a specific dataset or narrative file was given as the path to `nextstrain
  view`, then that dataset or narrative is opened.  Otherwise, if there's only
  a single dataset or narrative available in the directory path given to
  `nextstrain view`, then it is opened.  Otherwise, Auspice's listing of
  available datasets and narratives is opened.
  ([#240][])

[#240]: https://github.com/nextstrain/cli/pull/240

* Local images used in a narrative are now automatically embedded into it when
  uploading the narrative to nextstrain.org via `nextstrain remote upload`.
  In local text editors which can render Markdown, this permits previewing of
  narratives that reference images on the local filesystem without requiring
  manual conversion to remote images or embedded images before upload.
  ([#235](https://github.com/nextstrain/cli/pull/235))

* The `nextstrain remote upload` command now outputs a nicer error message
  that's more interpretable and actionable when nextstrain.org returns a "bad
  request" error.  The error message also includes the error details returned
  by nextstrain.org.
  ([#238](https://github.com/nextstrain/cli/pull/238))

## Development

* The Conda runtime now uses Micromamba 1.0.0 (an upgrade from 0.27.0).
  ([#233](https://github.com/nextstrain/cli/pull/233))


# 5.0.1 (1 November 2022)

## Bug fixes

* `nextstrain shell` no longer errors when its history file, e.g.
  _~/.nextstrain/shell-history_, doesn't exist.  This primarily affected the
  Docker runtime and was a regression from 4.2.0 introduced in 5.0.0.
  ([#232](https://github.com/nextstrain/cli/pull/232))


# 5.0.0 (25 October 2022)

_Version 5.0.0 had two development pre-releases (5.0.0.dev0 and 5.0.0.dev1)
prior to final release.  For convenience, the changes from those pre-releases
are also re-described here._

The major improvement in this release is the introduction of a new Conda
runtime, filling a gap between the Docker runtime and the ambient runtime
(formerly "native" runtime).  See more details below.

This release also contains **potentially-breaking changes** for existing
usages of `nextstrain remote download` and `nextstrain update`.  The changes
are described below.

## Improvements

* A new Conda runtime (aka runner or build environment) now complements the
  existing Docker and ambient runtimes and fills a gap between them.  This
  runtime is more isolated and reproducible than your ambient environment, but
  is less isolated and robust than the Docker runtime.  Like the Docker
  runtime, the Conda runtime is fully-managed by Nextstrain CLI and receives
  updates via `nextstrain update`.

  The new runtime uses the [Conda](https://docs.conda.io) ecosystem with
  packages from [our own channel](https://anaconda.org/Nextstrain/nextstrain-base),
  [Bioconda](https://bioconda.github.io/) and
  [Conda-Forge](https://conda-forge.org/), installed by
  [Micromamba](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html)
  into an isolated location, typically `~/.nextstrain/runtimes/conda/env`.  It
  does not interact with or impact other usage of Conda/Mamba environments and
  will not, for example, appear in the output of `conda env list`.

  Set up of the runtime is automated and can be performed by running:

      nextstrain setup conda

  When complete, you'll be able to use the `--conda` runtime option supported
  by Nextstrain CLI commands such as `nextstrain build`, `nextstrain view`,
  `nextstrain shell`, etc.
  ([#218][])

* The "native" runtime (aka runner or build environment) is now the "ambient"
  runtime.  This name better reflects what it is and further distinguishes it
  from the new Conda runtime, which is also "native" in the binary executable
  sense.

  Existing usages of "native" should be unaffected.  The `--native` option
  continues to work anywhere it used to previously, though it is hidden from
  `--help` output to discourage new use.  The string "native" is also accepted
  anywhere runner names are accepted, e.g. in config as the `core.runner`
  setting or in command-line arguments to `check-setup` or `setup`.
  ([#224](https://github.com/nextstrain/cli/pull/224))

* `nextstrain setup docker` now downloads the Docker runtime image if it's not
  already available locally.  This can be a useful initial step after
  installation to avoid the automatic download on first use.
  ([#222](https://github.com/nextstrain/cli/pull/222))

* The local filenames produced by `nextstrain remote download` now include
  more of the remote dataset/narrative path.  This reduces the potential for
  ambiguous filenames and makes it easier to copy datasets/narratives between
  destinations (e.g. from one group to another) while retaining the same path.
  It is, however, a **potentially-breaking change** if you're relying on the
  filenames of the downloaded datasets/narratives (e.g. for automation).

  For example, downloading `nextstrain.org/flu/seasonal/h3n2/ha/2y` previously
  produced the local files:

  ```
  2y.json
  2y_root-sequence.json
  2y_tip-frequencies.json
  ```

  which could easily conflict with the similarly-named
  `nextstrain.org/flu/seasonal/h3n2/na/2y`,
  `nextstrain.org/flu/seasonal/h1n1pdm/ha/2y`, etc.  The downloaded files are
  now named:

  ```
  flu_seasonal_h3n2_ha_2y.json
  flu_seasonal_h3n2_ha_2y_root-sequence.json
  flu_seasonal_h3n2_ha_2y_tip-frequencies.json
  ```

  Within groups, filenames are similarly longer but the group name is not
  included.  For example, downloading `groups/blab/ncov/cross-species/cat`
  previously produced:

  ```
  cat.json
  cat_root-sequence.json
  cat_tip-frequencies.json
  ```

  and now produces:

  ```
  ncov_cross-species_cat.json
  ncov_cross-species_cat_root-sequence.json
  ncov_cross-species_cat_tip-frequencies.json
  ```
  ([#213](https://github.com/nextstrain/cli/pull/213))

* Advanced globbing features are now supported in patterns for the `--download`
  option of `nextstrain build`, including multi-part wildcards (`**`), extended
  globbing (`@(…)`, `+(…)`, etc.), and negation (`!…`).  Basic globbing
  features like single-part wildcards (`*`), character classes (`[…]`), and
  brace expansion (`{…, …}`) are still supported.  Note that the `--download`
  option continues to be applicable only to the AWS Batch runtime (e.g. the
  `--aws-batch` option).
  ([#215](https://github.com/nextstrain/cli/pull/215))

* `check-setup` now accepts one or more runtime names as arguments.

  The default behaviour doesn't change, but specifying runtimes now lets you
  restrict checks to a single runtime or, with multiple runtimes, re-order them
  by your preference for use with --set-default.
  ([#218][])

* `update` now only updates a specific runtime instead of all of them at once.

  With no arguments, the default runtime is updated.  The name of another
  runtime to update instead may be provided as an argument.

  In practice this isn't much of a behaviour change because only one runtime
  currently supports updating (Docker); the others (ambient, AWS Batch) just
  pass.  Existing users are unlikely to notice the change unless they use
  multiple runtimes and Docker is not their default.  In that case, `update`
  may stop updating Docker for them when it would have done so previously,
  which is a **potentially-breaking change**.
  ([#218][])

* A new command, `setup`, now exists to perform automatic set up of runtimes
  that support it (currently only Conda).  For all runtimes, even those that
  don't support automatic set up, the `setup` command will also run the same
  checks as `check-setup` and optionally set the default runtime.
  ([#218][])

* The shell launched by the `shell` command now remembers its own command
  history and differentiates its command prompt from other shells with a
  stylized variant of the Nextstrain wordmark.
  ([#218][])

* The output of commands in dry run mode (e.g. with the `--dry-run` option) is
  now uniformly indicated to be a dry run by the prefix `DRY RUN │ `.  This
  includes the `remote` family of commands and the new `setup` command.
  ([#218][])

* Runtime checks in `check-setup` and `setup` now test for not just the
  presence of Snakemake, Augur, and Auspice, but also that they can be
  executed.
  ([#218][])

## Development

* We now provide standalone installers (i.e. shell programs) to download and
  unpack the standalone installation archives into standard locations,
  potentially upgrading/overwriting a prior standalone install.  These
  installers will be served from GitHub directly out of this project's
  repository via convenience redirects on nextstrain.org.

  These will eventually form the basis for Nextstrain install instructions that
  don't suffer from Python bootstrapping issues.  As a preview for now, you can
  play around with the following platform-specific commands:

      curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/linux | bash
      curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/mac | bash
      Invoke-RestMethod https://nextstrain.org/cli/installer/windows | Invoke-Expression

  A new companion command, `init-shell`, exists to simplify shell configuration
  (i.e. `PATH` modification) for such installations.

* The `NEXTSTRAIN_HOME` environment variable can now be used to specify the
  desired location for per-user settings, files, etc., overriding the default
  of _~/.nextstrain/_.
  ([#218][])

* A new `nextstrain authorization` command makes it easier to generate direct
  requests to nextstrain.org's web API using the same credentials as the CLI.
  ([#229](https://github.com/nextstrain/cli/pull/229))

* The development documentation now documents how to build the documentation
  locally, and sphinx-autobuild is used to make a very nice edit-preview cycle
  with quick turnaround.
  ([#218][])

* Development dependency issues with `flake8` and `sphinx-markdown-tables`,
  caused by upstream changes, are now resolved.
  ([#218][])


# 5.0.0.dev1 (25 October 2022)

_This is the second development pre-release made prior to the final release of 5.0.0._

## Improvements

* The "native" runtime (aka runner or build environment) is now the "ambient"
  runtime.  This name better reflects what it is and further distinguishes it
  from the new Conda runtime, which is also "native" in the binary executable
  sense.

  Existing usages of "native" should be unaffected.  The `--native` option
  continues to work anywhere it used to previously, though it is hidden from
  `--help` output to discourage new use.  The string "native" is also accepted
  anywhere runner names are accepted, e.g. in config as the `core.runner`
  setting or in command-line arguments to `check-setup` or `setup`.
  ([#224](https://github.com/nextstrain/cli/pull/224))

* `nextstrain setup docker` now downloads the Docker runtime image if it's not
  already available locally.  This can be a useful initial step after
  installation to avoid the automatic download on first use.
  ([#222](https://github.com/nextstrain/cli/pull/222))

* `nextstrain build`'s check for use of the `--image` option with unsupported
  runtimes now includes the Conda runtime.
  ([#224](https://github.com/nextstrain/cli/pull/224))

* The Conda runtime now uses the new [`nextstrain-base` Conda
  meta-package](https://anaconda.org/Nextstrain/nextstrain-base) instead of
  using a hardcoded list of packages.

  This decouples Conda runtime updates from Nextstrain CLI updates, as we can
  make new releases of `nextstrain-base` and users can update to those without
  upgrading Nextstrain CLI itself.  This brings the update story for the Conda
  runtime into much better parity with the Docker runtime.

  Using the meta-package also brings increased reproducibility to the runtime,
  as the package completely locks its full transitive dependency tree.  This
  means that if version _X_ of `nextstrain-base` worked in the past, it'll
  still work the same way in the future.

  The `NEXTSTRAIN_CONDA_BASE_PACKAGE` environment variable may be used with
  `nextstrain setup conda` to install a specific version.  The value is a
  [Conda package specification][], e.g. `nextstrain-base ==X`.
  ([#228](https://github.com/nextstrain/cli/pull/228))

* The Conda runtime now uses a pinned version of Micromamba (currently 0.27.0)
  so that new releases of the latter can't break `nextstrain setup conda` or
  `nextstrain update conda` between one day and the next.  The pinned version
  will be bumped up over time as needed with subsequent releases of Nextstrain
  CLI.

  The `NEXTSTRAIN_CONDA_MICROMAMBA_VERSION` environment variable may be used
  with `nextstrain setup conda` to override the built-in pin, either with
  another specific version or `latest`.

[Conda package specification]: https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/pkg-specs.html#package-match-specifications

## Bug fixes

* The Conda runtime now runs Micromamba in greater isolation to avoid undesired
  interactions when a) Nextstrain CLI itself is running inside an
  externally-activated Conda environment and/or b) user-specific Mamba
  configuration exists.  This applies to usages of `nextstrain setup` and
  `nextstrain update` with the Conda runtime.
  ([#223](https://github.com/nextstrain/cli/pull/223))

* The Conda runtime now configures the appropriate channels during `update` too,
  not just during `setup`, ensuring package updates are found.
  ([#228](https://github.com/nextstrain/cli/pull/228))

* The Conda runtime now avoids pinning Python in the isolated environment to
  allow it to be upgraded by `update`.
  ([#228](https://github.com/nextstrain/cli/pull/228))

## Development

* The Conda runtime is now tested in CI, joining the Docker and ambient
  runtimes.
  ([#223](https://github.com/nextstrain/cli/pull/223))


# 5.0.0.dev0 (6 October 2022)

_This is a development pre-release made prior to the final release of 5.0.0._

The major improvement in this release is the introduction of a new Conda
runtime, filling a gap between the Docker runtime and the "native" (soon to be
"ambient") runtime.  See more details below.

This release also contains **a potentially-breaking change** for existing
usages of `nextstrain remote download` and `nextstrain update`.  The changes
are described below.

## Improvements

* A new Conda runtime (aka runner or build environment) now complements the
  existing Docker and "native" runtimes and fills a gap between them.  This
  runtime is more isolated and reproducible than your native ambient
  environment, but is less isolated and robust than the Docker runtime.  Like
  the Docker runtime, the Conda runtime is fully-managed by Nextstrain CLI and
  receives updates via `nextstrain update`.

  The new runtime uses the [Conda](https://docs.conda.io) ecosystem with
  packages from [Bioconda](https://bioconda.github.io/) and
  [Conda-Forge](https://conda-forge.org/), installed by
  [Micromamba](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html)
  into an isolated location, typically `~/.nextstrain/runtimes/conda/env`.  It
  does not interact with or impact other usage of Conda/Mamba environments and
  will not, for example, appear in the output of `conda env list`.

  Set up of the runtime is automated and can be performed by running:

      nextstrain setup conda

  When complete, you'll be able to use the `--conda` runtime option supported
  by Nextstrain CLI commands such as `nextstrain build`, `nextstrain view`,
  `nextstrain shell`, etc.
  ([#218][])

* The local filenames produced by `nextstrain remote download` now include
  more of the remote dataset/narrative path.  This reduces the potential for
  ambiguous filenames and makes it easier to copy datasets/narratives between
  destinations (e.g. from one group to another) while retaining the same path.
  It is, however, a **potentially-breaking change** if you're relying on the
  filenames of the downloaded datasets/narratives (e.g. for automation).

  For example, downloading `nextstrain.org/flu/seasonal/h3n2/ha/2y` previously
  produced the local files:

  ```
  2y.json
  2y_root-sequence.json
  2y_tip-frequencies.json
  ```

  which could easily conflict with the similarly-named
  `nextstrain.org/flu/seasonal/h3n2/na/2y`,
  `nextstrain.org/flu/seasonal/h1n1pdm/ha/2y`, etc.  The downloaded files are
  now named:

  ```
  flu_seasonal_h3n2_ha_2y.json
  flu_seasonal_h3n2_ha_2y_root-sequence.json
  flu_seasonal_h3n2_ha_2y_tip-frequencies.json
  ```

  Within groups, filenames are similarly longer but the group name is not
  included.  For example, downloading `groups/blab/ncov/cross-species/cat`
  previously produced:

  ```
  cat.json
  cat_root-sequence.json
  cat_tip-frequencies.json
  ```

  and now produces:

  ```
  ncov_cross-species_cat.json
  ncov_cross-species_cat_root-sequence.json
  ncov_cross-species_cat_tip-frequencies.json
  ```
  ([#213](https://github.com/nextstrain/cli/pull/213))

* Advanced globbing features are now supported in patterns for the `--download`
  option of `nextstrain build`, including multi-part wildcards (`**`), extended
  globbing (`@(…)`, `+(…)`, etc.), and negation (`!…`).  Basic globbing
  features like single-part wildcards (`*`), character classes (`[…]`), and
  brace expansion (`{…, …}`) are still supported.  Note that the `--download`
  option continues to be applicable only to the AWS Batch runtime (e.g. the
  `--aws-batch` option).
  ([#215](https://github.com/nextstrain/cli/pull/215))

* `check-setup` now accepts one or more runtime names as arguments.

  The default behaviour doesn't change, but specifying runtimes now lets you
  restrict checks to a single runtime or, with multiple runtimes, re-order them
  by your preference for use with --set-default.
  ([#218][])

* `update` now only updates a specific runtime instead of all of them at once.

  With no arguments, the default runtime is updated.  The name of another
  runtime to update instead may be provided as an argument.

  In practice this isn't much of a behaviour change because only one runtime
  currently supports updating (Docker); the others (native, AWS Batch) just
  pass.  Existing users are unlikely to notice the change unless they use
  multiple runtimes and Docker is not their default.  In that case, `update`
  may stop updating Docker for them when it would have done so previously,
  which is a **potentially-breaking change**.
  ([#218][])

* A new command, `setup`, now exists to perform automatic set up of runtimes
  that support it (currently only Conda).  For all runtimes, even those that
  don't support automatic set up, the `setup` command will also run the same
  checks as `check-setup` and optionally set the default runtime.
  ([#218][])

* The shell launched by the `shell` command now remembers its own command
  history and differentiates its command prompt from other shells with a
  stylized variant of the Nextstrain wordmark.
  ([#218][])

* The output of commands in dry run mode (e.g. with the `--dry-run` option) is
  now uniformly indicated to be a dry run by the prefix `DRY RUN │ `.  This
  includes the `remote` family of commands and the new `setup` command.
  ([#218][])

* Runtime checks in `check-setup` and `setup` now test for not just the
  presence of Snakemake, Augur, and Auspice, but also that they can be
  executed.
  ([#218][])

## Development

* We now provide standalone installers (i.e. shell programs) to download and
  unpack the standalone installation archives into standard locations,
  potentially upgrading/overwriting a prior standalone install.  These
  installers will be served from GitHub directly out of this project's
  repository via convenience redirects on nextstrain.org.

  These will eventually form the basis for Nextstrain install instructions that
  don't suffer from Python bootstrapping issues.  As a preview for now, you can
  play around with the following platform-specific commands:

      curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/linux | bash
      curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/mac | bash
      Invoke-RestMethod https://nextstrain.org/cli/installer/windows | Invoke-Expression

  A new companion command, `init-shell`, exists to simplify shell configuration
  (i.e. `PATH` modification) for such installations.

* The `NEXTSTRAIN_HOME` environment variable can now be used to specify the
  desired location for per-user settings, files, etc., overriding the default
  of _~/.nextstrain/_.
  ([#218][])

* The development documentation now documents how to build the documentation
  locally, and sphinx-autobuild is used to make a very nice edit-preview cycle
  with quick turnaround.
  ([#218][])

* Development dependency issues with `flake8` and `sphinx-markdown-tables`,
  caused by upstream changes, are now resolved.
  ([#218][])


[#218]: https://github.com/nextstrain/cli/pull/218


# 4.2.0 (29 July 2022)

## Bug fixes

* Using `remote delete` on nextstrain.org now correctly outputs the "Deleting…"
  message *before* performing each delete, as intended (and as S3 remotes do).
  Previously, the message was misleadingly output *after* each delete was
  already performed.
  ([#209](https://github.com/nextstrain/cli/pull/209))

* Detection of the installation method during self-upgrade checks in
  `nextstrain update` and `nextstrain check-setup` now looks for explicit
  installer metadata files and no longer assumes Pip as the final fallback.  If
  the installation method is not explicitly detected, then no upgrade
  instructions are shown.  Better to suggest nothing than to suggest the wrong
  thing.
  ([#207][])

* An uncaught `StopIteration` error that could have occurred in very specific
  and limited circumstances during self-upgrade checks in `nextstrain update`
  and `nextstrain check-setup` can no longer occur.
  ([#207][])

## Improvements

* The `nextstrain remote download`, `upload`, and `delete` commands now support
  a `--dry-run` mode.

  This mode, as is broader convention, goes through the motions of doing the
  thing, as much as possible, but doesn't _actually_ do the thing.  That is, no
  changes should occur when `--dry-run` is active.

  This is particularly useful for seeing what will happen if you're unsure of
  how a path or argument is handled.  Dry runs of the `list` (`ls`) command
  don't make sense and aren't included.
  ([#210](https://github.com/nextstrain/cli/pull/210))

* Installations via a Conda package are now detected during self-upgrade checks
  and the suggested upgrade command uses `mamba install` or `conda install`.
  ([#207][])

* Suggested upgrade commands now specify the expected new version so they fail
  if that version is not found rather than succeed but do nothing (or do
  something different).
  ([#207][])

## Development

* A new debugging mode can be enabled by setting the `NEXTSTRAIN_DEBUG`
  environment variable to `1` (or another truthy value).  Currently the only
  effect is to print more information about handled (i.e. anticipated) errors.
  For example, stack traces and parent exceptions in an exception chain are
  normally omitted for handled errors, but setting this env var includes them.
  Future debugging and troubleshooting features, like verbose operation
  logging, will likely also condition on this new debugging mode.

* We now avoid a runtime dep on setuptools by switching from
  `pkg_resources.parse_version` to `packaging.version.parse`.  The latter was
  already transitively in our dep tree.
  ([#207][])


[#207]: https://github.com/nextstrain/cli/pull/207


# 4.1.1 (18 July 2022)

## Improvements

* The new version check now links out to the changelog for the latest version
  so you know what you're gonna get.

* The new version check now detects standalone installations and provides
  correct upgrade instructions.

## Development

* The "__NEXT__" heading (and description) is no longer included in the
  _CHANGES.md_ file in release artifacts and tags, as it's a development-only
  section that's always empty in releases.

* The `NEXTSTRAIN_CLI_LATEST_VERSION` environment variable can be set to `0` to
  disable the new version check performed by default during `nextstrain update`
  and `nextstrain check-setup`.  Other values can be provided to override the
  result of querying PyPI for the latest version.

* A new command, `debugger`, was added as a tool to help with troubleshooting
  environment and execution context issues.  The only thing it does is invoke
  pdb from within the command's context.


# 4.1.0 (11 July 2022)

## Improvements

* The `nextstrain remote` family of commands now output a nicer error message
  that's more interpretable and actionable when a server error (HTTP status
  5xx) is received during an operation against the nextstrain.org remote.

* The `nextstrain remote upload` command now outputs a nicer error message
  that's more interpretable and actionable when the connection to the
  nextstrain.org remote server is broken during transfer.

* Timestamps are now shown for each line of output from an AWS Batch build.


# 4.0.0 (24 June 2022)

This release contains **two potentially-breaking changes** for existing usages.
The circumstances and implications of each are described below.

## Improvements

* It is now an error (instead of a warning) to use the `--image` option to
  `nextstrain build` when using the "native" runner (either explicitly via
  `--native` or implicitly via config set by `nextstrain check-setup
  --set-default`).  The error message is:

      The --image option is incompatible with the "native" runner (…).

      If you need to use the "native" runner, please omit the --image option.

      If you need the --image option, please select another runner (e.g.
      with the --docker option) that supports it.  Currently --image is
      supported by the Docker (--docker) and AWS Batch (--aws-batch)
      runners.  You can check if your setup supports these runners with
      `nextstrain check-setup`.

  This is a **potentially-breaking change** as invocations using the "native"
  runner with the `--image` option may exist and be working for users as they
  expect.  If you encounter this new error after upgrading but your results of
  running `nextstrain` commands has always been as-expected, then you can
  safely drop the `--image` option from your invocations and avoid the new
  error.

* When running a Snakemake workflow, `nextstrain build` now defaults
  Snakemake's `--cores` option to `all` unless `build`'s own `--cpus` option is
  provided.  If you provide your own `--cores` (or equivalent, e.g.  `-j`)
  option to Snakemake via `nextstrain build`, as in `nextstrain build .
  --cores 2`, then this new default isn't applicable.

  This is a **potentially-breaking change** if you're…

    - …using Snakemake version 5.10 or earlier (such as via our standard Docker
      runtime image), _and_

    - …are not already providing a `--cores` (or equivalent, e.g. `-j`) option
      to Snakemake via `nextstrain build`, _and_

    - …expect your `nextstrain build` invocations to use only a single CPU/core
      instead of all CPUs/cores available on your computer.

  If this is the case, you can pass `--cpus 1` to `nextstrain build` to regain
  the original behaviour, e.g. `nextstrain build --cpus 1 .`.

  This change will allow upgrading of Snakemake in our Docker runtime image
  without inflicting the addition of `--cores` (or equivalent) arguments onto
  every existing `nextstrain build` invocation that lacks it.

  For context, Snakemake [requires the `--cores` option as of
  5.11](https://github.com/snakemake/snakemake/issues/283).  This has spawned
  much discussion
  ([1](https://github.com/snakemake/snakemake/issues/308),
   [2](https://github.com/snakemake/snakemake/issues/312),
   [3](https://github.com/snakemake/snakemake/issues/450),
   [4](https://github.com/snakemake/snakemake/issues/885))
  where it was made clear this is an intentional, permanent change and a
  default will not be added.  By adding our own default, we can insulate our
  users from the upstream change and make Nextstrain builds fast-by-default.
  Our `--cpus` option can be used to limit CPU usage back from this default if
  necessary, and users can always specify `--cores` (or equivalents)
  themselves.

* The `version --verbose` and `check-setup` commands now indicate the default
  runner in their output, which is useful context when troubleshooting or just
  plain unsure what the default is.

* The `check-setup` command now exits with an error code if the default runner
  is not supported.  Prior to this it only exited with an error code if no
  runners were supported.

## Bug fixes

* When using the AWS Batch runner, the `--cpus` and `--memory` options for
  `build` now correctly override the corresponding resource requests in newer
  style AWS Batch job definitions.  Prior to this they would be ignored by AWS
  Batch.  Older style AWS Batch job definitions were never affected by this and
  continue to work with `--cpus` and `--memory` as expected.  See
  [#144](https://github.com/nextstrain/cli/issues/144) for more details.

* A deprecation warning from the `cryptography` module (version 37 and higher)
  when running on Python 3.6 is now suppressed as it's just noise to an end
  user.  This probably moves us closer to dropping 3.6 support ourselves, but
  it's not so onerous yet.

* The rST to plain text conversion used to format `--help` text was fixed to
  avoid emitting `\r\n` in the wrong context.

* The stdout and stderr streams are now configured at program start to always
  emit UTF-8.  Previously they used the Python defaults, determined in part by
  the system defaults, which often resolved to UTF-8, but not always.  The code
  base assumes UTF-8, and now the streams are guaranteed to match.  In
  particular, this fixes `UnicodeEncodeError` issues in some contexts on
  Windows even when UTF-8 is supported.

## Documentation

* This changelog now sports a preamble to set the scene and provide context for
  the content.

## Development

* The source repo now uses a `+git` local version part to distinguish
  actual releases from installations of unreleased code.  Relatedly, the
  development builds created by CI use a `+git.${commit}` local version part to
  pin down the specific commit from which they were built.  This is mostly
  helpful when reading CI logs or downloading the builds from the CI artifacts.

* The CI workflow has seen some significant sprucing up and additions,
  including sporting a more typical lifecycle with separate steps for build,
  test, and release (a new addition).  The single test step is also now split
  between source tests (unit tests, type checking, linting, etc) and dist tests
  (functional tests, integration tests, interface tests, etc).  The release
  step uploads to PyPI after a release tag is pushed, built, and tested,
  replacing manual uploads from a local development environment.  Various other
  small improvements to CI were also made.

* We now run CI tests on Windows. \o/ It's not perfect, but this should help
  avoid basic Windows-only pitfalls which we might not otherwise notice in a
  timely fashion.

* Our CI now builds (and tests) standalone installation archives (`.tar.gz` for
  Linux and macOS, `.zip` for Windows) comprising of:

    1. A `nextstrain` executable containing a bundled Python interpreter + the
       Python stdlib + the Nextstrain CLI code + its dependencies.

    2. External files (lib, data, etc) that are necessary but can't (for a
       variety of reasons) be bundled into the executable.

  These installation archives can be downloaded, extracted, and run in-place
  without even a Python interpreter being installed on the host computer, hence
  the "standalone" moniker.

  Currently these are for development/testing/experimentation purposes only.
  We include them as assets on GitHub Releases, but do not provide an automated
  means of "installing" or unpacking them; those are ultimate goals, but this
  is just a first step towards those.  If you try out the standalone archives
  in the meantime, though, please let us know how it goes (good or bad) by
  opening an issue with your experience/feedback/questions.

* GitHub Releases are now created by CI after making a release to PyPI.  These
  are visible on the GitHub repo's [releases
  page](https://github.com/nextstrain/cli/releases) and various other places on
  GitHub.  Each GitHub Release includes a copy of the relevant changelog
  section and release assets like the Python distributions and standalone
  installation archives (see above).  Releases on GitHub are currently intended
  mostly for informational and notification purposes; the primary release
  distribution method is still PyPI and sources downstream of PyPI (e.g.
  Conda).


# 3.2.5 (23 May 2022)

## Improvements

* A better error message with a potential remediation is emitted when requests
  to nextstrain.org fail due to stale user tokens.

## Documentation

* The cross-reference to Nextstrain Groups documentation is now up to date with
  the latest Groups docs.


# 3.2.4 (6 April 2022)

## Bug fixes

* `update` will no longer overwrite a `docker.image` config setting when the
  current/default value includes an explicit `latest` tag.  This change makes
  it possible to track the "latest" Docker runtime image by manually setting
  
  ```ini
  [docker]
  image = nextstrain/base:latest
  ```
  
  in _~/.nextstrain/config_.
  ([#163](https://github.com/nextstrain/cli/pull/163))

* `update` now correctly prunes old images starting from and including the
  just-updated-from image, instead of accidentally skipping it until the next
  `update`.
  ([#163](https://github.com/nextstrain/cli/pull/163))

* `check-setup --set-default` now sets the `docker.image` setting to the most
  recent `build-*` image when the Docker runtime is selected as the default.
  ([#168](https://github.com/nextstrain/cli/pull/168))


# 3.2.3 (1 April 2022)

## Bug fixes

* `remote upload` to nextstrain.org destinations is no longer exceedingly slow.
  This was most noticeable for large dataset JSONs.  The slowness was a result
  of poor IO patterns during gzip compression that weren't triggered by S3
  destinations.  Additionally, after benchmarking, the gzip compression level
  was reduced from the max (9) to the default (currently 6) as a better
  compromise between speed and compressed size.
  ([#165](https://github.com/nextstrain/cli/pull/165))


# 3.2.2 (28 March 2022)

## Documentation

* A new page describes how to upgrade Nextstrain CLI.

* The doc page for `nextstrain remote` now links to the pages for its
  subcommands.

* A placeholder in the `nextstrain remote list` command usage now matches the
  placeholder used elsewhere in its `--help` output.


# 3.2.1 (22 March 2022)

## Bug fixes

* `remote upload` no longer gzip compresses files which are already compressed
  when uploading them to an S3 remote.  This isn't expected in typical usage
  when uploading Nextstrain dataset (JSON) or narrative (Markdown) files but
  arises when uploading related files to an S3 remote (e.g. a `metadata.tsv.gz`
  file to `s3://nextstrain-data/files/zika/`).
  ([#161](https://github.com/nextstrain/cli/pull/161))

## Development

* The CI workflow setup steps were simplified a bit.


# 3.2.0 (9 March 2022)

## Bug fixes

* `check-setup` no longer errors when, on some systems, awk outputs a large
  number (bytes of memory reported by /proc/meminfo) in exponential notation.
  ([#159](https://github.com/nextstrain/cli/pull/159))

## Features

* The `view` and `remote` family of commands now support "measurements" dataset
  sidecar files.
  ([#156](https://github.com/nextstrain/cli/pull/156))


# 3.1.1 (4 March 2022)

## Bug fixes

* The Docker runtime now avoids merging stdout and stderr together when at
  least one of stdout or stderr isn't a console (TTY), e.g. when redirecting
  one or both streams to a file or piping output to another command.
  ([#155](https://github.com/nextstrain/cli/pull/155))

* A global lockfile is now used for reading/writing config files instead of
  locking the config files themselves.  This resolves a regression on Windows
  introduced in 3.0.4 which manifested as an `[Errno 13] Permission denied`
  error when running `nextstrain update` and `nextstrain check-setup
  --set-default`.
  ([#157](https://github.com/nextstrain/cli/pull/157))

## Documentation

* The changelog now notes two minor (har har) semantic versioning mistakes in
  previous releases.


# 3.1.0 (1 March 2022)

## Features

* `remote` family of commands now support interacting with nextstrain.org's web
  API using the credentials established by the `login` command.

  See the [nextstrain.org
  remote](https://docs.nextstrain.org/projects/cli/page/remotes/nextstrain.org/)
  documentation for more information.

* `login` now sports a `--renew` flag to request new tokens with refreshed user
  information (e.g. group memberships).

## Bug fixes

* `build` now exits 1 (an error) when the AWS Batch job fails due to
  infrastructural issues like the EC2 instance its running on being terminated.
  Previously it exited 0 (success) despite the job not being successful.

* `check-setup` now supports Docker hosts with cgroups v2 and better handles
  failures in the memory limits check.

* Messages related to automatic login (authn) management are now send to stderr
  instead of stdout.

* `remote delete` messages now correctly imply each deletion is just about to
  happen instead of just happened already.

* The messages produced when an internal error is detected now suggest filing
  an issue on GitHub to report the bug.

## Documentation

* The specific release version will now be displayed under the project name in
  the sidebar of the documentation pages.

## Development

* Many breakages of our CI caused by external changes in upstream testing deps
  are now resolved.


# 3.0.6 (26 January 2022)

## Documentation

* The organization of the documentation sidebar menu is now improved to show
  more of the pages instead of burying them in subpage table of contents.

* The formatting of `--help` output is now slightly improved with regard to
  links, but more importantly, richer formatting of content shared between
  `--help` and the online documentation is now possible.


# 3.0.5 (20 December 2021)

_This release should have bumped the minor version, not the patch version,
since it added a new feature.  —trs, 1 March 2022_

## Features

* `view` now supports a `--host` option to specify the IP address or hostname
  on which to listen, complementing the existing `--port` option.
  `--allow-remote-access` is now an alias for `--host=0.0.0.0`.

## Paper cut remedies

* [netifaces](https://pypi.org/project/netifaces/) is no longer a dependency
  since its lack of wheels for recent Python versions means it often requires a
  C toolchain for installation.  This impacted multiple platforms, including
  Windows and Linux.  For more context, see discussion starting with [this
  issue comment](https://github.com/nextstrain/cli/issues/31#issuecomment-966609539).

  Unfortunately the package no longer has a maintainer, so we can't count on
  any timeline for updates and do not have the resources to maintain it
  ourselves.  Dropping the dep makes the UX of `nextstrain view
  --allow-remote-access` a bit poorer, but makes installation a lot easier.


# 3.0.4 (3 November 2021)

_This release should have bumped the minor version, not the patch version,
since it added new features/commands.  —trs, 1 March 2022_

## Features

* Three new commands—`login`, `logout`, and `whoami`—for authenticating with
  nextstrain.org.  These commands manage tokens stored in
  _~/.nextstrain/secrets_.  No other commands currently use the tokens, but
  future features will start using them, e.g.  for managing datasets and
  narratives on nextstrain.org with the `remote` family of commands.

## Bug fixes

* Adjusted dependencies on s3fs and aiobotocore to avoid incompatible versions
  being selected by pip.

  aiobotocore released a new version, 2.0.0, with breaking changes and pip's
  resolution algorithm chose an older s3fs version which was "compatible" by
  dep declaration by not actually in practice, leading to `nextstrain build
  --aws-batch` throwing errors at runtime.

* update: Explicitly handle errors from the Docker Hub registry.

## Documentation

* AWS Batch: Documented the unintuitive interaction of compute envs and launch
  template versions and updated the disk space section for Amazon Linux 2
  compute environments.

* Updated various links that had moved.

## Development

* Ditched Pipenv for a plain venv setup.

* Dependencies for Read The Docs and CI docs builds are no longer pinned but
  will use the latest versions that otherwise meet standard dep declarations.

* Added pyright tests for additional type checking.  This covers some kinds of
  checks that mypy does not, and in particular lets us use protocol types to
  check the Runner and Remote module interfaces.

* Enabled more mypy checks and resolve findings.

* Tests now treat warnings as errors so we can address them, and CI is now
  warnings clean.

  Python warnings are important to see earlier than later so we can avoid
  spewing warnings to users.

  Sphinx warnings are often authoring mistakes that need to be addressed.


# 3.0.3 (23 February 2021)

## Documentation

* The help output for `build` now correctly describes the default behaviour of
  the `--download` and `--no-download` options.

* The help output for `build` now warns about the need to escape wildcards or
  quote the whole pattern when using `--download` so as to avoid expansion by
  the shell.


# 3.0.2 (16 February 2021)

## Bug fixes

* `update` more gracefully handles Docker not being installed.  Although the
  command still exits with error (as it currently serves only to pull the
  latest Docker image), an uncaught exception isn't thrown.  More improvements
  to come later with [#87](https://github.com/nextstrain/cli/issues/87).

* `version` now gracefully handles Docker not being installed when `--verbose`
  is given instead of throwing an uncaught exception.

* `version` now includes Python information when `--verbose` is given, which is
  helpful for debugging Python issues, e.g. which Python install is being used.

* The Docker (`--docker`) runner for `build`, `shell`, and `view` no longer
  requests a TTY connected to the container when stdin is not itself a TTY
  (e.g. run from a non-interactive shell).  This avoids a fatal error from
  Docker ("the input device is not a TTY").

* Distribution metadata was fixed so that the LICENSE file is no longer
  attempted to be installed under the Python installation prefix (e.g.
  `/usr/local`).  It is instead included inside the "egg-info" directory
  alongside the code in the Python site libraries.

## Development

* Revamp CI by switching from Travis CI to GitHub Actions, expanding the test
  matrix to macOS and Python 3.9, and adding an integration test for the
  "native" build runner.


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
