========
Runtimes
========

Nextstrain's runtimes are specific :term:`computing environments <computing
environment>` in which Nextstrain CLI expects to find and run other Nextstrain
programs, like :doc:`Augur <augur:index>` and :doc:`Auspice <auspice:index>`.
In turn, Nextstrain CLI provides a consistent set of commands to run and
visualize Nextstrain pathogen builds regardless of the underlying runtime in
use.  Together, this allows Nextstrain to be used across many different
computing platforms and operating systems.

The :doc:`/commands/build`, :doc:`/commands/view`, and :doc:`/commands/shell`
commands all require a runtime, as they require access to other Nextstrain
software.

The :doc:`/commands/setup`, :doc:`/commands/check-setup`, and
:doc:`/commands/update` commands manage the runtimes available for use by the
commands above.  The :doc:`/commands/version` command's :option:`--verbose
<nextstrain version --verbose>` option reports detailed version information
about all available runtimes.

Other Nextstrain CLI commands, such as the :doc:`/commands/remote/index` family
of commands and the related :doc:`/commands/login` and :doc:`/commands/logout`
commands, do not require a runtime.  They may be used without any prior set up
of a runtime.

The runtimes currently available are the:

  - :doc:`/runtimes/docker`
  - :doc:`/runtimes/singularity`
  - :doc:`/runtimes/conda`
  - :doc:`/runtimes/ambient`
  - :doc:`/runtimes/aws-batch`

Runtimes are managed (maintained, tested, versioned, released) by the
Nextstrain team, except for the ambient runtime.  The ambient runtime is
special in that it's whatever computing environment in which Nextstrain CLI
itself is running (that is, it's managed by the user).

You can set up and use multiple runtimes on the same computer, for example if
you want to use them in different contexts.  Runtime-using commands let you
select a different runtime than your default with command-line options (e.g.
``--docker``, ``--conda``, and so on).  For example, you might use the Docker
runtime to run small builds locally and then use the AWS Batch runtime to run
large scale builds with more computing power.

If you pick one runtime and later realize you want to switch, you can go back
and set up the other.


Comparison
==========

.. csv-table::
    :file: comparison.csv
    :header-rows: 1
    :stub-columns: 1

Isolation level
    A relative ranking from least isolated (*none*, 0) to most isolated
    (*great*, 3) from the underlying computer system.

Containerized?
    A containerized :term:`computing platform` provides a higher degree of
    isolation, which in turn usually means a higher degree of portabililty and
    reproducibility across different computers and users.

Locality
    *Local* means "on the same computer where ``nextstrain`` is being run".
    *Remote* means "on a different computer".

    Docker is most often used to run containers locally, but can also be used
    to run them remotely.

External dependencies
    Third-party programs or configuration which are required to use a runtime
    but not managed by :doc:`/commands/setup` and :doc:`/commands/update`.


Compatibility
=============

Switching runtimes or updating the version of a runtime may result in different
versions of Nextstrain components like Augur and Auspice as well as other
programs, and thus different behaviour.  Use the :doc:`/commands/version`
command's :option:`--verbose <nextstrain version --verbose>` option to report
detailed version information about all available runtimes.

Exact behavioural compatibility is not guaranteed between different runtimes
(e.g. between the Docker vs. Conda runtimes) or between versions of the same
runtime (e.g. between Docker runtime images
``nextstrain/base:build-20230714T205715Z`` and
``nextstrain/base:build-20230720T001758Z``).  However, the containerized
runtimes (Docker, Singularity, AWS Batch; see comparison_ above) will usually
have identical behaviour given the same runtime version (e.g. ``build-…``) as
they are all based the same runtime image (``nextstrain/base``).  Any variance
is typically due to use of external resources (intentional or otherwise) from
outside the container.
