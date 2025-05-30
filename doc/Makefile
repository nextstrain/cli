# Minimal makefile for Sphinx documentation
#
SHELL := bash -euo pipefail

# You can set these variables from the command line, and also
# from the environment for the first three.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
BUILDDIR      ?= _build
SOURCEDIR     = .

# Require stricter builds with
#   -n: warn on missing references
#   -W: error on warnings
#   --keep-going: find all warnings
# https://www.sphinx-doc.org/en/master/man/sphinx-build.html
STRICT = -n -W --keep-going
LOOSE = -n

GENERATE = ../devel/generate-doc

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile livehtml

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	if [[ $@ != clean ]]; then $(GENERATE); fi
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(STRICT) $(SPHINXOPTS) $(O)

HOST ?= 127.0.0.1
PORT ?= 8000

serve: dirhtml
	cd "$(BUILDDIR)/dirhtml" && python3 -m http.server --bind "$(HOST)" "$(PORT)"

livehtml:
	sphinx-autobuild -b dirhtml "$(SOURCEDIR)" "$(BUILDDIR)/dirhtml" --host "$(HOST)" --port "$(PORT)" --watch ../nextstrain/cli --pre-build "$(GENERATE)" $(LOOSE) $(SPHINXOPTS) $(O)
