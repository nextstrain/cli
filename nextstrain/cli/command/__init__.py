from . import (
    run,
    build,
    view,
    deploy,
    remote,
    shell,
    update,
    setup,
    check_setup,
    login,
    logout,
    whoami,
    version,
    init_shell,
    authorization,
    debugger,
)

# Maintain this list manually for now while its relatively static.  If we need
# to support pluggable commands or command discovery, we can switch to using
# the "entry points" system:
#    https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins
#
# The order of this list is important and intentional: it determines the order
# in various user interfaces, e.g. `nextstrain --help`.
#
all_commands = [
    run,
    build,
    view,
    deploy,
    remote,
    shell,
    update,
    setup,
    check_setup,
    login,
    logout,
    whoami,
    version,
    init_shell,
    authorization,
    debugger,
]
