"""Batch-lift recognized ``main_part`` families with DXBC ABI validation."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import threading
from typing import Any

from .compare import compare_bytecodes
from .hlsl import (
    hlsl_token_sha256,
    resolve_local_includes,
    semantic_module_variants,
)
from .recipes.common import PROFILES, semantic_worker_count
from .recipes.main_part_families import (
    MAIN_PART_VERTEX_FAMILIES,
    lift_main_part_vertex_family,
)
from .recipes.main_part_pixel_families import lift_main_part_pixel_family
from .recipes.main_part_picking_families import lift_main_part_picking_family
from .recipes.main_part_depth_families import lift_main_part_depth_family
from .recipes.main_part_overlay_families import lift_main_part_overlay_family
from .recipes.main_part_early_gforward_families import (
    lift_main_part_early_gforward_family,
)
from .recipes.main_part_transparent_families import (
    lift_main_part_transparent_family,
)
from .main_part_phase_compiler import compile_main_part_phase_graph
from .recipes.main_part import lift_main_part_variant
from .recipes.main_character import main_character_execution
from .recipes.main_part_directional_glass_surface import (
    classify_main_part_directional_glass_surface,
)
from .reflect import ShaderReflector
from .sbc import D3DCompiler


INCLUDE = re.compile(
    r'^[ \t]*#include[ \t]+"([^"]+)"[ \t]*$', re.MULTILINE
)


def _include_path(
    name: str, *, asset_root: Path, semantic_include_root: Path
) -> Path:
    normalized = name.replace("\\", "/")
    if normalized.startswith("include/"):
        normalized = normalized[len("include/"):]
    elif normalized.startswith("../"):
        normalized = normalized[3:]
    asset_path = asset_root / normalized
    if asset_path.exists():
        return asset_path
    output_path = semantic_include_root / normalized
    if output_path.exists():
        return output_path
    raise RuntimeError(f"family include does not exist: {name}")


def expand_family_includes(
    source: str, *, asset_root: Path, semantic_include_root: Path,
    stack: tuple[Path, ...] = (),
) -> str:
    """Resolve both generated-root and helper-local includes in memory."""
    def replace(match: re.Match[str]) -> str:
        path = _include_path(
            match.group(1),
            asset_root=asset_root,
            semantic_include_root=semantic_include_root,
        ).resolve()
        if path in stack:
            raise RuntimeError(f"cyclic family include: {path.name}")
        return expand_family_includes(
            path.read_text(encoding="utf-8"),
            asset_root=asset_root,
            semantic_include_root=semantic_include_root,
            stack=(*stack, path),
        ).rstrip()

    return INCLUDE.sub(replace, source)


def render_family_snippet(source: str) -> str:
    """Translate recipe-root includes to paths relative to split snippets."""
    return source.replace('#include "include/', '#include "../')


def _asset_closure(asset_root: Path) -> set[str]:
    pending = {
        filename
        for family in MAIN_PART_VERTEX_FAMILIES
        for filename in family.assets
    }
    pending.update(
        filename
        for family in MAIN_PART_VERTEX_FAMILIES
        for _cbuffer, filename in family.cbuffers
        if (asset_root / filename).exists()
    )
    pending.add("main_part_gbuffer.hlsl")
    pending.add("main_part_directional_glass_surface.hlsl")
    pending.add("main_part_tinted_dissolve_glass_surface.hlsl")
    pending.add("main_part_directional_map.hlsl")
    pending.add("main_part_visualization_depth.hlsl")
    pending.add("main_part_glass_behind_light_cap.hlsl")
    pending.add("main_part_glass_surface_medium_dissolve.hlsl")
    pending.add("main_part_glass_surface_low_dissolve.hlsl")
    pending.add("main_part_glass_surface_low.hlsl")
    pending.add("main_part_glass_surface_medium.hlsl")
    pending.add("main_part_glass_surface_low_single.hlsl")
    pending.add("main_part_glass_surface_low_single_dissolve.hlsl")
    pending.add("main_part_glass_surface_medium_off.hlsl")
    pending.add("main_part_glass_surface_medium_off_dissolve.hlsl")
    pending.add("main_part_glass_surface_medium_single.hlsl")
    pending.add("main_part_glass_surface_medium_single_dissolve.hlsl")
    pending.add("main_part_glass_surface_low_no_cutout.hlsl")
    pending.add("main_part_glass_surface_low_off_no_cutout.hlsl")
    pending.add("main_part_glass_surface_low_single_no_cutout.hlsl")
    pending.add("main_part_glass_surface_medium_no_cutout.hlsl")
    pending.add("main_part_glass_surface_medium_off_no_cutout.hlsl")
    pending.add("main_part_glass_surface_medium_single_no_cutout.hlsl")
    pending.add("main_part_glass_surface_medium_light_cap.hlsl")
    pending.add("main_part_glass_surface_medium_light_cap_single.hlsl")
    pending.add("main_part_glass_surface_medium_light_cap_off.hlsl")
    pending.add("main_part_glass_surface_medium_light_cap_unresponsive.hlsl")
    pending.add(
        "main_part_glass_surface_medium_light_cap_single_unresponsive.hlsl"
    )
    pending.add(
        "main_part_glass_surface_medium_light_cap_off_unresponsive.hlsl"
    )
    pending.add("main_part_legacy_glass_surface_basic.hlsl")
    pending.add("main_part_legacy_glass_surface_single.hlsl")
    pending.add("main_part_legacy_glass_surface_plain_multi.hlsl")
    pending.add("main_part_legacy_glass_surface_plain_off.hlsl")
    pending.add("main_part_legacy_glass_surface_plain_single.hlsl")
    pending.add("main_part_tinted_glass_surface_off.hlsl")
    pending.add("main_part_tinted_glass_surface_transmission_multi.hlsl")
    pending.add("main_part_tinted_glass_surface_transmission_off.hlsl")
    pending.add("main_part_tinted_glass_surface_transmission_single.hlsl")
    pending.add("main_part_tinted_glass_surface_dissolve_multi.hlsl")
    pending.add("main_part_tinted_glass_surface_dissolve_off.hlsl")
    pending.add("main_part_tinted_glass_surface_dissolve_single.hlsl")
    pending.add("main_part_standard_glass_surface_unresponsive_multi.hlsl")
    pending.add("main_part_standard_glass_surface_unresponsive_off.hlsl")
    pending.add("main_part_standard_glass_surface_unresponsive_single.hlsl")
    pending.add("main_part_standard_glass_surface_geometric_multi.hlsl")
    pending.add("main_part_standard_glass_surface_geometric_off.hlsl")
    pending.add("main_part_standard_glass_surface_geometric_single.hlsl")
    pending.add("main_part_glass_surface_medium_standard.hlsl")
    pending.add("main_part_glass_surface_medium_single_standard.hlsl")
    pending.add("main_part_glass_surface_medium_off_standard.hlsl")
    pending.add("main_part_glass_surface_medium_standard_geometric.hlsl")
    pending.add("main_part_glass_surface_medium_single_standard_geometric.hlsl")
    pending.add("main_part_glass_surface_medium_off_standard_geometric.hlsl")
    pending.update(
        path.name
        for path in asset_root.glob("main_part_*.hlsl")
        if path.read_text(encoding="utf-8").startswith(
            "// Synthesized semantic family"
        )
    )
    output: set[str] = set()
    while pending:
        filename = pending.pop()
        if filename in output:
            continue
        output.add(filename)
        source = (asset_root / filename).read_text(encoding="utf-8")
        for include in INCLUDE.findall(source):
            if not include.startswith(("include/", "../")):
                pending.add(include)
    return output


def _changed_assets(
    asset_root: Path, semantic_include_root: Path
) -> set[str]:
    """Return recipe assets whose installed copies are absent or different."""
    changed: set[str] = set()
    for filename in _asset_closure(asset_root):
        source_path = asset_root / filename
        installed_path = semantic_include_root / filename
        if (
            not installed_path.exists()
            or installed_path.read_bytes() != source_path.read_bytes()
        ):
            changed.add(filename)
    return changed


def _family_asset_dependencies(
    source: str,
    *,
    asset_root: Path,
    semantic_include_root: Path,
    seen: set[Path] | None = None,
) -> set[str]:
    """Collect the recipe assets reached by a semantic wrapper's includes."""
    if seen is None:
        seen = set()
    dependencies: set[str] = set()
    asset_root = asset_root.resolve()
    for include in INCLUDE.findall(source):
        path = _include_path(
            include,
            asset_root=asset_root,
            semantic_include_root=semantic_include_root,
        ).resolve()
        if path in seen:
            continue
        seen.add(path)
        try:
            filename = path.relative_to(asset_root).as_posix()
        except ValueError:
            filename = None
        if filename is not None:
            dependencies.add(filename)
        dependencies.update(
            _family_asset_dependencies(
                path.read_text(encoding="utf-8"),
                asset_root=asset_root,
                semantic_include_root=semantic_include_root,
                seen=seen,
            )
        )
    return dependencies


