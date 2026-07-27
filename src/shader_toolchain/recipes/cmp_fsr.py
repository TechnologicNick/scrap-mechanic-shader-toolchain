"""Emit FidelityFX Super Resolution 1 EASU and RCAS compute passes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def _ensure_fsr_includes(staging: Path) -> None:
    repository = Path(__file__).parents[3]
    source = repository / "third_party" / "FidelityFX-FSR" / "ffx-fsr"
    include = staging / "semantic" / "include"
    include.mkdir(parents=True, exist_ok=True)
    for filename in ("ffx_a.h", "ffx_fsr1.h"):
        (include / filename).write_text(
            (source / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )


def apply_cmp_fsr_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "cmp_fsr"]
    if len(shaders) != 4 or any(shader["stage"] != "compute" for shader in shaders):
        return None
    ensure_projection_include(staging)
    _ensure_fsr_includes(staging)
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix_lines = []
        for definition in shader["defines"]:
            name, separator, value = definition.partition("=")
            prefix_lines.append(f"#define {name} {value if separator else '1'}\n")
        bodies[shader["selector"]] = "".join(prefix_lines) + asset("cmp_fsr.hlsl")
        easu = "EASU" in shader["defines"]
        executions[shader["selector"]] = {
            "kind": "compute_texture",
            "width": 64,
            "height": 64,
            "dispatch_width": 256,
            "dispatch_height": 4,
            "texture_slots": [0],
            "texture_kinds": ["2d"],
            "samplers": [{"slot": 6, "filter": "linear"}] if easu else [],
            "constant_buffers": [
                {"slot": 0, "profile": "fsr-easu" if easu else "fsr-rcas"},
            ] + ([{"slot": 5, "profile": "projection"}] if easu else []),
            "output": "color",
            "output_components": 4,
            "output_targets": 1,
            "thread_group": [64, 1, 1],
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cmp_fsr",
        bodies=bodies,
        executions=executions,
    )
