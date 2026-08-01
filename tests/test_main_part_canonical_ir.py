from shader_toolchain.main_part_canonical_ir import (
    align_canonical_bodies,
    canonical_family_key,
    canonicalize_main_part_body,
    canonicalize_main_part_shader,
)
from shader_toolchain.main_part_permutation_graph import (
    describe_main_part_permutation,
)


SOURCE_A = '''
void commonPS(float2 v2 : UV0, out float4 o0 : SV_Target0) {
  float4 partPositionState;
  partPositionState.xy = v2;
  o0 = partPositionState;
}
'''
SOURCE_B = '''
void commonPS(float2 uv : UV0, out float4 color : SV_Target0) {
  float4 materialSampleState;
  materialSampleState.xy = uv;
  color = materialSampleState;
}
'''


def test_canonical_body_ignores_decompiler_and_parameter_names() -> None:
    assert canonicalize_main_part_body(SOURCE_A) == canonicalize_main_part_body(
        SOURCE_B
    )


def test_family_key_removes_quality_and_reflection_axes() -> None:
    base = {"PIXEL_SHADER", "PS_PERM_TRANSPARANT_SURFACE", "PS_GLASS"}
    first = describe_main_part_permutation(
        "SM_SHADER_A", base | {"PS_SHADER_QUALITY_LOW", "PS_REFLECTION_OFF"},
        SOURCE_A,
    )
    second = describe_main_part_permutation(
        "SM_SHADER_B", base | {"PS_SHADER_QUALITY_HIGH", "PS_REFLECTION_MULTI"},
        SOURCE_B,
    )
    first_ir = canonicalize_main_part_shader(first, SOURCE_A)
    second_ir = canonicalize_main_part_shader(second, SOURCE_B)
    assert first_ir.behavior_key == second_ir.behavior_key
    assert canonical_family_key(first_ir) == canonical_family_key(second_ir)


def test_alignment_finds_common_blocks_and_policy_regions() -> None:
    alignment = align_canonical_bodies((
        "a b c d shared one two three four e f g h",
        "x y c d shared one two three four z q g h",
    ), window=4)
    assert alignment.common_token_ratio > 0.3
    assert alignment.common_block_count >= 1
    assert alignment.variant_region_count >= 1
