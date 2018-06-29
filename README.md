# nextstrain-cli

This is the Nextstrain command-line tool.  It aims to provide access to
Nextstrain components in a local environment with a minimum of fuss.

You can use it to run a pathogen build which makes use of components like
[sacra][], [fauna][], and [augur][] or view the results of such a build in our
standard viewer, [auspice][].


[sacra]: https://github.com/nextstrain/sacra
[fauna]: https://github.com/nextstrain/fauna
[augur]: https://github.com/nextstrain/augur
[auspice]: https://github.com/nextstrain/auspice


## Usage

This package provides a `nextstrain` program which provides access to a few
commands.  If you've installed this package (`nextstrain-cli`), you can just
run `nextstrain`.  Otherwise, you can run `./bin/nextstrain` from a copy of the
source code.

```
usage: nextstrain [-h] {build,view,update,check-setup,version} ...

Nextstrain command-line tool

optional arguments:
  -h, --help            show this help message and exit

commands:
  {build,view,update,check-setup,version}
    build               Run pathogen build
    view                View pathogen build
    update              Updates your local image copy
    check-setup         Tests your local setup
    version             Show version information
```

For more information on a specific command, you can run it with the `--help`
option, for example, `nextstrain build --help`.


## Installation

This tool is written in Python 3 and requires at least Python 3.5.  Currently
it is unpublished on [PyPi][] while still in initial development, but you may
still install the development version with pip (or pip3) like so:

    pip install git+https://github.com/nextstrain/cli

or from a git clone or copy of the source code:

    pip install .

If your system has both Python 2 and Python 3 installed side-by-side, you may
need to use pip3 instead of pip (which often defaults to pip2).

We plan to publish a package on [PyPi][] soon.

This tool also currently requires [Docker][].  You can download and install the
[Docker Community Edition (CE)][] for your platform for free.  After doing so,
run `nextstrain check-setup` to ensure it works.


[PyPi]: https://pypi.org
[Docker]: https://docker.com
[Docker Community Edition (CE)]: https://www.docker.com/community-edition#download
