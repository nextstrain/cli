.. default-role:: literal

.. program:: nextstrain remote

=================
nextstrain remote
=================

.. code-block:: none

    usage: nextstrain remote [-h] {upload,download,list,ls,delete,rm} ...


Upload, download, and manage remote datasets and narratives.

nextstrain.org is the primary remote source/destination for most users, but
Amazon S3 buckets are also supported for some internal use cases.

Remote sources/destinations are specified using URLs starting with
``https://nextstrain.org/`` and ``s3://<bucket-name>/``.  nextstrain.org remote
URLs represent datasets and narratives each as a whole, where datasets may
consist of multiple files (the main JSON file + optional sidecar files) when
uploading/downloading.  Amazon S3 remote URLs represent dataset and narrative
files individually.

For more details on using each remote, see their respective documentation
pages:

    * :doc:`/remotes/nextstrain.org`
    * :doc:`/remotes/s3`

For more information on dataset (Auspice JSON) and narrative (Markdown) files,
see :doc:`docs:reference/data-formats`.

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

commands
========



.. option:: upload

    Upload dataset and narrative files. See :doc:`/commands/remote/upload`.

.. option:: download

    Download dataset and narrative files. See :doc:`/commands/remote/download`.

.. option:: list

    List datasets and narratives. See :doc:`/commands/remote/list`.

.. option:: delete

    Delete dataset and narratives. See :doc:`/commands/remote/delete`.

