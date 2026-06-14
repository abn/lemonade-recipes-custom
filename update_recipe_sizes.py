#!/usr/bin/env python3
import os
import json
import re
import pathlib
from typing import Dict, Any, List, Tuple


def get_hf_cache_dir() -> pathlib.Path:
    if "HF_HUB_CACHE" in os.environ:
        return pathlib.Path(os.environ["HF_HUB_CACHE"])
    if "HF_HOME" in os.environ:
        return pathlib.Path(os.environ["HF_HOME"]) / "hub"
    cache_home = os.environ.get("CACHE_HOME") or os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return pathlib.Path(cache_home) / "huggingface" / "hub"
    return pathlib.Path(os.path.expanduser("~/.cache/huggingface/hub"))


def get_lemonade_cache_dir() -> pathlib.Path:
    if "LEMONADE_CACHE_DIR" in os.environ:
        return pathlib.Path(os.environ["LEMONADE_CACHE_DIR"])
    cache_home = os.environ.get("CACHE_HOME") or os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return pathlib.Path(cache_home) / "lemonade"
    return pathlib.Path(os.path.expanduser("~/.cache/lemonade"))


def repo_id_to_slug(repo_id: str) -> str:
    return "models--" + repo_id.replace("/", "--")


def get_active_snapshot_dir(repo_path: pathlib.Path) -> pathlib.Path | None:
    if not repo_path.exists():
        return None

    # Try reading refs/main
    ref_path = repo_path / "refs" / "main"
    if ref_path.exists():
        try:
            commit_hash = ref_path.read_text().strip()
            snapshot_dir = repo_path / "snapshots" / commit_hash
            if snapshot_dir.exists():
                return snapshot_dir
        except Exception:
            pass

    # Fallback to scanning snapshots directory
    snapshots_path = repo_path / "snapshots"
    if snapshots_path.exists():
        try:
            subdirs = [d for d in snapshots_path.iterdir() if d.is_dir()]
            if subdirs:
                # Use the most recently modified snapshot
                return max(subdirs, key=lambda d: d.stat().st_mtime)
        except Exception:
            pass

    return None


def resolve_checkpoint_files(
    repo_id: str, variant: str, hf_cache: pathlib.Path
) -> List[pathlib.Path]:
    slug = repo_id_to_slug(repo_id)
    repo_path = hf_cache / slug
    if not repo_path.exists():
        return []

    snapshot_dir = get_active_snapshot_dir(repo_path)
    if not snapshot_dir or not snapshot_dir.exists():
        return []

    # If no variant is specified, it means we treat the entire repository directory as the checkpoint
    # (common for non-GGUF repositories, e.g., PyTorch / safetensors weights in vLLM)
    if not variant:
        files = []
        for root, _, filenames in os.walk(snapshot_dir):
            for name in filenames:
                # Ignore partial downloads and hidden metadata files
                if not name.endswith(".partial") and not name.startswith("."):
                    files.append(pathlib.Path(root) / name)
        return files

    # Find matching variant files inside the snapshot directory
    variant_lower = variant.lower()
    all_files = []
    for root, _, filenames in os.walk(snapshot_dir):
        for name in filenames:
            if not name.endswith(".partial") and not name.startswith("."):
                all_files.append(pathlib.Path(root) / name)

    # 1. Exact filename match
    for f in all_files:
        if f.name.lower() == variant_lower:
            return [f]

    # 2. Exact match with .gguf appended
    for f in all_files:
        if f.name.lower() == f"{variant_lower}.gguf":
            return [f]

    # 3. Ends with -variant.gguf or _variant.gguf
    for f in all_files:
        if f.name.lower().endswith(f"-{variant_lower}.gguf") or f.name.lower().endswith(
            f"_{variant_lower}.gguf"
        ):
            return [f]

    # 4. Ends with variant
    for f in all_files:
        if f.name.lower().endswith(variant_lower):
            return [f]

    # 5. Case-insensitive contains variant
    matches = []
    for f in all_files:
        if variant_lower in f.name.lower():
            matches.append(f)
    if matches:
        return [matches[0]]

    return []


