## Welcome to Nextstrain CLI Development
For more general intofrmation on contributing to Nextstrain, please see [the contribution documentation here.](https://nextstrain.org/docs/contributing/philosophy)

## Setting up Nextstrain CLI for development
This document outlines how to use your system's python to develop the CLI. If you are familiar with virtual environments, you may also use them but they are not currently covered here.

### Python Installation
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

### Update Pip
Ensure pip (Package Installer for Python) is up to date. Pip is automatically installed with Python 3.5 or greater.

Linux or macOS:

```pip install -U pip```

Windows:

```python -m pip install -U pip```

### Install Required Dependencies
Run pip to install the required dependencies found in setup.py.

```pip install .```

### Running Local Changes
With the dependencies in place, you can now run `./bin/nextstrain` to run with your local changes without installing them.

### Installing Nextstrain CLI from source
If you need to or wish to install from source, so that you can run your local changes with `nextstrain` rather than `./bin/nextstrain`, you can run the following:

```pip install .```
