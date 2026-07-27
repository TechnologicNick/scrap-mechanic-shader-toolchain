"""Recognize the clustered-light culling grid permutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def _group_size(defines: list[str], axis: str) -> int:
    prefix = f"GROUP_SIZE_{axis}="
    return int(next(
        value.removeprefix(prefix)
        for value in defines
        if value.startswith(prefix)
    ))


def apply_cmp_cluster_culling_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "cmp_cluster_culling"
    ]
    if len(shaders) != 94 or any(
        shader["stage"] != "compute" for shader in shaders
    ):
        return None
    body = asset("cmp_cluster_culling_compute.hlsl")
    bodies = {
        shader["selector"]: "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
            if name in {"GROUP_SIZE_X", "GROUP_SIZE_Y", "GROUP_SIZE_Z", "ORTHO"}
        ) + body
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        group_x = _group_size(shader["defines"], "X")
        group_y = _group_size(shader["defines"], "Y")
        thread_count = group_x * group_y
        executions[shader["selector"]] = {
            "kind": "compute_structured_u32",
            "width": group_x * 3,
            "height": group_y,
            "dispatch_width": group_x * 3,
            "dispatch_height": group_y,
            "thread_group": [group_x, group_y, 1],
            "texture_slots": [],
            "samplers": [],
            "constant_buffers": [
                {"slot": 0, "profile": "cluster"},
                {"slot": 1, "profile": "cluster-culling"},
            ],
            "structured_output_elements": thread_count * 3 * 33,
            "output": "color",
            "output_components": 1,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="cmp_cluster_culling", bodies=bodies, executions=executions,
        shared_source=body,
    )
