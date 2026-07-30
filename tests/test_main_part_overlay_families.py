import json
from pathlib import Path

from shader_toolchain.hlsl import module_variants
from shader_toolchain.recipes.main_part_overlay_families import (
    lift_main_part_overlay_family,
)


def test_overlay_and_wireframe_permutations_use_typed_policies():
    manifest = json.loads(Path("output/manifest.json").read_text())
    records = [
        record for record in manifest["shaders"]
        if record["source_name"] == "main_part"
        and ({"PS_PERM_OVERLAY", "PS_PERM_WIREFRAME"}
             & set(record["defines"]))
    ]
    variants = module_variants(Path("output/hlsl/main_part.hlsl").read_text())
    lifted = [
        lift_main_part_overlay_family(
            record["defines"], variants[record["selector"]]
        )
        for record in records
    ]
    assert len(lifted) == 4
    assert all(result is not None for result in lifted)
    assert {result[0] for result in lifted} == {
        "wireframe", "connect_overlay", "editor_overlay",
        "editor_overlay_clipped",
    }
    assert all("partPositionState" not in result[1] for result in lifted)
