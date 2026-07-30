import json
from pathlib import Path

from shader_toolchain.hlsl import module_variants
from shader_toolchain.recipes.main_part_depth_families import (
    classify_main_part_depth_family,
    lift_main_part_depth_family,
)


def _data():
    manifest = json.loads(Path("output/manifest.json").read_text())
    records = [
        record for record in manifest["shaders"]
        if record["source_name"] == "main_part"
        and "PS_PERM_DEPTH" in record["defines"]
    ]
    variants = module_variants(Path("output/hlsl/main_part.hlsl").read_text())
    return records, variants


def test_every_depth_permutation_has_a_structural_policy():
    records, variants = _data()
    families = [
        classify_main_part_depth_family(
            record["defines"], variants[record["selector"]]
        )
        for record in records
    ]
    assert len(families) == 18
    assert sum(family is not None for family in families) == 17
    excluded = [
        record["selector"] for record, family in zip(records, families)
        if family is None
    ]
    assert excluded == ["SM_SHADER_3CF5FA9A30148E08"]


def test_depth_dissolve_lift_composes_shared_cutout_helpers():
    records, variants = _data()
    record = next(
        record for record in records
        if record["selector"] == "SM_SHADER_F7E31F8485F66749"
    )
    result = lift_main_part_depth_family(
        record["defines"], variants[record["selector"]]
    )
    assert result is not None
    lifted = result[1]
    assert "ApplyMainPartDepthPointAsg(v1)" in lifted
    assert "EvaluateMainPartSurfaceDissolveBand(w1, v2)" in lifted
    assert "ApplyMainPartSurfaceDissolveWindow(dissolve)" in lifted
    assert "partPositionState" not in lifted
