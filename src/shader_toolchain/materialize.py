"""Produce clean standalone semantic HLSL for one recovered permutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hlsl import resolve_local_includes, semantic_module_variants
from .reconstruct import ToolchainError


def semantic_records(corpus: Path, source_name: str) -> list[dict[str, Any]]:
    manifest_path = corpus / "manifest.json"
    if not manifest_path.is_file():
        raise ToolchainError(f"not a reconstructed shader corpus: {corpus}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = [
        shader
        for shader in manifest.get("shaders", [])
        if shader["source_name"] == source_name
        and shader.get("semantic_hlsl_path")
    ]
    if not records:
        raise ToolchainError(f"no semantic shader module named {source_name}")
    return sorted(records, key=lambda item: item["selector"])


def select_semantic_record(
    records: list[dict[str, Any]],
    *,
    selector: str | None = None,
    required_defines: list[str] | None = None,
) -> dict[str, Any]:
    matches = records
    if selector:
        matches = [record for record in matches if record["selector"] == selector]
    for definition in required_defines or []:
        matches = [record for record in matches if definition in record["defines"]]
    if len(matches) != 1:
        raise ToolchainError(
            f"semantic variant selection matched {len(matches)} shaders; "
            "use --list to inspect selectors and recovered definitions"
        )
    return matches[0]


def expand_semantic_records(
    corpus: Path, records: list[dict[str, Any]]
) -> dict[str, str]:
    relative_paths = {record["semantic_hlsl_path"] for record in records}
    if len(relative_paths) != 1:
        raise ToolchainError("semantic records do not share one source module")
    module_path = corpus / next(iter(relative_paths))
    source = module_path.read_text(encoding="utf-8")
    variants = semantic_module_variants(
        source,
        {record["selector"]: record["defines"] for record in records},
    )
    return {
        selector: resolve_local_includes(body, module_path, corpus / "semantic")
        for selector, body in variants.items()
    }


def materialize_semantic_variant(
    corpus: Path,
    source_name: str,
    output: Path,
    *,
    selector: str | None = None,
    required_defines: list[str] | None = None,
) -> dict[str, Any]:
    records = semantic_records(corpus, source_name)
    record = select_semantic_record(
        records, selector=selector, required_defines=required_defines
    )
    variants = expand_semantic_records(corpus, records)
    if output.exists():
        raise ToolchainError(f"output path already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"// Materialized {source_name} {record['selector']}\n"
        f"// Stage: {record['stage']}; entry point: {record['entry_point']}\n"
        + variants[record["selector"]],
        encoding="utf-8",
        newline="\n",
    )
    return {
        "source_name": source_name,
        "selector": record["selector"],
        "stage": record["stage"],
        "entry_point": record["entry_point"],
        "defines": record["defines"],
        "output": str(output),
    }
