# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile livehtml

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

HOST ?= 127.0.0.1
PORT ?= 8000

serve: dirhtml
	cd "$(BUILDDIR)/dirhtml" && python3 -m http.server --bind "$(HOST)" "$(PORT)"

livehtml:
	sphinx-autobuild -b dirhtml "$(SOURCEDIR)" "$(BUILDDIR)/dirhtml" --host "$(HOST)" --port "$(PORT)" --watch ../nextstrain/cli $(SPHINXOPTS) $(O)
