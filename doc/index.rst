==============
Nextstrain CLI
==============

.. hint::
   This is reference documentation for the Nextstrain CLI (command-line
   interface).  If you're just getting started with Nextstrain, please see
   :doc:`our general documentation <docs:index>` instead.

The Nextstrain CLI is a program called ``nextstrain``.  It aims to provide a
consistent way to run and visualize pathogen builds and access Nextstrain
components like :doc:`Augur <augur:index>` and :doc:`Auspice <auspice:index>`
across computing environments such as `Docker <https://docker.com>`__, `Conda
<https://docs.conda.io/en/latest/miniconda.html>`__, and `AWS Batch
<https://aws.amazon.com/batch/>`__.

.. note::
    If you're unfamiliar with Nextstrain builds, you may want to follow our
    :doc:`docs:tutorials/running-a-workflow` tutorial first and then come back
    here.


Table of Contents
=================

.. toctree::
    :maxdepth: 3

    Introduction <self>
    installation
    AWS Batch <aws-batch>

.. toctree::
    :caption: Commands
    :name: commands
    :titlesonly:
    :maxdepth: 3

    commands/build
    commands/view
    commands/deploy
    commands/remote/index
    commands/remote/list
    commands/remote/download
    commands/remote/upload
    commands/remote/delete
    commands/shell
    commands/update
    commands/check-setup
    commands/login
    commands/logout
    commands/whoami
    commands/version

.. toctree::
    :caption: Remotes
    :titlesonly:

    nextstrain.org <remotes/nextstrain.org>
    Amazon S3 <remotes/s3>


Big Picture
===========

.. XXX TODO: Move this into our explanatory doc pages when they're written.

The Nextstrain CLI glues together many different components.  Below is a brief
overview of the `big picture <_static/big-picture.svg>`__:

.. image:: _static/big-picture.svg
    :target: _static/big-picture.svg


Indices and Tables
==================

* :ref:`genindex`
* :ref:`search`
