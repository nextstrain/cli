from setuptools import setup, find_packages
from pathlib    import Path

base_dir     = Path(__file__).parent.resolve()
version_file = base_dir / "nextstrain/cli/__version__.py"
readme_file  = base_dir / "README.md"

# Eval the version file to get __version__; avoids importing our own package
with version_file.open() as f:
    exec(f.read())

# Get the long description from the README file
with readme_file.open(encoding = "utf-8") as f:
    long_description = f.read()

# Nextstrain is a "namespace" package, which is supported natively in Python 3
# but not supported by find_packages().  A namespace package is a) shareable by
# several subpackages and b) is defined by the lack of an __init__.py.  The
# actual concrete packages in this distribution are nextstrain.cli,
# nextstrain.cli.command, etc.  Although find_packages() doesn't support
# namespace packages (it won't look within them), we can use find_packages() by
# looking past the namespace and then adding the namespace prefix back.
def find_namespaced_packages(namespace):
    return [
        "%s.%s" % (namespace, pkg)
            for pkg in find_packages(namespace.replace(".", "/"))
    ]

setup(
    name     = "nextstrain-cli",
    version  = __version__, # noqa: F821
    packages = find_namespaced_packages("nextstrain"),

    description      = "Nextstrain command-line tool",
    long_description = long_description,
    long_description_content_type = "text/markdown",

    author       = "Thomas Sibley",
    author_email = "tsibley@fredhutch.org",

    license = "MIT",

    url          = "https://github.com/nextstrain/cli",
    project_urls = {
        "Bug Reports": "https://github.com/nextstrain/cli/issues",
        "Change Log":  "https://github.com/nextstrain/cli/blob/master/CHANGES.md",
        "Source":      "https://github.com/nextstrain/cli",
    },

    classifiers = [
        # Stable now
        "Development Status :: 5 - Production/Stable",

        # This is a CLI
        "Environment :: Console",

        # This is for bioinformatic software devs and researchers
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Scientific/Engineering :: Bio-Informatics",

        # License
        "License :: OSI Approved :: MIT License",

        # Python 3 only
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],

    # Install a "nextstrain" program which calls nextstrain.cli.__main__.main()
    #   https://setuptools.readthedocs.io/en/latest/setuptools.html#automatic-script-creation
    entry_points = {
        "console_scripts": [
            "nextstrain = nextstrain.cli.__main__:main",
        ],
    },

    python_requires = '>=3.6',

    install_requires = [
        "netifaces >=0.10.6",
        "requests",

        # We use fsspec's S3 support, which has a runtime dep on s3fs.  s3fs
        # itself requires aiobotocore, which in turn requires very specific
        # versions of botocore (because aiobotocore is a giant monkey-patch).
        #
        # We also use boto3, which also requires botocore, usually with minimum
        # versions closely matching the boto3 version (they're released in near
        # lock step).
        #
        # If we declare a dep on boto3 directly, this leads to conflicts during
        # dependency resolution when a newer boto3 (from our declaration here)
        # requires a newer botocore than is supported by s3fs → aiobotocore's
        # declarations.
        #
        # Resolve the issue by using a specially-provided package extra from
        # aiobotocore which causes them to declare explicit dependencies on
        # boto3 so that the dependency resolver can figure it out properly.
        #
        # See <https://github.com/dask/s3fs/issues/357> for more background.
        #
        # What a mess.
        "fsspec",
        "s3fs",
        "aiobotocore[boto3]",

        # We use pkg_resources.parse_version(), which (confusingly) is provided
        # by setuptools.  setuptools is nearly ever-present, but it can be
        # missing!
        "setuptools >=8.0.3",

        "pycognito",
    ],

    extras_require = {
        "dev": [
            "docutils<0.16",
            "flake8",
            "mypy",
            "nextstrain-sphinx-theme",
            "pytest",
            "pytest-flake8",
            "pytest-mypy",
            "recommonmark",
            "sphinx>=3",
            "sphinx-argparse",
            "sphinx-markdown-tables",
            "sphinx_rtd_theme",
        ],
    },
)
