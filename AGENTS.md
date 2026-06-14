# AGENTS.md

This file provides guidance for agent-driven tasks and code reviews when working with the custom recipes repository.

## General Guidance

* **Read the Documentation First:** The primary developer documentation, technical rationale, workflow explanations, directory structure, and invariants reside in the repository's [README.md](README.md).
* **Keep README.md Up-to-Date:** Whenever you modify existing model recipes, add new custom recipes, introduce new workflows, or change configuration options (such as updating speculative flags or backend requirements), you **MUST** ensure that the [README.md](README.md) is updated in the same change to reflect those modifications.
* **Recipe Validation:** Always validate any new or updated recipe files using the `validate_recipe_json.py` script before finalizing your task:
  ```bash
  python3 recipes/lemonade/validate_recipe_json.py <recipe_file.json>
  ```
