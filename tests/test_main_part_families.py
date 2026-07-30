import pytest

from shader_toolchain.recipes.main_part_families import (
    SemanticKey,
    classify_main_part_vertex_family,
    lift_main_part_vertex_family,
    parse_entry_signature,
    vertex_family_shape,
)


MORPH_SOURCE = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 position : POSITION0,
  float4 atlasUv : TEXCOORD0,
  float2 detailUv : TEXCOORD1,
  float3 normal : NORMAL0,
  float4 tangent : TANGENT0,
  float3 posePosition : POSITION1,
  float3 poseNormal : NORMAL1,
  float4 transform0 : LTW0,
  float4 transform1 : LTW1,
  float4 transform2 : LTW2,
  uint4 instance : INSTANCE_DATA0,
  out float4 clip : SV_Position0,
  out float3 view : VIEW_POSITION0,
  out float2 uv : UV0,
  out float3 normalOut : NORMAL0,
  out float4 color : VERTEXCOLOR0) {}
'''


def test_signature_parser_preserves_semantic_bindings() -> None:
    signature, parameters = parse_entry_signature(MORPH_SOURCE)
    assert signature.startswith("void mainVS(")
    assert parameters[0].semantic == SemanticKey("POSITION", 0)
    assert parameters[-1].semantic == SemanticKey("VERTEXCOLOR", 0)
    assert parameters[-1].output


def test_signature_parser_accepts_interpolation_qualifiers() -> None:
    source = '''void mainVS(
  float3 position : POSITION0,
  out linear noperspective centroid float3 screen : SCREEN_UV0) {}
'''
    _signature, parameters = parse_entry_signature(source)
    assert parameters[1].output
    assert parameters[1].semantic == SemanticKey("SCREEN_UV", 0)


def test_family_lift_uses_semantics_instead_of_register_names() -> None:
    defines = {
        "VERTEX_SHADER",
        "VS_FULL_TRANSFORM",
        "VS_INPUT_TANGENTS",
        "VS_INPUT_UV1",
        "VS_POSE_0_ANIM",
        "TRANSFER_COLOR",
        "TRANSFER_NORMAL",
        "TRANSFER_UV0",
        "TRANSFER_VIEW_POSITION",
    }
    family = classify_main_part_vertex_family(defines, MORPH_SOURCE)
    assert family is not None
    assert family.name == "explicit_ltw_pose1_surface"
    result = lift_main_part_vertex_family(defines, MORPH_SOURCE)
    assert result is not None
    name, lifted = result
    assert name == family.name
    assert "position, atlasUv.xy, detailUv, normal, tangent" in lifted
    assert "clip = vertex.clipPosition;" in lifted
    assert "view = vertex.viewPosition;" in lifted
    assert "uv = vertex.uv0;" in lifted
    assert "normalOut = vertex.normalView;" in lifted
    assert "color = vertex.color;" in lifted
    assert "partPositionState" not in lifted


def test_family_accepts_supported_transfer_subsets() -> None:
    base = {
        "VERTEX_SHADER",
        "VS_FULL_TRANSFORM",
        "VS_INPUT_TANGENTS",
        "VS_INPUT_UV1",
        "VS_POSE_0_ANIM",
    }
    first = classify_main_part_vertex_family(base | {"TRANSFER_UV0"}, MORPH_SOURCE)
    second = classify_main_part_vertex_family(
        base | {"TRANSFER_UV0", "TRANSFER_COLOR", "TRANSFER_NORMAL"},
        MORPH_SOURCE,
    )
    assert first is not None
    assert second is not None
    assert first.name == second.name


def test_family_rejects_unknown_structural_feature() -> None:
    defines = {
        "VERTEX_SHADER",
        "VS_FULL_TRANSFORM",
        "VS_INPUT_TANGENTS",
        "VS_INPUT_UV1",
        "VS_POSE_0_ANIM",
        "VS_SKEL_ANIM",
    }
    assert classify_main_part_vertex_family(defines, MORPH_SOURCE) is None


def test_family_shape_ignores_transfer_channels() -> None:
    first = vertex_family_shape(
        ["VERTEX_SHADER", "VS_FULL_TRANSFORM", "TRANSFER_UV0"]
    )
    second = vertex_family_shape(
        ["TRANSFER_COLOR", "VERTEX_SHADER", "VS_FULL_TRANSFORM"]
    )
    assert first == second == ("VERTEX_SHADER", "VS_FULL_TRANSFORM")


def test_signature_parser_rejects_unmodelled_parameter() -> None:
    with pytest.raises(RuntimeError, match="unsupported HLSL parameter"):
        parse_entry_signature("void mainVS(Texture2D value : TEXCOORD0) {}")
