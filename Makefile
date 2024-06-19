# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first three.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
PYTHON        ?= python3
SOURCEDIR     = source
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
.PHONY: help
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)

.PHONY: clean
clean:
	-rm -rf "$(BUILDDIR)/*"

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.
.PHONY: Makefile
%: Makefile
	@$(PYTHON) babel_runner.py compile source/_extensions/acaciaext acaciaext
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)