def extract_checkpoints_from_recipe(recipe: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Extracts all checkpoint specifications as (repo_id, variant) tuples.
    Also parses any implicit draft models from the recipe.
    """
    checkpoints: List[Tuple[str, str]] = []

    # 1. Standard checkpoints dictionary
    cps = recipe.get("checkpoints")
    if isinstance(cps, dict):
        for key, val in cps.items():
            if isinstance(val, str):
                checkpoints.append(parse_checkpoint_str(val))

    # 2. Root checkpoint/mmproj/mtp keys
    for key in ["checkpoint", "mmproj", "mtp"]:
        val = recipe.get(key)
        if isinstance(val, str):
            checkpoints.append(parse_checkpoint_str(val))

    return checkpoints


def parse_checkpoint_str(cp_str: str) -> Tuple[str, str]:
    if ":" in cp_str:
        repo_id, variant = cp_str.split(":", 1)
        return repo_id.strip(), variant.strip()

    # If no colon, but has a slash, it's a repository ID (no variant)
    if "/" in cp_str:
        return cp_str.strip(), ""

    # Otherwise, it's a variant belonging to the main model (repo will be inferred from main)
    return "", cp_str.strip()


def extract_recipe_args_drafts(recipe: Dict[str, Any]) -> List[str]:
    """
    Extracts any referenced draft/speculative model IDs or paths in recipe_options.
    """
    drafts = []
    opts = recipe.get("recipe_options", {})
    if not isinstance(opts, dict):
        return []

    # llamacpp --model-draft
    llamacpp_args = opts.get("llamacpp_args", "")
    if llamacpp_args:
        matches = re.findall(r"--model-draft\s+([^\s]+)", llamacpp_args)
        for m in matches:
            drafts.append(m.strip("\"'"))

    # vllm --speculative-config/model
    vllm_args = opts.get("vllm_args", "")
    if vllm_args:
        # Check for JSON speculative-config
        spec_config_match = re.search(r"--speculative-config\s+(\{.*?\})", vllm_args)
        if spec_config_match:
            try:
                config = json.loads(spec_config_match.group(1))
                if isinstance(config, dict) and "model" in config:
                    drafts.append(config["model"])
            except Exception:
                pass
        # Check for --speculative-model parameter
        spec_model_match = re.search(r"--speculative-model\s+([^\s]+)", vllm_args)
        if spec_model_match:
            drafts.append(spec_model_match.group(1))

    return drafts


def main():
    hf_cache = get_hf_cache_dir()
    lemonade_cache = get_lemonade_cache_dir()

    print(f"Hugging Face Cache: {hf_cache}")
    print(f"Lemonade Cache: {lemonade_cache}")

    # Discover recipe directories inside the repository root
    repo_root = pathlib.Path(__file__).parent.resolve()
    recipe_dirs = [repo_root / "recipes"]

    recipe_files: List[pathlib.Path] = []
    for rdir in recipe_dirs:
        if rdir.exists():
            for root, _, filenames in os.walk(rdir):
                for fname in filenames:
                    if fname.endswith(".json"):
                        recipe_files.append(pathlib.Path(root) / fname)

    print(f"Found {len(recipe_files)} recipe files to process.")

    # Load user_models.json to update it in sync
    user_models_path = lemonade_cache / "user_models.json"
    user_models = {}
    user_models_updated = False
    if user_models_path.exists():
        try:
            with open(user_models_path, "r", encoding="utf-8") as f:
                user_models = json.load(f)
            print("Loaded user_models.json")
        except Exception as e:
            print(f"Warning: Failed to load user_models.json: {e}")

    for recipe_path in recipe_files:
        try:
            with open(recipe_path, "r", encoding="utf-8") as f:
                recipe = json.load(f)
        except Exception as e:
            print(f"Error reading {recipe_path}: {e}")
            continue

        # Basic validation: must have recipe name/options or checkpoints
        if not isinstance(recipe, dict) or (
            "recipe" not in recipe
            and "checkpoints" not in recipe
            and "checkpoint" not in recipe
        ):
            continue

        model_name = recipe.get("model_name", recipe.get("id", ""))
        if not model_name:
            continue

        # Parse checkpoints from recipe
        raw_cps = extract_checkpoints_from_recipe(recipe)
        if not raw_cps:
            continue

        # Infer repository for variant-only checkpoints
        main_repo = None
        for repo_id, variant in raw_cps:
            if repo_id:
                # The first checkpoint with a repository ID is assumed to be the main repository
                main_repo = repo_id
                break

        checkpoints = []
        for repo_id, variant in raw_cps:
            if not repo_id and main_repo:
                checkpoints.append((main_repo, variant))
            else:
                checkpoints.append((repo_id, variant))

        # Extract implicit drafts from recipe options arguments (speculative decoding)
        drafts = extract_recipe_args_drafts(recipe)
        for draft in drafts:
            # Parse the draft model path or ID
            if os.path.isabs(draft):
                # Absolute path: handle directly
                checkpoints.append(("", draft))
            else:
                d_repo, d_variant = parse_checkpoint_str(draft)
                if not d_repo and main_repo:
                    checkpoints.append((main_repo, d_variant))
                else:
                    checkpoints.append((d_repo, d_variant))

        # Dedup checkpoints
        unique_checkpoints = []
        seen = set()
        for repo_id, variant in checkpoints:
            key = (repo_id, variant)
            if key not in seen:
                seen.add(key)
                unique_checkpoints.append(key)

        # Resolve all files for checkpoints
        resolved_files: List[pathlib.Path] = []

        for repo_id, variant in unique_checkpoints:
            if not repo_id and os.path.isabs(variant):
                # Handled absolute path directly
                p = pathlib.Path(variant)
                if p.exists() and p.is_file():
                    resolved_files.append(p)
            else:
                files = resolve_checkpoint_files(repo_id, variant, hf_cache)
                if files:
                    resolved_files.extend(files)

        # If the main checkpoint exists, calculate size
        # We check if we got at least one file from the main repository
        has_main_downloaded = False
        if main_repo:
            main_slug = repo_id_to_slug(main_repo)
            for f in resolved_files:
                if main_slug in str(f):
                    has_main_downloaded = True
                    break

        if has_main_downloaded:
            # Calculate total size in GiB (deduplicate files by absolute path)
            unique_files = list(set(f.resolve() for f in resolved_files))
            total_bytes = sum(f.stat().st_size for f in unique_files)
            size_gib = round(total_bytes / (1024**3), 3)

            old_size = recipe.get("size")
            if old_size != size_gib:
                recipe["size"] = size_gib
                try:
                    with open(recipe_path, "w", encoding="utf-8") as f:
                        json.dump(recipe, f, indent=4)
                        f.write("\n")
                    print(
                        f"Updated {recipe_path.relative_to(repo_root)}: {old_size} -> {size_gib} GiB"
                    )
                except Exception as e:
                    print(f"Failed to write updated recipe {recipe_path}: {e}")
            else:
                print(
                    f"Recipe {recipe_path.relative_to(repo_root)} is already up-to-date: {size_gib} GiB"
                )

            # Update user_models.json if matching
            # Format in user_models.json keys could be e.g., "GLM-4.7-Flash-GGUF-NoThinking"
            # whereas recipe.model_name is "user.GLM-4.7-Flash-GGUF-NoThinking"
            canonical_name = model_name
            if canonical_name.startswith("user."):
                canonical_name = canonical_name[5:]

            if canonical_name in user_models:
                old_user_size = user_models[canonical_name].get("size")
                if old_user_size != size_gib:
                    user_models[canonical_name]["size"] = size_gib
                    user_models_updated = True
                    print(
                        f"  Updated user_models.json [{canonical_name}]: {old_user_size} -> {size_gib} GiB"
                    )
        else:
            print(
                f"Skipping {recipe_path.relative_to(repo_root)}: checkpoints not downloaded/found in cache."
            )

    # Save user_models.json if updated
    if user_models_updated and user_models_path.exists():
        try:
            with open(user_models_path, "w", encoding="utf-8") as f:
                json.dump(user_models, f, indent=2)
                f.write("\n")
            print("Successfully saved updated user_models.json")
        except Exception as e:
            print(f"Error saving user_models.json: {e}")


if __name__ == "__main__":
    main()
