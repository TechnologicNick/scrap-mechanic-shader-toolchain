from shader_toolchain.reflect import ShaderReflector, abi_differences
from shader_toolchain.sbc import D3DCompiler


def test_reflection_normalizes_shader_abi() -> None:
    source = """
cbuffer Params : register(b2) { float4 color; };
Texture2D<float4> sourceTexture : register(t3);
SamplerState sourceSampler : register(s1);
float4 mainPS(float2 uv : TEXCOORD0) : SV_Target0 {
    return sourceTexture.Sample(sourceSampler, uv) * color;
}
"""
    bytecode = D3DCompiler().compile(source, "mainPS", "ps_5_0")
    abi = ShaderReflector().abi(bytecode)

    assert abi["version"] >> 16 == 0
    assert abi["inputs"][0]["semantic"] == "TEXCOORD"
    assert abi["outputs"][0]["semantic"] == "SV_TARGET"
    assert {(item["type"], item["bind_point"]) for item in abi["resources"]} == {
        (0, 2),
        (2, 3),
        (3, 1),
    }
    assert abi["constant_buffers"][0]["size"] == 16
    assert abi["constant_buffers"][0]["variables"][0]["offset"] == 0
    assert abi["thread_group"] == [0, 0, 0]


def test_abi_differences_names_changed_sections() -> None:
    baseline = {
        "version": 1,
        "inputs": [],
        "outputs": [],
        "resources": [],
        "constant_buffers": [],
        "thread_group": [0, 0, 0],
    }
    candidate = {**baseline, "thread_group": [8, 8, 1]}
    assert abi_differences(baseline, candidate) == ["thread_group"]
