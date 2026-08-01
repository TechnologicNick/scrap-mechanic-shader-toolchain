from shader_toolchain.main_part_graph_codegen import (
    AbiIncludeRule,
    GraphEntrySpecification,
    PolicyAxis,
    render_main_part_graph_entry,
)
from shader_toolchain.recipes.main_part_families import SemanticKey


SOURCE = '''
cbuffer CB_TEST : register(b3) { float4 value; }
// 3Dmigoto declarations
void commonPS(float2 uv : UV0, out float4 target : SV_Target0) {}
'''


def test_generic_graph_codegen_renders_policies_abi_and_semantic_binding() -> None:
    specification = GraphEntrySpecification(
        name="test_graph",
        include_asset="test_graph.hlsl",
        evaluator="EvaluateTestGraph",
        semantics=(SemanticKey("UV", 0), SemanticKey("SV_TARGET", 0)),
        axes=(PolicyAxis("quality", {"low": "TEST_LOW", "high": None}),),
        abi_includes=(AbiIncludeRule("CB_TEST", "test_abi.hlsl"),),
    )
    rendered = render_main_part_graph_entry(
        specification, {"quality": "low"}, SOURCE
    )
    assert '#include "include/test_abi.hlsl"' in rendered
    assert '#include "include/test_graph.hlsl"' in rendered
    assert "#define TEST_LOW" in rendered
    assert "EvaluateTestGraph(\n      uv, target);" in rendered


def test_generic_graph_codegen_rejects_unknown_axis_value() -> None:
    specification = GraphEntrySpecification(
        name="test_graph", include_asset="test.hlsl", evaluator="Evaluate",
        semantics=(SemanticKey("UV", 0),),
        axes=(PolicyAxis("quality", {"low": None}),),
        abi_includes=(),
    )
    try:
        render_main_part_graph_entry(
            specification, {"quality": "ultra"}, SOURCE
        )
    except RuntimeError as error:
        assert "quality=ultra" in str(error)
    else:
        raise AssertionError("unsupported policy must be rejected")

