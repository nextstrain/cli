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
    version  = __version__,
    packages = find_namespaced_packages("nextstrain"),

    data_files = [("", ["LICENSE"])],

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

        # Python 3 only; subprocess.run is >=3.5
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],

    # Install a "nextstrain" program which calls nextstrain.cli.__main__.main()
    #   https://setuptools.readthedocs.io/en/latest/setuptools.html#automatic-script-creation
    entry_points = {
        "console_scripts": [
            "nextstrain = nextstrain.cli.__main__:main",
        ],
    },

    python_requires = '>=3.5',

    install_requires = [
        "boto3",
        "netifaces >=0.10.6",
        "requests",
    ],
)
