LEMONADE ?= lemonade
export LEMONADE

.DEFAULT_GOAL := help

.PHONY: list help FORCE recipes/sizes lint

##@ Recipies & Recipes

list: ## List all available recipe options
	@find recipies recipes -type f -name "*.json"

recipies/%: FORCE ## Import a custom recipe (e.g., recipies/unsloth/gemma/Gemma-4-E4B-it-qat-MTP.json)
	@case "$*" in \
		unsloth/gemma/*-MTP.json) \
			./recipies/unsloth/gemma/import-mtp.sh "$@" ;; \
		*) \
			$(LEMONADE) import "$@" ;; \
	esac

recipes/%: FORCE ## Import a standard recipe (e.g., recipes/lemonade/coding-agents/GLM-4.7-Flash-GGUF-NoThinking.json)
	$(LEMONADE) import "$@"

recipes/sizes: ## Determine and update recipe sizes from local HF cache
	@python3 ./update_recipe_sizes.py

##@ Utilities

lint: ## Run linter and formatter checks using pre-commit
	pre-commit run --all-files

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	  /^[a-zA-Z0-9_%/-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
