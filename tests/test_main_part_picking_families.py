import json
from pathlib import Path

from shader_toolchain.hlsl import module_variants
from shader_toolchain.recipes.main_part_picking_families import (
    classify_main_part_picking_family,
    lift_main_part_picking_family,
)


def _records():
    manifest = json.loads(Path("output/manifest.json").read_text())
    return [
        record for record in manifest["shaders"]
        if record["source_name"] == "main_part"
        and "PS_PERM_PICKING" in record["defines"]
    ]


def _raw_variants():
    source = Path("output/hlsl/main_part.hlsl").read_text()
    return module_variants(source)


def test_every_picking_permutation_has_a_structural_policy():
    variants = _raw_variants()
    families = {
        record["selector"]: classify_main_part_picking_family(
            record["defines"], variants[record["selector"]]
        )
        for record in _records()
    }
    assert len(families) == 14
    assert all(family is not None for family in families.values())
    assert {family.cutout for family in families.values()} == {
        "none", "point", "linear", "flow"
    }


def test_picking_lift_is_a_thin_typed_wrapper():
    variants = _raw_variants()
    record = next(
        record for record in _records()
        if record["selector"] == "SM_SHADER_E45698CDFCF10EBB"
    )
    result = lift_main_part_picking_family(
        record["defines"], variants[record["selector"]]
    )
    assert result is not None
    assert result[0] == "picking_flow"
    lifted = result[1]
    assert "ApplyMainPartPickingFlowCutout(v1)" in lifted
    assert "WriteMainPartPickingColor(v2, o0)" in lifted
    function_body = lifted[lifted.index("void commonPS("):]
    assert '#include "include/' not in function_body
    assert "partPositionState" not in function_body
