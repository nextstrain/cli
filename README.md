# Nextstrain CLI

This is the source code repository for a program called `nextstrain`, the
Nextstrain command-line interface (CLI).  It aims to provide a consistent way
to run and visualize pathogen builds and access Nextstrain components like
[Augur][] and [Auspice][] across computing environments such as [Docker][],
[Conda][], and [AWS Batch][].

If you're unfamiliar with Nextstrain builds, you may want to follow our
[quickstart guide][] first and then come back here.


[quickstart guide]: https://nextstrain.org/docs/getting-started/quickstart


## Usage

The `nextstrain` program, or command, provides subcommands for building,
viewing, and managing Nextstrain pathogen builds.

For details on installation, [see below](#installation).

```
usage: nextstrain [-h]
                  {build,view,deploy,remote,shell,update,check-setup,version}
                  ...

Nextstrain command-line interface (CLI)

The `nextstrain` program and its subcommands aim to provide a consistent way to
run and visualize pathogen builds and access Nextstrain components like Augur
and Auspice across computing environments such as Docker, Conda, and AWS Batch.

optional arguments:
  -h, --help            show this help message and exit

commands:
  {build,view,deploy,remote,shell,update,check-setup,version}
    build               Run pathogen build
    view                View pathogen build
    deploy              Deploy pathogen build
    remote              Upload, download, and manage Nextstrain files on
                        remote sources.
    shell               Start a new shell in the build environment
    update              Update your local image copy
    check-setup         Test your local setup
    version             Show version information
```

For more information on a specific command, you can run it with the `--help`
option, for example, `nextstrain build --help`.


## Installation

### Python 3.5 or newer

This program is written in Python 3 and requires at least Python 3.5.  There are
many ways to install Python 3 on Windows, macOS, or Linux, including the
[official packages][], [Homebrew][] for macOS, and the [Anaconda
Distribution][].  Details are beyond the scope of this guide, but make sure you
install Python 3.5 or higher.  You may already have Python 3 installed,
especially if you're on Linux.  Check by running `python --version` or `python3
--version`.

[official packages]: https://www.python.org/downloads/
[Homebrew]: https://brew.sh
[Anaconda distribution]: https://www.anaconda.com/distribution/

### nextstrain-cli

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

### Computing environment

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

#### Docker

[Docker][] is a very popular container system freely-available for all
platforms.  When you use Docker with the Nextstrain CLI, you don't need to
install any other Nextstrain software dependencies as validated versions are
already bundled into a container image by the Nextstrain team.

On Windows or a Mac you should download and install [Docker Desktop][] (also
known as "Docker for Mac" and "Docker for Windows").

On Linux, your package manager should include a Docker package.  For example,
on Ubuntu, you can install Docker with `sudo apt install docker.io`.

Once you've installed Docker, proceed with [checking your
setup](#checking-your-setup).

[Docker Desktop]: https://www.docker.com/products/docker-desktop

#### Native

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

#### AWS Batch

[AWS Batch][] is an advanced computing environment which allows you to launch
and monitor Nextstrain builds in the cloud from the comfort of your own
computer.  The same image used by the local Docker runner is used by AWS Batch,
making your builds more reproducible, and builds have access to computers with
very large CPU and memory allocations if necessary.

The initial setup is quite a bit more involved, but [detailed
instructions](docs/aws-batch.md) are available.

Once you've setup AWS, proceed with [checking your
setup](#checking-your-setup).

### Checking your setup

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


## Big picture

The Nextstrain CLI glues together many different components.  Below is [a brief
overview of the big picture](doc/big-picture.svg):

![The Nextstrain CLI glues together many components](doc/big-picture.svg)


## Development

Development of `nextstrain-cli` happens at <https://github.com/nextstrain/cli>.

We currently target compatibility with Python 3.5 and higher.  This may be
increased to 3.6 in the future.

Versions for this project follow the [Semantic Versioning rules][].

### Running with local changes

From within a clone of the git repository you can run `./bin/nextstrain` to
test your local changes without installing them.  (Note that `./bin/nextstrain`
is not the script that gets installed by pip as `nextstrain`; that script is
generated by the `entry_points` configuration in `setup.py`.)

### Releasing

New releases are made frequently and tagged in git using a [_signed_ tag][].
The source and wheel (binary) distributions are uploaded to [the nextstrain-cli
project on PyPi](https://pypi.org/project/nextstrain-cli).

There is a `./devel/release` script which will prepare a new release from your
local repository.  It ends with instructions for you on how to push the release
commit/tag and how to upload the built distributions to PyPi.  You'll need [a
PyPi account][] and [twine][] installed.

### Type annotations and static analysis

Our goal is to gradually add [type annotations][] to our code so that we can
catch errors earlier and be explicit about the interfaces expected and
provided.  Annotation pairs well with the functional approach taken by the
package.

During development you can run static type checks using [mypy][]:

    $ mypy nextstrain
    # No output is good!

There are also many [editor integrations for mypy][].

Note that our goal of compatibility with Python 3.5 means that type comments
are necessary to annotate variable declarations:

    # Not available in Python 3.5:
    foo: int = 3

    # Instead, use trailing type hint comments:
    foo = 3  # type: int

The [`typing_extensions`][] module should be used for features added to the
standard `typings` module after 3.5.  (Currently this isn't necessary since we
don't use those features.)

We also use [Flake8][] for some static analysis checks focusing on runtime
safety and correctness.  You can run them like this:

    $ flake8
    # No output is good!


[Augur]: https://github.com/nextstrain/augur
[Auspice]: https://github.com/nextstrain/auspice
[AWS Batch]: https://aws.amazon.com/batch/
[Docker]: https://docker.com
[Conda]: https://docs.conda.io/en/latest/miniconda.html
[Semantic Versioning rules]: https://semver.org
[_signed_ tag]: https://git-scm.com/book/en/v2/Git-Tools-Signing-Your-Work
[a PyPi account]: https://pypi.org/account/register/
[twine]: https://pypi.org/project/twine
[type annotations]: https://www.python.org/dev/peps/pep-0484/
[mypy]: http://mypy-lang.org/
[editor integrations for mypy]: https://github.com/python/mypy#ide--linter-integrations
[`typing_extensions`]: https://pypi.org/project/typing-extensions
[Flake8]: https://flake8.pycqa.org
