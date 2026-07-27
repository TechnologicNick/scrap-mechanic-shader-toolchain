"""Recognize and emit the three-stage SMAA pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def _ensure_smaa_include(staging: Path) -> None:
    destination = staging / "semantic" / "include" / "SMAA.hlsl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    repository = Path(__file__).resolve().parents[3]
    destination.write_text(
        (repository / "third_party" / "SMAA" / "SMAA.hlsl").read_text(encoding="cp1252"),
        encoding="utf-8",
        newline="\n",
    )


def apply_post_smaa_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_smaa"]
    if len(shaders) != 13 or sum(shader["stage"] == "pixel" for shader in shaders) != 7:
        return None
    ensure_projection_include(staging)
    _ensure_smaa_include(staging)
    bodies = {}
    executions = {}
    vertices: dict[tuple[str, str], str] = {}
    for shader in shaders:
        defines = set(shader["defines"])
        stage = next(name for name in (
            "EDGE_DETECTION", "BLENDING_WEIGHTS", "NEIGHBORHOOD_BLENDING"
        ) if name in defines)
        preset = next(
            (name for name in defines if name.startswith("SMAA_PRESET_")),
            "SMAA_PRESET_LOW=1",
        )
        if shader["stage"] == "vertex":
            vertices[(stage, preset)] = shader["selector"]
        prefix = "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
        )
        bodies[shader["selector"]] = prefix + asset(
            "post_smaa_vertex.hlsl" if shader["stage"] == "vertex"
            else "post_smaa_pixel.hlsl"
        )
    for shader in shaders:
        if shader["stage"] != "pixel":
            continue
        defines = set(shader["defines"])
        stage = next(name for name in (
            "EDGE_DETECTION", "BLENDING_WEIGHTS", "NEIGHBORHOOD_BLENDING"
        ) if name in defines)
        preset = next(name for name in defines if name.startswith("SMAA_PRESET_"))
        vertex_selector = vertices.get((stage, preset)) or vertices[(stage, "SMAA_PRESET_LOW=1")]
        if stage == "EDGE_DETECTION":
            slots = [0, 1]
            samplers = [{"slot": 1, "filter": "point"}, {"slot": 6, "filter": "linear"}]
            components = 2
        elif stage == "BLENDING_WEIGHTS":
            slots = [0, 1, 2]
            samplers = [{"slot": 6, "filter": "linear"}]
            components = 4
        else:
            slots = [0, 1]
            samplers = [{"slot": 6, "filter": "linear"}]
            components = 4
        executions[shader["selector"]] = {
            "kind": "post_smaa",
            "vertex_selector": vertex_selector,
            "texture_slots": slots,
            "texture_kinds": ["2d"] * len(slots),
            "samplers": samplers,
            "constant_buffers": [
                {"slot": 0, "profile": "random"},
                {"slot": 5, "profile": "projection"},
            ],
            "output": "color",
            "output_components": components,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_smaa", bodies=bodies, executions=executions,
    )
