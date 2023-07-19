.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain deploy

.. _nextstrain deploy:

=================
nextstrain deploy
=================

.. code-block:: none

    usage: nextstrain deploy [-h] [--dry-run] <remote-url> <file> [<file2> […]] [<file> [<file2> […]] ...]


Upload dataset and narratives files to a remote destination.


The `nextstrain deploy` command is an alias for `nextstrain remote upload`.


A remote destination URL specifies where to upload, e.g. to upload the dataset
files::

    auspice/ncov_local.json
    auspice/ncov_local_root-sequence.json
    auspice/ncov_local_tip-frequencies.json

so they're visible at `https://nextstrain.org/groups/example/ncov`::

    nextstrain remote upload nextstrain.org/groups/example/ncov auspice/ncov_local*.json

If uploading multiple datasets or narratives, uploading to the top-level of a
Nextstrain Group, or uploading to an S3 remote, then the local filenames are
used in combination with any path prefix in the remote source URL.

See :command-reference:`nextstrain remote` for more information on remote sources.

positional arguments
====================



.. option:: <remote-url>

    Remote destination URL for a dataset or narrative.  A path prefix if the files to upload comprise more than one dataset or narrative or the remote is S3.

.. option:: <file> [<file2> […]]

    Files to upload.  Typically dataset and sidecar files (Auspice JSON files) and/or narrative files (Markdown files).

options
=======



.. option:: -h, --help

    show this help message and exit

.. option:: --dry-run

    Don't actually upload anything, just show what would be uploaded

