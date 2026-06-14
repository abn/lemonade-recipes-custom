# AGENTS.md

This file provides guidance to agent-driven tasks and code reviews when working with the custom recipes repository.

## Repository Overview

`lemonade-recipes-custom` is a repository of custom model recipes for the [Lemonade LLM Server](file:///home/abn/workspace/lemonade-sdk/lemonade/AGENTS.md). Model recipes define custom load configurations, system paths, specific backends (such as `llamacpp` or `vllm`), hardware acceleration backends (like `vulkan` or `rocm`), context window allocations, and speculative decoding options.

## Directory Structure

- [Makefile](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/Makefile) — Entrypoint for developers to list, import, and manage recipes.
- [update_recipe_sizes.py](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/update_recipe_sizes.py) — Reusable helper script to calculate real checkpoint sizes in GiB and sync them with recipe definitions and the server's cache.
- `recipes/` — General/standard recipe definitions. Includes the [recipes/lemonade](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/recipes/lemonade) Git submodule containing default upstream model definitions.
  - [validate_recipe_json.py](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/recipes/lemonade/validate_recipe_json.py) — Strict validation script for recipe JSON files.
- `recipies/` — Custom/experimental recipe configurations (e.g., Unsloth-based models or specialized coding agents).
  - [import-mtp.sh](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/recipies/unsloth/gemma/import-mtp.sh) — Helper to auto-resolve relative MTP draft paths to absolute local Hugging Face cache paths.

## Key Developer Workflows

### 1. Listing Available Recipes
Use `make list` to print all JSON recipe files:
```bash
make list
```

### 2. Importing a Standard Recipe
Importing standard recipes translates to a `lemonade import <recipe_path>` call:
```bash
make recipes/lemonade/coding-agents/GLM-4.7-Flash-GGUF-NoThinking.json
```

### 3. Importing a Multi-Token Prediction (MTP) Speculative Recipe
MTP recipes in `recipies/unsloth/gemma/` require the draft model's absolute path because `llama-server` executes in a separate process directory and cannot resolve relative paths. 
The Make target invokes [import-mtp.sh](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/recipies/unsloth/gemma/import-mtp.sh), which performs the following operations:
1. Registers the initial recipe via `lemonade import` (initiating model pulling).
2. Searches the local Hugging Face hub cache (`~/.cache/huggingface/hub/`) for the downloaded MTP draft GGUF.
3. Automatically overwrites the `--model-draft` argument inside `recipe_options.llamacpp_args` with the resolved absolute path.
4. Performs a second `lemonade import` to load the updated configuration.

Run this import via:
```bash
make recipies/unsloth/gemma/Gemma-4-E4B-it-qat-MTP.json
```

### 4. Updating Recipe Sizes
When model files have been pulled/cached, run `make recipes/sizes` (or [update_recipe_sizes.py](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/update_recipe_sizes.py) directly). This script:
1. Scans `recipes/` and `recipies/` directories for recipe JSONs.
2. Extracts all checkpoints (main, mmproj, mtp, etc.) and spec drafts from command args.
3. Finds matching cache directories in Hugging Face Hub (`~/.cache/huggingface/hub` or `HF_HUB_CACHE` / `HF_HOME`).
4. Computes the cumulative size in GiB and updates the `"size"` attribute in the recipe JSON.
5. If the model exists in the Lemonade user registry (`~/.cache/lemonade/user_models.json`), updates its size there as well.

```bash
make recipes/sizes
```

---

## Critical Invariants & Gotchas

### Deprecated llama.cpp Speculative Flags (N-gram)
Older llama.cpp options are deprecated and will crash the model server on load. Ensure you adhere to the updated schema:
- **Do NOT use**: `--spec-ngram-size-n`, `--draft-min`, or `--draft-max`.
- **DO use**: `--spec-type ngram-mod --spec-ngram-mod-n-match <N> --spec-ngram-mod-n-min <min> --spec-ngram-mod-n-max <max>`

*Example from GLM-4.7 recipe options:*
```json
"llamacpp_args": "--temp 0.7 --top-p 1 --min-p 0.01 -b 4096 -ub 1024 --spec-type ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64"
```

### vLLM Recipes & ROCm Backend
For high-performance GPU/APU inference on Linux (specifically tested on AMD Strix Halo gfx1151 targets), use the `vllm` recipe engine.
- The backend configuration should specify `"vllm_backend": "rocm"`.
- Speculative decoding for vLLM is configured inside `vllm_args` using the `--speculative-config` (JSON) or `--speculative-model` arguments:
  ```json
  "vllm_args": "--speculative-config {\"method\":\"mtp\",\"model\":\"google/gemma-4-E4B-it-qat-q4_0-unquantized-assistant\",\"num_speculative_tokens\":1}"
  ```

### Recipe Validation Rules
Any new or modified recipe JSON file must pass strict checks via [validate_recipe_json.py](file:///home/abn/workspace/lemonade-sdk/lemonade-recipes-custom/recipes/lemonade/validate_recipe_json.py) before integration.
- Supported keys are strictly bounded to: `checkpoint`, `checkpoints`, `model_name`, `id`, `image_defaults`, `labels`, `recipe`, `recipe_options`, `size`.
- Checkpoints must specify either the top-level string `checkpoint` or the mapping object `checkpoints` containing component strings (like `"main"`, `"npu_cache"`, `"text_encoder"`, or `"vae"`).
- Run validation manually using:
  ```bash
  python3 recipes/lemonade/validate_recipe_json.py <recipe_file.json>
  ```