def migrate_main_part_families(
    corpus: Path, *, apply: bool = False
) -> dict[str, Any]:
    """Validate and optionally install every newly recognized family member."""
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    semantic_include_root = corpus / "semantic" / "include"
    snippet_root = semantic_include_root / "main_part"
    dxbc_root = corpus / "dxbc"
    asset_root = Path(__file__).parent / "recipes" / "assets"
    changed_assets = _changed_assets(asset_root, semantic_include_root)
    candidates: list[tuple[dict[str, Any], str, str, str, bool]] = []
    dependent_count = 0
    for shader in manifest["shaders"]:
        if shader["source_name"] != "main_part":
            continue
        path = snippet_root / f"{shader['selector']}.hlsl"
        source = path.read_text(encoding="utf-8")
        if "// 3Dmigoto declarations" not in source:
            dependencies = _family_asset_dependencies(
                source,
                asset_root=asset_root,
                semantic_include_root=semantic_include_root,
            )
            if not dependencies.intersection(changed_assets):
                continue
            # Validate only wrappers reached by assets that will actually be
            # replaced. This preserves shared-helper safety without turning a
            # leaf backend addition into a full-corpus recompilation.
            expanded = expand_family_includes(
                source,
                asset_root=asset_root,
                semantic_include_root=semantic_include_root,
            )
            candidates.append(
                (shader, "existing_semantic_dependency", source, expanded, False)
            )
            dependent_count += 1
            continue
        if shader["stage"] == "vertex":
            result = lift_main_part_vertex_family(shader["defines"], source)
        elif shader["stage"] == "pixel":
            result = lift_main_part_picking_family(shader["defines"], source)
            if result is None:
                result = lift_main_part_depth_family(shader["defines"], source)
            if result is None:
                result = lift_main_part_overlay_family(shader["defines"], source)
            if result is None:
                result = lift_main_part_early_gforward_family(
                    shader["defines"], source
                )
            if result is None:
                result = lift_main_part_pixel_family(shader["defines"], source)
            if result is None:
                result = lift_main_part_transparent_family(
                    shader["defines"], source
                )
            if result is None:
                compiled_graph = compile_main_part_phase_graph(
                    shader["defines"], source,
                    selector=shader["selector"],
                )
                if compiled_graph is not None:
                    result = (compiled_graph.family, compiled_graph.source)
            if result is None:
                lifted = lift_main_part_variant(
                    asset_root, shader["selector"], shader["defines"], source
                )
                if lifted != source:
                    result = ("main_part_recipe", lifted)
        else:
            result = None
        if result is None:
            continue
        family_name, lifted = result
        expanded = expand_family_includes(
            lifted,
            asset_root=asset_root,
            semantic_include_root=semantic_include_root,
        )
        candidates.append((shader, family_name, lifted, expanded, True))

    local = threading.local()

    def validate(
        item: tuple[dict[str, Any], str, str, str, bool]
    ) -> tuple[dict[str, Any], str, str, str, bool, dict[str, Any]]:
        shader, family_name, lifted, expanded, install = item
        if not hasattr(local, "compiler"):
            local.compiler = D3DCompiler()
            local.reflector = ShaderReflector()
        try:
            candidate = local.compiler.compile(
                expanded, shader["entry_point"], PROFILES[shader["stage"]]
            )
        except RuntimeError as error:
            raise RuntimeError(
                f"{shader['selector']} family {family_name} failed to compile: "
                f"{error}"
            ) from error
        key = shader["shader_key"]
        if key.startswith("0x"):
            key = key[2:]
        baseline = (dxbc_root / f"{key.lower()}.dxbc").read_bytes()
        comparison, _baseline_assembly, _candidate_assembly = compare_bytecodes(
            baseline, candidate, local.compiler, local.reflector
        )
        if not comparison["abi_compatible"]:
            differences = ", ".join(comparison["abi_differences"])
            raise RuntimeError(
                f"{shader['selector']} family {family_name} changes ABI: "
                f"{differences}"
            )
        return shader, family_name, lifted, expanded, install, comparison

    validated = []
    if candidates:
        with ThreadPoolExecutor(
            max_workers=semantic_worker_count(len(candidates))
        ) as executor:
            futures = [executor.submit(validate, item) for item in candidates]
            for future in as_completed(futures):
                validated.append(future.result())
    validated.sort(key=lambda item: item[0]["selector"])

    if apply:
        for filename in sorted(_asset_closure(asset_root)):
            source = (asset_root / filename).read_text(encoding="utf-8")
            (semantic_include_root / filename).write_text(
                source, encoding="utf-8", newline="\n"
            )
        for shader, _family_name, lifted, expanded, install, comparison in validated:
            path = snippet_root / f"{shader['selector']}.hlsl"
            if install:
                path.write_text(
                    render_family_snippet(lifted), encoding="utf-8", newline="\n"
                )
            shader["semantic_assembly_exact"] = comparison["assembly_exact"]
            shader["semantic_abi_compatible"] = True
            key = shader["shader_key"]
            if key.startswith("0x"):
                key = key[2:]
            shader["semantic_execution"] = main_character_execution(
                shader, (dxbc_root / f"{key.lower()}.dxbc").read_bytes()
            )
        # Fingerprint the installed factored module exactly as corpus
        # verification sees it.  This matters when two helpers include the
        # same guarded dependency: the factored-module expander resolves that
        # guard structure, while the in-memory compiler expander intentionally
        # preserves raw include order for ABI validation.
        semantic_module = corpus / "semantic" / "main_part.hlsl"
        main_part_records = [
            shader
            for shader in manifest["shaders"]
            if shader["source_name"] == "main_part"
        ]
        installed_variants = semantic_module_variants(
            semantic_module.read_text(encoding="utf-8"),
            {
                shader["selector"]: shader["defines"]
                for shader in main_part_records
            },
        )
        validated_selectors = {item[0]["selector"] for item in validated}
        semantic_root = (corpus / "semantic").resolve()
        for shader in main_part_records:
            snippet = snippet_root / f"{shader['selector']}.hlsl"
            if classify_main_part_directional_glass_surface(
                shader["defines"], snippet.read_text(encoding="utf-8")
            ) is not None:
                key = shader["shader_key"]
                if key.startswith("0x"):
                    key = key[2:]
                shader["semantic_execution"] = main_character_execution(
                    shader, (dxbc_root / f"{key.lower()}.dxbc").read_bytes()
                )
            if shader["selector"] not in validated_selectors:
                continue
            expanded_installed = resolve_local_includes(
                installed_variants[shader["selector"]],
                semantic_module,
                semantic_root,
            )
            shader["semantic_hlsl_token_sha256"] = hlsl_token_sha256(
                expanded_installed
            )
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    family_counts = Counter(
        item[1] for item in validated
        if item[1] != "existing_semantic_dependency"
    )
    instruction_deltas = Counter(
        item[5]["baseline_instruction_lines"]
        - item[5]["candidate_instruction_lines"]
        for item in validated
    )
    return {
        "applied": apply,
        "candidate_count": len(candidates) - dependent_count,
        "dependent_count": dependent_count,
        "validated_count": len(validated),
        "family_counts": dict(sorted(family_counts.items())),
        "assembly_exact_count": sum(
            item[5]["assembly_exact"] for item in validated
        ),
        "opcode_sequence_exact_count": sum(
            item[5]["opcode_sequence_exact"] for item in validated
        ),
        "instruction_deltas": {
            str(key): value for key, value in sorted(instruction_deltas.items())
        },
        "selectors": [item[0]["selector"] for item in validated],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = migrate_main_part_families(args.corpus, apply=args.apply)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
