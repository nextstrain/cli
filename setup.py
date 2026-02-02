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
    package_data = {
        "nextstrain.cli.resources": [
            "bashrc",
            "schema-pathogen-v0.json",
        ],
    },

    description      = "Nextstrain command-line tool",
    long_description = long_description,
    long_description_content_type = "text/markdown",

    author       = "Thomas Sibley",
    author_email = "tsibley@fredhutch.org",

    license = "MIT",

    url          = "https://docs.nextstrain.org/projects/cli/",
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],

    # Install a "nextstrain" program which calls nextstrain.cli.__main__.main()
    #   https://setuptools.readthedocs.io/en/latest/setuptools.html#automatic-script-creation
    entry_points = {
        "console_scripts": [
            "nextstrain = nextstrain.cli.__main__:main",
        ],
    },

    python_requires = '>=3.8',

    install_requires = [
        "boto3 ==1.*",
        "certifi",
        "docutils",
        "fasteners",
        "importlib_resources >=5.3.0; python_version < '3.11'",
        "jsonschema >=4", # for draft 2020-12 support
        "packaging",
        "pyjwt[crypto] >=2.0.0",
        "pyparsing >=3.0.0",
        "pyyaml >=5.3.1",
        "requests",
        "typing_extensions >=3.7.4",
        "wcmatch >=6.0",
        "wrapt >=2.0.0",

        # Avoiding 2023.9.1 due to change in `auto_mkdir` parameter in
        # https://github.com/fsspec/filesystem_spec/pull/1358 that causes the
        # error described in https://github.com/fsspec/s3fs/issues/790
        "fsspec[s3] !=2023.9.1",

        # From 2.0.0 onwards, urllib3 is better typed, but not usable (given
        # our dep tree) on 3.8 and 3.9 so we use types-urllib3 there (see
        # below).
        "urllib3 >=2.0.0; python_version >= '3.10'",
    ],

    extras_require = {
        "dev": [
            "cram >=0.7",
            "flake8 >=4.0.0",
            "myst-parser",
            "nextstrain-sphinx-theme>=2022.5",
            "pytest; python_version != '3.9'",
            "pytest !=7.0.0; python_version == '3.9'",
            "pytest-forked",
            "sphinx>=3",
            "sphinx-autobuild",
            "sphinx-markdown-tables !=0.0.16",
            "sphinx_rtd_theme",
            "types-boto3",
            "types-boto3-s3",
            "types-botocore",

            # Only necessary for urllib3 <2.0.0, which we only have to use on
            # Python 3.8 and 3.9.
            "types-urllib3; python_version < '3.10'"
        ],
    },
)
