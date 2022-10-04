# Installation

<!-- XXX TODO: Replace with a ".. hint::" directive when we convert to rST -->
<div class="admonition hint"><p class="admonition-title">Hint</p>

This is a reference page with brief pointers for installing and setting up
Nextstrain CLI.  For a more comprehensive installation guide, please see [our
general Nextstrain installation
page](https://docs.nextstrain.org/page/install.html).

</div>

## Python 3.6 or newer

This program is written in Python 3 and requires at least Python 3.6.  There are
many ways to install Python 3 on Windows, macOS, or Linux, including the
[official packages][], [Homebrew][] for macOS, and the [Anaconda
Distribution][].  Details are beyond the scope of this guide, but make sure you
install Python 3.6 or higher.  You may already have Python 3 installed,
especially if you're on Linux.  Check by running `python --version` or `python3
--version`.

[official packages]: https://www.python.org/downloads/
[Homebrew]: https://brew.sh
[Anaconda distribution]: https://www.anaconda.com/distribution/

## nextstrain-cli

With Python 3 installed, you can use [Pip](https://pip.pypa.io) to install the
[nextstrain-cli package](https://pypi.org/project/nextstrain-cli):

    $ python3 -m pip install nextstrain-cli
    Collecting nextstrain-cli
    […a lot of output…]
    Successfully installed nextstrain-cli-1.16.5

This package also works great with [Pipx](https://pipxproject.github.io/pipx/),
a nice alternative to Pip for command-line apps like this one:

    $ pipx install nextstrain-cli
    Installing to directory '/home/tom/.local/pipx/venvs/nextstrain-cli'
      installed package nextstrain-cli 1.16.5, Python 3.6.9
      These apps are now globally available
        - nextstrain
    done! ✨ 🌟 ✨

Either way you choose, make sure the `nextstrain` command is available after
installation by running `nextstrain version`:

    $ nextstrain version
    nextstrain.cli 1.16.5

The version you get will probably be different than the one shown in the
example above.

## Computing environment

The Nextstrain CLI provides a consistent interface for running and visualizing
Nextstrain pathogen builds across several different computing environments,
such as [Docker][], [Conda][], and [AWS Batch][].  Each computing environment
provides specific versions of Nextstrain's software components and is
responsible for running Nextstrain's programs like [Augur][] and [Auspice][].
For this reason, the different computing environments are called "runners" by
the CLI.

At least one of these computing environments, or runners, must be setup in
order for many of `nextstrain`'s subcommands to work, such as `nextstrain
build` and `nextstrain view`.

The default runner is Docker, using the [nextstrain/base][] container image.
Containers provide a tremendous amount of benefit for scientific workflows by
isolating dependencies and increasing reproducibility.  However, they're not
always appropriate, so a "native" runner is also supported.  The installation
and setup of supported runners is described below.

[nextstrain/base]: https://github.com/nextstrain/docker-base

### Docker

[Docker][] is a very popular container system freely-available for all
platforms.  When you use Docker with the Nextstrain CLI, you don't need to
install any other Nextstrain software dependencies as validated versions are
already bundled into a container image by the Nextstrain team.

On macOS, download and install [Docker Desktop][], also known previously as
"Docker for Mac".

On Linux, install Docker with the standard package manager.  For example, on
Ubuntu, you can install Docker with `sudo apt install docker.io`.

On Windows, there are still significant obstacles to running with Docker, as
documented in [our issue tracking the problems][windows issue].  However, if
you have access to [WSL2][], you should be able to use Docker inside it by
following the Linux install instructions.  Alternatively, you can use the
[native](#native) or [AWS Batch](#aws-batch) runners.

Once you've installed Docker, proceed with [checking your
setup](#checking-your-setup).

[Docker Desktop]: https://www.docker.com/products/docker-desktop
[windows issue]: https://github.com/nextstrain/cli/issues/31
[WSL2]: https://docs.microsoft.com/en-us/windows/wsl/wsl2-index

### Native

The "native" runner allows you to use the Nextstrain CLI without installing
Docker, for cases when you cannot or do not want to use containers.

However, you will need to make sure all of the Nextstrain software dependencies
are available locally or "natively" on your computer.  The easiest and most
common way to do this is by using [Conda][] to install our [Conda
environment](https://github.com/nextstrain/conda#readme), as [documented
here](https://nextstrain.org/docs/getting-started/local-installation).  It is
also possible to install the required Nextstrain software [Augur][] and
[Auspice][] and their dependencies manually, although this is not recommended.

Once you've installed dependencies, proceed with [checking your
setup](#checking-your-setup).

### AWS Batch

[AWS Batch][] is an advanced computing environment which allows you to launch
and monitor Nextstrain builds in the cloud from the comfort of your own
computer.  The same image used by the local Docker runner is used by AWS Batch,
making your builds more reproducible, and builds have access to computers with
very large CPU and memory allocations if necessary.

The initial setup is quite a bit more involved, but [detailed
instructions](aws-batch.md) are available.

Once you've setup AWS, proceed with [checking your
setup](#checking-your-setup).

## Checking your setup

After installation and setup, run `nextstrain check-setup --set-default` to
ensure everything works and automatically pick an appropriate default runner
based on what's available.  You should see output similar to the following:

    $ nextstrain check-setup --set-default
    nextstrain-cli is up to date!

    Testing your setup…

    # docker is supported
    ✔ yes: docker is installed
    ✔ yes: docker run works
    ✔ yes: containers have access to >2 GiB of memory
    ✔ yes: image is new enough for this CLI version

    # native is not supported
    ✔ yes: snakemake is installed
    ✘ no: augur is installed
    ✘ no: auspice is installed

    # aws-batch is not supported
    ✘ no: job description "nextstrain-job" exists
    ✘ no: job queue "nextstrain-job-queue" exists
    ✘ no: S3 bucket "nextstrain-jobs" exists

    All good!  Supported Nextstrain environments: docker

    Setting default environment to docker.

If the output doesn't say "All good!" and list at least one supported
Nextstrain computing environment (typically Docker or native), then something
may be wrong with your installation.

The default is written to the _~/.nextstrain/config_ file.  If multiple
environments are supported, you can override the default for specific runs
using command-line options such as `--docker`, `--native`, and `--aws-batch`,
e.g. `nextstrain build --native …`.


[Augur]: https://github.com/nextstrain/augur
[Auspice]: https://github.com/nextstrain/auspice
[AWS Batch]: https://aws.amazon.com/batch/
[Docker]: https://docker.com
[Conda]: https://docs.conda.io/en/latest/miniconda.html
