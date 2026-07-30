import json
from pathlib import Path

from shader_toolchain.hlsl import module_variants
from shader_toolchain.recipes.main_part_early_gforward_families import (
    lift_main_part_early_gforward_family,
)


def test_both_early_gforward_permutations_use_typed_outputs():
    manifest = json.loads(Path("output/manifest.json").read_text())
    records = [
        record for record in manifest["shaders"]
        if record["source_name"] == "main_part"
        and "PS_PERM_EARLY_GFORWARD" in record["defines"]
    ]
    variants = module_variants(Path("output/hlsl/main_part.hlsl").read_text())
    results = [
        lift_main_part_early_gforward_family(
            record["defines"], variants[record["selector"]]
        )
        for record in records
    ]
    assert len(results) == 2
    assert all(result is not None for result in results)
    assert {result[0] for result in results} == {
        "early_gforward_reflection_as_diffuse",
        "early_gforward_opaque_glass",
    }
    assert all("MainPartEarlyGForward result" in result[1] for result in results)
