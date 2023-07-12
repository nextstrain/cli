:orphan:

.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain init-shell

.. _nextstrain init-shell:

=====================
nextstrain init-shell
=====================

.. code-block:: none

    usage: nextstrain init-shell [-h] [shell]


Prints the shell init script for a Nextstrain CLI standalone installation.

If PATH does not contain the expected installation path, emits an appropriate
``export PATH=…`` statement.  Otherwise, emits only a comment.

Use this command in your shell config with a line like the following::

    eval "$(…/path/to/nextstrain init-shell)"

Exits with error if run in an non-standalone installation.

positional arguments
====================



.. option:: shell

    Shell that's being initialized (e.g. bash, zsh, etc.); currently we always emit POSIX shell syntax but this may change in the future.

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

