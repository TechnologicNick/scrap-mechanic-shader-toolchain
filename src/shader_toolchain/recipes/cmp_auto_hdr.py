"""Recognize and emit automatic HDR feedback/update variants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_recovered_cbuffer_include


def apply_cmp_auto_hdr_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "cmp_auto_hdr"
    ]
    if len(shaders) != 8 or any(shader["stage"] != "compute" for shader in shaders):
        return None
    ensure_recovered_cbuffer_include(
        staging, "cmp_auto_hdr", "cb_hdr_settings", "auto_hdr_abi.hlsl"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix = "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
        )
        bodies[shader["selector"]] = prefix + asset("cmp_auto_hdr.hlsl")
        executions[shader["selector"]] = {
            "kind": "compute_structured",
            "width": 1,
            "height": 1,
            "dispatch_width": 1,
            "dispatch_height": 1,
            "texture_slots": [],
            "texture_kinds": [],
            "constant_buffers": [
                {"slot": 0, "profile": "auto-hdr"},
                {"slot": 9, "profile": "hdr"},
            ],
            "structured_outputs": [
                {
                    "slot": 0, "elements": 8, "stride": 4,
                    "profile": "hdr-feedback",
                },
                {
                    "slot": 1, "elements": 1, "stride": 112,
                    "profile": "hdr-setting",
                },
            ],
            "output": "color",
            "output_components": 1,
            "output_targets": 1,
            "thread_group": [1, 1, 1],
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="cmp_auto_hdr", bodies=bodies, executions=executions,
    )
