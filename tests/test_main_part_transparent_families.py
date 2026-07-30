from pathlib import Path

from shader_toolchain.recipes.main_part_transparent_families import (
    classify_main_part_transparent_family,
    lift_main_part_transparent_family,
)


ORIGINAL_SOURCE = Path(
    "output/reports/transparent-family-originals/"
    "SM_SHADER_12EF27649EEA9E0F.hlsl"
)
DEFINES = {
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_GLASS", "PS_LIGHT_CAP",
    "PS_PERM_TRANSPARANT_BEHIND", "PS_REFLECTION_OFF", "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
}


def test_classifies_light_cap_behind_pass_by_policies_and_semantics():
    source = ORIGINAL_SOURCE.read_text(encoding="utf-8")
    family = classify_main_part_transparent_family(DEFINES, source)
    assert family is not None
    assert family.name == "transparent_behind_light_cap_reflection_off"
    assert classify_main_part_transparent_family(
        DEFINES | {"PS_SHADER_QUALITY_HIGH"}, source
    ) is None


def test_lift_exposes_typed_transparent_phases():
    result = lift_main_part_transparent_family(
        DEFINES, ORIGINAL_SOURCE.read_text(encoding="utf-8")
    )
    assert result is not None
    _name, lifted = result
    assert "RejectMainPartBehindOpaqueDepth(v5)" in lifted
    assert "EvaluateMainPartBehindLightCapMaterial" in lifted
    assert "EvaluateMainPartBehindDirectionalLighting" in lifted
    assert "ComposeMainPartBehindGlass" in lifted
    assert "WriteMainPartBehindGlass(composite, o0, o1)" in lifted
    assert "partPositionState" not in lifted
    assert "../phases/" not in lifted
