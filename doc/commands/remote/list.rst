.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain remote list

.. _nextstrain remote list:

======================
nextstrain remote list
======================

.. code-block:: none

    usage: nextstrain remote list <remote-url>
           nextstrain remote list --help


List datasets and narratives on a remote source.
 
A remote source URL specifies what to list, e.g. to list what's in the
Nextstrain Group named "Blab"::

    nextstrain remote list nextstrain.org/groups/blab

or list the core seasonal influenza datasets::

    nextstrain remote list nextstrain.org/flu/seasonal

See :command-reference:`nextstrain remote` for more information on remote sources.

positional arguments
====================



.. option:: <remote-url>

    Remote source URL, with optional path prefix to scope/filter the results

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

