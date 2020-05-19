# nextstrain-cli

This is the Nextstrain command-line tool.  It aims to provide access to
Nextstrain components in a local environment with a minimum of fuss.

You can use it to run a pathogen build which makes use of components like
[sacra][], [fauna][], and [augur][] or view the results of such a build in our
standard viewer, [auspice][].

If you're unfamiliar with Nextstrain builds, you may want to follow our
[quickstart guide][] first and then come back here.


[sacra]: https://github.com/nextstrain/sacra
[fauna]: https://github.com/nextstrain/fauna
[augur]: https://github.com/nextstrain/augur
[auspice]: https://github.com/nextstrain/auspice
[quickstart guide]: https://nextstrain.org/docs/getting-started/quickstart


## Usage

This package provides a `nextstrain` program which provides access to a few
commands.  If you've installed this package (`nextstrain-cli`), you can just
run `nextstrain`.  Otherwise, you can run `./bin/nextstrain` from a copy of the
source code.

```
usage: nextstrain [-h]
                  {build,view,deploy,remote,shell,update,check-setup,version}
                  ...

Nextstrain command-line tool

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

This tool is written in Python 3 and requires at least Python 3.5.  There are
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

With Python 3 installed, you can use [pip](https://pip.pypa.io) to install the
[nextstrain-cli package](https://pypi.org/project/nextstrain-cli):

    $ python3 -m pip install nextstrain-cli
    Collecting nextstrain-cli
    […a lot of output…]
    Successfully installed nextstrain-cli-1.6.1

After installation, make sure the `nextstrain` command works by running
`nextstrain version`:

    $ nextstrain version
    nextstrain.cli 1.6.1

The version you get will probably be different than the one shown in the
example above.

### Docker

This tool also currently requires [Docker][], which is freely available.  On
Windows or a Mac you should download and install [Docker Desktop][] (also known
as "Docker for Mac" and "Docker for Windows").  On Linux, your package manager
should include a Docker package.

[Docker]: https://docker.com
[Docker Desktop]: https://www.docker.com/products/docker-desktop

After installing Docker, run `nextstrain check-setup` to ensure it works:

    $ nextstrain check-setup
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

If the output doesn't say "All good!" and list at least one supported
Nextstrain environment (typically Docker or native), then something may be
wrong with your installation.


## Big picture

The Nextstrain CLI glues together many different components with an easy-to-use
interface that doesn't require a lot of fussing.  Below is [a brief overview of
the big picture](doc/big-picture.svg):

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


[Semantic Versioning rules]: https://semver.org
[_signed_ tag]: https://git-scm.com/book/en/v2/Git-Tools-Signing-Your-Work
[a PyPi account]: https://pypi.org/account/register/
[twine]: https://pypi.org/project/twine
[type annotations]: https://www.python.org/dev/peps/pep-0484/
[mypy]: http://mypy-lang.org/
[editor integrations for mypy]: https://github.com/python/mypy#ide--linter-integrations
[`typing_extensions`]: https://pypi.org/project/typing-extensions
[Flake8]: https://flake8.pycqa.org
