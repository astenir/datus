PACKAGES := datus-storage-base datus-storage-postgresql
PKG ?=

.PHONY: build clean publish-test publish install-test help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

_pkgs = $(if $(PKG),$(PKG),$(PACKAGES))

build: clean ## Build packages (all or PKG=<name>)
	@set -e; for pkg in $(_pkgs); do \
		echo "Building $$pkg..."; \
		uv build --package $$pkg; \
	done

clean: ## Clean dist directories
	rm -rf dist

publish-test: build ## Build and publish to TestPyPI (all or PKG=<name>)
	uvx twine upload --repository testpypi dist/*

publish: build ## Build and publish to PyPI (all or PKG=<name>)
	uvx twine upload dist/*

install-test: ## Install packages from TestPyPI (for verification)
	uv pip install --index-url https://test.pypi.org/simple/ \
		--extra-index-url https://pypi.org/simple/ \
		datus-storage-base datus-storage-postgresql
