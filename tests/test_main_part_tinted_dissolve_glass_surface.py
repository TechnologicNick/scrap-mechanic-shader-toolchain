from pathlib import Path

from shader_toolchain.main_part_phase_compiler import (
    compile_main_part_phase_graph,
)
from shader_toolchain.recipes.main_part_tinted_dissolve_glass_surface import (
    TINTED_DISSOLVE_GLASS_SURFACES,
    classify_main_part_tinted_dissolve_glass_surface,
    lift_main_part_tinted_dissolve_glass_surface,
)


SELECTORS = (
    "SM_SHADER_199877BE6440B88A", "SM_SHADER_39690D1D0A1AD2D9",
    "SM_SHADER_7DB0C1A6D7A3ED12", "SM_SHADER_810FB6508049C193",
    "SM_SHADER_8DD506E70407F033", "SM_SHADER_A141F0E307CCB3AA",
    "SM_SHADER_A4268DEA40475CAA", "SM_SHADER_ABA777F8072AD45F",
    "SM_SHADER_F27C9A0E81164B61",
)

SOURCE = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_REFLECTIONS : register(b11) { float4 reflections; }
cbuffer CB_GLASS { float4 glass; }
cbuffer CB_DISSOLVE { float4 dissolve; }
cbuffer Cluster : register(b6) { float4 cluster; }
cbuffer LightProps : register(b8) { float4 lights; }
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float2 w2 : UV1, float3 v3 : NORMAL0,
  float3 v4 : TANGENT0, float3 v5 : BITANGENT0,
  float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, nointerpolation float v9 : CUTOFF0,
  uint v10 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''


def _source(selector: str) -> str:
    return Path(
        f"output/semantic/include/main_part/{selector}.hlsl"
    ).read_text(encoding="utf-8")


def test_complete_tinted_dissolve_matrix_is_classified() -> None:
    manifest = __import__("json").loads(
        Path("output/manifest.json").read_text(encoding="utf-8")
    )
    records = {
        shader["selector"]: shader for shader in manifest["shaders"]
        if shader["selector"] in SELECTORS
    }
    classified = set()
    for selector in SELECTORS:
        family = classify_main_part_tinted_dissolve_glass_surface(
            records[selector]["defines"], _source(selector)
        )
        assert family is not None
        classified.add((family.quality, family.reflection))
    assert classified == {
        (quality, reflection)
        for quality in ("default", "medium", "high")
        for reflection in ("multi", "off", "single")
    }


def test_tinted_dissolve_wrappers_are_generated_and_typed() -> None:
    family = next(
        value for value in TINTED_DISSOLVE_GLASS_SURFACES
        if value.quality == "default" and value.reflection == "multi"
    )
    result = lift_main_part_tinted_dissolve_glass_surface(
        family.defines, SOURCE
    )
    assert result is not None
    _name, lifted = result
    assert "EvaluateMainPartTintedDissolveGlassSurfaceGraph" in lifted
    assert "main_part_tinted_dissolve_glass_surface.hlsl" in lifted
    assert "partPositionState" not in lifted
    assert "../phases/" not in lifted


def test_tinted_dissolve_family_uses_validated_graph_compiler() -> None:
    family = next(
        value for value in TINTED_DISSOLVE_GLASS_SURFACES
        if value.quality == "default" and value.reflection == "multi"
    )
    compiled = compile_main_part_phase_graph(
        family.defines, SOURCE, selector="SM_SHADER_F27C9A0E81164B61"
    )
    assert compiled is not None
    assert compiled.template == "tinted_dissolve_glass_surface"


def test_tinted_dissolve_asset_is_phase_structured() -> None:
    asset = Path(
        "src/shader_toolchain/recipes/assets/"
        "main_part_tinted_dissolve_glass_surface.hlsl"
    ).read_text(encoding="utf-8")
    for helper in (
        "EvaluateMainPartTintedDissolveLighting",
        "ComposeMainPartTintedDissolveGraph",
        "EvaluateMainPartTintedDissolveGlassSurfaceGraph",
    ):
        assert helper in asset
    assert "partPositionState" not in asset
