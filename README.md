# Lemonade Custom Model Recipes

This repository contains custom and experimental model recipe definitions for the [Lemonade LLM Server](https://github.com/lemonade-sdk/lemonade). Model recipes define custom load configurations, system paths, specific backends (such as `llamacpp` or `vllm`), hardware acceleration backends (like `vulkan` or `rocm`), context window allocations, and speculative decoding options.

> [!WARNING]
> ### 🐉 Here Be Dragons!
> This repository is a wild frontier of custom configurations. These recipes are configured, tuned, and optimized for **AMD Strix Halo** hardware targets (specifically AMD Ryzen AI Max APUs).
> - Some options, particularly **context sizes** (e.g., up to 32k/64k windows), are optimized for the massive unified memory architecture of Strix Halo and **will need to be adjusted** on systems with less memory or other hardware configurations.
> - **This repository is for personal use only and is not supported in any way, shape, or form.** Use it at your own risk. If your APU starts breathing real fire, your unified memory turns into a black hole, or your terminal decides to achieve sentience and demand coffee, you are entirely on your own!

---

## Technical Configuration & Rationale

We use specific design principles and optimization patterns when configuring custom model recipes for this repository:

### 1. Hardware Targeting (AMD Strix Halo)
* **Unified Memory Scaling:** Because Strix Halo features up to 64GB or 128GB of high-bandwidth unified LPDDR5X memory, we can configure large context windows (`context_size`) and allocate significant resources to graphics queues.
* **ROCm Engine Acceleration:** For high-performance GPU/APU inference under Linux, we target the `vllm` recipe engine utilizing ROCm.
  * Backend configuration specifies `"vllm_backend": "rocm"`.
  * Validated specifically for the `gfx1151` target architecture.

### 2. Multi-Token Prediction (MTP) & Speculative Decoding
Speculative decoding reduces latency by using a smaller assistant or draft model.
* **llama.cpp Speculative Flags:** Older N-gram options are deprecated and will crash the model server on load. We strictly adhere to the updated schema:
  * **Do NOT use:** `--spec-ngram-size-n`, `--draft-min`, or `--draft-max`.
  * **DO use:** `--spec-type ngram-mod --spec-ngram-mod-n-match <N> --spec-ngram-mod-n-min <min> --spec-ngram-mod-n-max <max>`
* **vLLM Speculative Config:** Configured within `vllm_args` using the `--speculative-config` (JSON) or `--speculative-model` arguments:
  ```json
  "vllm_args": "--speculative-config {\"method\":\"mtp\",\"model\":\"google/gemma-4-E4B-it-qat-q4_0-unquantized-assistant\",\"num_speculative_tokens\":1}"
  ```
* **Absolute Path Constraint (MTP):** Since `llama-server` executes in a separate process directory, it cannot resolve relative paths for speculative draft models (e.g., `--model-draft`). Therefore, our custom import workflow resolves the draft model GGUF path to an absolute path inside the Hugging Face cache.

### 3. Process & Environment Configuration
By default, the `Makefile` and other scripts assume Lemonade is running as a user process. They resolve the cache location using `$CACHE_HOME` (which is configurable, defaulting to `$XDG_CACHE_HOME` and falling back to `~/.cache/`) for locating both the Hugging Face cache and the Lemonade cache.

You can override this directory when running `make` by passing it as a variable:
```bash
make recipes/unsloth/gemma/Gemma-4-E4B-it-qat-MTP.json CACHE_HOME=/path/to/custom/cache
```

For Flatpak server instances, this setup assumes the following filesystem overrides are configured in `~/.local/share/flatpak/overrides/ai.lemonade_server.Lemonade`:

```ini
[Context]
filesystems=xdg-config/flm;xdg-cache/huggingface;xdg-cache/lemonade;xdg-config/lemonade
```

---

## Directory Structure

* [Makefile](Makefile) — Entrypoint for developers to list, import, and manage recipes.
* [update_recipe_sizes.py](update_recipe_sizes.py) — Reusable helper script to calculate real checkpoint sizes in GiB and sync them with recipe definitions and the server's cache.
* `recipes/` — Recipe definitions:
  * `recipes/lemonade/` — Git submodule containing default, unmodified upstream model definitions.
    * [validate_recipe_json.py](recipes/lemonade/validate_recipe_json.py) — Strict validation script for recipe JSON files.
  * `recipes/coding-agents/` and `recipes/unsloth/` — Custom/experimental recipe configurations (e.g., Unsloth-based models or specialized coding agents).
    * [import-mtp.sh](recipes/unsloth/gemma/import-mtp.sh) — Helper to auto-resolve relative MTP draft paths to absolute local Hugging Face cache paths.

### Custom Model Recipes

In addition to upstream recipes, this repository defines:
* **Gemma-4 12B QAT + MTP Coding Variants** (in `recipes/unsloth/gemma/`):
  * `Gemma-4-12B-NoThinking-qat-MTP.json` — Coding variant with reasoning disabled (`--reasoning off`, `--temp 0.1`).
  * `Gemma-4-12B-ThinkingCoder-qat-MTP.json` — Coding variant with reasoning enabled (`--reasoning on`, `--temp 0.7`).

---


## Key Developer Workflows

### 1. Listing Available Recipes
Use `make list` to print all JSON recipe files in the repository:
```bash
make list
```

### 2. Importing a Standard Recipe
Importing standard recipes translates to a `lemonade import <recipe_path>` call:
```bash
make recipes/lemonade/coding-agents/GLM-4.7-Flash-GGUF-NoThinking.json
```

### 3. Importing a Multi-Token Prediction (MTP) Speculative Recipe
For experimental recipes in `recipes/unsloth/gemma/` that require resolving absolute draft paths:
```bash
make recipes/unsloth/gemma/Gemma-4-E4B-it-qat-MTP.json
```
The Make target invokes [import-mtp.sh](recipes/unsloth/gemma/import-mtp.sh), which:
1. Registers the initial recipe via `lemonade import` (initiating model pulling).
2. Searches the local Hugging Face hub cache (`~/.cache/huggingface/hub/`) for the downloaded MTP draft GGUF.
3. Automatically overwrites the `--model-draft` argument inside `recipe_options.llamacpp_args` with the resolved absolute path.
4. Performs a second `lemonade import` to load the updated configuration.

### 4. Updating Recipe Sizes
When model files have been pulled/cached, run `make recipes/sizes` (or [update_recipe_sizes.py](update_recipe_sizes.py) directly) to scan for cached checkpoints, compute their real sizes in GiB, and sync them back with the recipe JSON and the Lemonade user registry:
```bash
make recipes/sizes
```

### 5. Recipe Validation Rules
Any new or modified recipe JSON file must pass strict checks via [validate_recipe_json.py](recipes/lemonade/validate_recipe_json.py) before integration.
* Supported keys are strictly bounded to: `checkpoint`, `checkpoints`, `model_name`, `id`, `image_defaults`, `labels`, `recipe`, `recipe_options`, `size`.
* Checkpoints must specify either the top-level string `checkpoint` or the mapping object `checkpoints` containing component strings (like `"main"`, `"npu_cache"`, `"text_encoder"`, or `"vae"`).

Run validation manually using:
```bash
python3 recipes/lemonade/validate_recipe_json.py <recipe_file.json>
```
