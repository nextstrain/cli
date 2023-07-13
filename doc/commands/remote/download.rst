.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain remote download

.. _nextstrain remote download:

==========================
nextstrain remote download
==========================

.. code-block:: none

    usage: nextstrain remote download <remote-url> [<local-path>]
           nextstrain remote download --recursively <remote-url> [<local-directory>]
           nextstrain remote download --help


Download datasets and narratives from a remote source.
 
A remote source URL specifies what to download, e.g. to download one of the
seasonal influenza datasets::

    nextstrain remote download nextstrain.org/flu/seasonal/h3n2/ha/2y

which creates three files in the current directory::

    flu_seasonal_h3n2_ha_2y.json
    flu_seasonal_h3n2_ha_2y_root-sequence.json
    flu_seasonal_h3n2_ha_2y_tip-frequencies.json

The --recursively option allows for downloading multiple datasets or narratives
at once, e.g. to download all the datasets under "ncov/open/…" into an existing
directory named "sars-cov-2"::

    nextstrain remote download --recursively nextstrain.org/ncov/open sars-cov-2/

which creates files for each dataset::

    sars-cov-2/ncov_open_global.json
    sars-cov-2/ncov_open_global_root-sequence.json
    sars-cov-2/ncov_open_global_tip-frequencies.json
    sars-cov-2/ncov_open_africa.json
    sars-cov-2/ncov_open_africa_root-sequence.json
    sars-cov-2/ncov_open_africa_tip-frequencies.json
    …

See :command-reference:`nextstrain remote` for more information on remote sources.

positional arguments
====================



.. option:: <remote-url>

    Remote source URL for a dataset or narrative.  A path prefix to scope/filter by if using --recursively.

.. option:: <local-path>

    Local directory to save files in.  May be a local filename to use if not using --recursively.  Defaults to current directory (".").

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

.. option:: --recursively, -r

    Download everything under the given remote URL path prefix

.. option:: --dry-run

    Don't actually download anything, just show what would be downloaded

