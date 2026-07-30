"""Inventory structural ``main_part`` feature families and lift coverage."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from .recipes.main_part_families import (
    classify_main_part_vertex_family,
    parse_entry_signature,
    vertex_family_shape,
)


def _semantic_label(parameter: Any) -> str:
    return f"{parameter.semantic.name}{parameter.semantic.index}"


def build_main_part_inventory(
    corpus: Path, *, large_threshold: int = 5 * 1024
) -> dict[str, Any]:
    """Describe repeated structural families and declarative lift coverage."""
    manifest = json.loads(
        (corpus / "manifest.json").read_text(encoding="utf-8")
    )
    records = [
        shader
        for shader in manifest["shaders"]
        if shader["source_name"] == "main_part"
    ]
    snippet_root = corpus / "semantic" / "include" / "main_part"
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    family_counts: Counter[str] = Counter()
    large_count = 0
    covered_large_count = 0
    parse_failures: list[dict[str, str]] = []
    for shader in records:
        if shader["stage"] != "vertex":
            continue
        path = snippet_root / f"{shader['selector']}.hlsl"
        source = path.read_text(encoding="utf-8")
        large = path.stat().st_size > large_threshold
        large_count += int(large)
        try:
            _signature, parameters = parse_entry_signature(source)
            family = classify_main_part_vertex_family(shader["defines"], source)
        except RuntimeError as error:
            parse_failures.append(
                {"selector": shader["selector"], "error": str(error)}
            )
            parameters = ()
            family = None
        family_name = family.name if family is not None else None
        if family_name is not None:
            family_counts[family_name] += 1
            covered_large_count += int(large)
        groups[vertex_family_shape(shader["defines"])].append(
            {
                "selector": shader["selector"],
                "large": large,
                "covered_by": family_name,
                "inputs": [
                    _semantic_label(parameter)
                    for parameter in parameters if not parameter.output
                ],
                "outputs": [
                    _semantic_label(parameter)
                    for parameter in parameters if parameter.output
                ],
            }
        )
    clusters = []
    for shape, members in groups.items():
        signatures = Counter(
            (
                tuple(member["inputs"]),
                tuple(member["outputs"]),
            )
            for member in members
        )
        clusters.append(
            {
                "shape": list(shape),
                "count": len(members),
                "large_count": sum(member["large"] for member in members),
                "covered_count": sum(
                    member["covered_by"] is not None for member in members
                ),
                "signature_count": len(signatures),
                "selectors": [member["selector"] for member in members],
            }
        )
    clusters.sort(key=lambda cluster: (-cluster["count"], cluster["shape"]))
    stage_counts = Counter(shader["stage"] for shader in records)
    return {
        "shader_count": len(records),
        "stage_counts": dict(sorted(stage_counts.items())),
        "large_threshold": large_threshold,
        "large_vertex_count": large_count,
        "covered_vertex_count": sum(family_counts.values()),
        "covered_large_vertex_count": covered_large_count,
        "family_counts": dict(sorted(family_counts.items())),
        "structural_cluster_count": len(clusters),
        "clusters": clusters,
        "parse_failures": parse_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--large-threshold", type=int, default=5 * 1024)
    args = parser.parse_args()
    report = build_main_part_inventory(
        args.corpus, large_threshold=args.large_threshold
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
