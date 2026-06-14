#!/bin/bash

set -xeuo pipefail

CACHE_DIR=${HOME}/.cache
LEMONADE_CACHE=${CACHE_DIR}/lemonade
HF_MODEL_CACHE=${CACHE_DIR}/huggingface/hub

RECIPE="$1"

mapfile -t ARGS < <(jq -r '.model_name, (.checkpoints.mtp | split(":")[-1]), (.checkpoints.mtp | split(":")[0])' "$RECIPE")
MODEL_ID="${ARGS[0]}"
MTP_DRAFT="${ARGS[1]}"
REPO_NAME="${ARGS[2]}"
REPO_DIR="models--$(echo "${REPO_NAME}" | sed 's/\//--/g')"

# 1. First import: Register the model and trigger the file downloads if not already downloaded.
"${LEMONADE:-lemonade}" import "${RECIPE}"

# 2. Find the downloaded MTP draft GGUF file in the specific repository's Hugging Face cache.
MTP_DRAFT_PATH=$(find -L ~/.cache/huggingface/hub/"${REPO_DIR}"/ -type f -name "$MTP_DRAFT" -print -quit)

if [ -n "$MTP_DRAFT_PATH" ]; then
    echo "Resolved MTP draft path: ${MTP_DRAFT_PATH}"

    # 3. Create a temporary modified recipe JSON file.
    # We put the absolute path to the draft model directly in the recipe options.
    TEMP_RECIPE="${RECIPE}.tmp"
    trap 'rm -f "${TEMP_RECIPE}"' EXIT

    jq --arg drf "--model-draft \"${MTP_DRAFT_PATH}\"" \
       '.recipe_options.llamacpp_args |= sub("--model-draft \\S+"; $drf)' \
       "${RECIPE}" > "${TEMP_RECIPE}"

    # 4. Import the modified recipe to update the server's in-memory state and disk cache.
    "${LEMONADE:-lemonade}" import "${TEMP_RECIPE}"
else
    echo "Warning: MTP draft file ${MTP_DRAFT} not found in HF cache. Skipping path resolution."
fi
