# This file defines how PyOxidizer application building and packaging is
# performed.  See PyOxidizer's documentation for details of this configuration
# file format:
#
#   https://pyoxidizer.readthedocs.io/en/stable/pyoxidizer_getting_started.html#the-pyoxidizer-bzl-configuration-file
#
# The short overview is that it's not-quite-Python but a subset called
# Starlark.
#
# The following variable can be controlled via --var or --var-env.
#
# NEXTSTRAIN_CLI_DIST
#    Specifies a pre-built dist to use for packaging Nextstrain CLI (e.g.
#    dist/nextstrain_cli-*-py3-none-any.whl) instead of packaging from the
#    source dir.
#
NEXTSTRAIN_CLI_DIST = VARS.get("NEXTSTRAIN_CLI_DIST", ".")


# Define how to bundle a Python interpreter + our Python code + shared
# libraries + other resources into a single executable + an adjacent filesystem
# "lib/" tree.
def make_exe():
    # Obtain the default PythonDistribution for our build target.  We link this
    # distribution into our produced executable and extract the Python standard
    # library from it.
    python_dist = default_python_distribution()

    # This function creates a `PythonPackagingPolicy` instance, which
    # influences how executables are built and how resources are added to the
    # executable.  You can customize the default behavior by assigning to
    # attributes and calling functions.
    packaging_policy = python_dist.make_python_packaging_policy()

    # Emit both classified resources (PythonModuleSource, etc) and unclassified
    # "File" resources, but only include the former in packaging by default.
    # Allow "File" resource to be explicitly added on a case-by-case basis.
    # See also our exe_resource_policy_decision() and the PyOxidizer docs.¹
    #
    # ¹ https://pyoxidizer.readthedocs.io/en/stable/pyoxidizer_config_type_python_packaging_policy.html
    packaging_policy.file_scanner_classify_files = True
    packaging_policy.file_scanner_emit_files = True
    packaging_policy.include_classified_resources = True
    packaging_policy.include_file_resources = False
    packaging_policy.allow_files = True

    # Embed included resources in the executable by default when possible (e.g.
    # pure Python modules and data files).  When not possible (e.g. compiled
    # extension modules) place them on the filesystem in a "lib/" directory
    # adjacent to the executable.
    packaging_policy.resources_location = "in-memory"
    packaging_policy.resources_location_fallback = "filesystem-relative:lib"

    # Invoke a function to make additional packaging decisions for each emitted
    # resource.
    packaging_policy.register_resource_callback(exe_resource_policy_decision)

    # Configuration of the embedded Python interpreter.  Setting run_module is
    # equivalent to `python -m nextstrain.cli …`.
    python_config = python_dist.make_python_interpreter_config()
    python_config.run_module = "nextstrain.cli"

    # Equivalent to: -Xnextstrain-cli-is-standalone, which we use to know if
    # we're in a standalone installation or not at runtime.
    python_config.x_options = ["nextstrain-cli-is-standalone"]

    # Produce a PythonExecutable from a Python distribution, embedded
    # resources, and other options. The returned object represents the
    # standalone executable that will be built.
    exe = python_dist.to_python_executable(
        name = "nextstrain",
        packaging_policy = packaging_policy,
        config = python_config)

    # Invoke `pip install` with our Python distribution to install Nextstrain
    # CLI from source.
    #
    # `pip_install()` returns objects representing installed files.
    # `add_python_resources()` adds these objects to the binary, with a load
    # location as defined by the packaging policy's resource location
    # attributes.
    exe.add_python_resources(exe.pip_install([NEXTSTRAIN_CLI_DIST]))

    # For Windows, always bundle the required Visual C++ Redistributable DLLs
    # alongside the binary.¹  If they can't be found on the build machine, the
    # build will error rather than produce a build that's missing these
    # required DLLs.
    #
    # ¹ https://pyoxidizer.readthedocs.io/en/stable/pyoxidizer_distributing_windows.html#installing-the-visual-c-redistributable-files-locally-next-to-your-binary
    #
    # XXX TODO: Check the licensing requirements of the DLLs this bundles.
    # They're meant to be redistributed—it's in the name!—and I believe are
    # even provided for download by the general public, but under what terms?
    #   -trs, 1 June 2022
    exe.windows_runtime_dlls_mode = "always"

    return exe


def exe_resource_policy_decision(policy, resource):
    # Some pure Python packages use __file__ to locate their resources (instead
    # of the importlib APIs) and thus cannot be embedded.  Locate the modules
    # and data resources of these packages on the filesystem as well.
    pkgs_requiring_file = ["botocore", "boto3", "docutils.parsers.rst", "docutils.writers"]

    if type(resource) == "PythonModuleSource":
        if resource.name in pkgs_requiring_file or any([resource.name.startswith(p + ".") for p in pkgs_requiring_file]):
            resource.add_location = "filesystem-relative:lib"

    if type(resource) in ("PythonPackageResource", "PythonPackageDistributionResource"):
        if resource.package in pkgs_requiring_file or any([resource.package.startswith(p + ".") for p in pkgs_requiring_file]):
            resource.add_location = "filesystem-relative:lib"

    # We ignore most "unclassified" Files (include_file_resources = False
    # above) since our config discovers and emits *both* classified
    # (PythonModuleSource, etc) and unclassified resources (File) and we prefer
    # the former.  However, a libffi shared object that ships with the Linux
    # wheel for cffi doesn't get classified and thus must be caught here as a
    # plain File.
    if type(resource) == "File":
        if resource.path.startswith("cffi.libs/libffi"):
            print("Adding " + resource.path + " to bundle")
            resource.add_include = True
            resource.add_location = "filesystem-relative:lib"


# Materialize all the installation artifacts for the executable + external
# resources into a directory.
def make_installation(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files


# XXX TODO: Consider also making distribution artifacts from these installation
# artifacts using Tugger <https://pyoxidizer.readthedocs.io/en/stable/tugger.html>.
#   -trs, 31 May 2022


register_target("exe", make_exe)
register_target("installation", make_installation, depends=["exe"], default=True)
resolve_targets()
