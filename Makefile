LEMONADE ?= lemonade
export LEMONADE

.DEFAULT_GOAL := help

.PHONY: list help FORCE recipes/sizes lint

##@ Recipes

list: ## List all available recipe options
	@find recipes -type f -name "*.json"

recipes/%: FORCE ## Import a recipe (e.g., recipes/unsloth/gemma/Gemma-4-E4B-it-qat-MTP.json)
	@case "$*" in \
		unsloth/gemma/*-MTP.json) \
			./recipes/unsloth/gemma/import-mtp.sh "$@" ;; \
		*) \
			$(LEMONADE) import "$@" ;; \
	esac

recipes/sizes: ## Determine and update recipe sizes from local HF cache
	@python3 ./update_recipe_sizes.py

##@ Utilities

lint: ## Run linter and formatter checks using pre-commit
	pre-commit run --all-files

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	  /^[a-zA-Z0-9_%/-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
