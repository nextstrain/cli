.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain remote delete

.. _nextstrain remote delete:

========================
nextstrain remote delete
========================

.. code-block:: none

    usage: nextstrain remote delete [--recursively] <remote-url>
           nextstrain remote delete --help


Delete datasets and narratives on a remote source.

A remote source URL specifies what to delete, e.g. to delete the "beta-cov"
dataset in the Nextstrain Group "blab"::

    nextstrain remote delete nextstrain.org/groups/blab/beta-cov

The :option:`--recursively` option allows for deleting multiple datasets or narratives
at once, e.g. to delete all the "ncov/wa/…" datasets in the "blab" group::

    nextstrain remote delete --recursively nextstrain.org/groups/blab/ncov/wa

See :command-reference:`nextstrain remote` for more information on remote sources.

positional arguments
====================



.. option:: <remote-url>

    Remote source URL for a dataset or narrative.  A path prefix to scope/filter by if using :option:`--recursively`.

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

.. option:: --recursively, -r

    Delete everything under the given remote URL path prefix

.. option:: --dry-run

    Don't actually delete anything, just show what would be deleted

