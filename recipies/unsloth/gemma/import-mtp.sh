#!/bin/bash

set -xeuo pipefail

CACHE_DIR=${HOME}/.cache
LEMONADE_CACHE=${CACHE_DIR}/lemonade
HF_MODEL_CACHE=${CACHE_DIR}/huggingface/hub

RECIPE="$1"
TARGET="${LEMONADE_CACHE}/recipe_options.json"

mapfile -t ARGS < <(jq -r '.model_name, (.checkpoints.mtp | split(":")[-1])' "$RECIPE")
MODEL_ID="${ARGS[0]}"
MTP_DRAFT="${ARGS[1]}"

"${LEMONADE:-lemonade}" import ${RECIPE}

MTP_DRAFT_PATH=$(find ~/.cache/huggingface/hub/ -type f -name "$MTP_DRAFT" -print -quit)

jq --arg id "$MODEL_ID" \
   --arg drf "--model-draft \"${MTP_DRAFT_PATH}\"" \
   '.[$id].llamacpp_args |= sub("--model-draft \\S+"; $drf)' "$TARGET" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"

