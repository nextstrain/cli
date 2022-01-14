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

.. toctree::
    :caption: Table of Contents
    :titlesonly:

    Introduction <self>
    installation
    commands/index
    aws-batch


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
