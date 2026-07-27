"""Apply and persist one semantic recipe in an existing reconstructed corpus."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from shader_toolchain.sbc import D3DCompiler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("module")
    args = parser.parse_args()

    manifest_path = args.corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest["shaders"]
    blobs: list[bytes] = [b""] * (max(r["bundle_index"] for r in records) + 1)
    for record in records:
        blobs[record["bundle_index"]] = (args.corpus / record["dxbc_path"]).read_bytes()

    recipe_module = importlib.import_module(
        f"shader_toolchain.recipes.{args.module}"
    )
    recipe = getattr(recipe_module, f"apply_{args.module}_recipe")
    result = recipe(args.corpus, records, blobs, D3DCompiler())
    if result is None:
        raise RuntimeError(f"{args.module} recipe did not recognize this corpus")

    recipes = manifest["summary"].setdefault("semantic_recipes", [])
    recipes[:] = [item for item in recipes if item["name"] != args.module]
    recipes.append(result)
    recipes.sort(key=lambda item: item["name"])
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
