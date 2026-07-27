from shader_toolchain.compare import compare_bytecodes
from shader_toolchain.reflect import ShaderReflector
from shader_toolchain.sbc import D3DCompiler


def test_bytecode_comparison_detects_exact_and_abi_compatible_changes() -> None:
    compiler = D3DCompiler()
    reflector = ShaderReflector()
    first = compiler.compile(
        "float4 mainPS() : SV_Target { return 1; }", "mainPS", "ps_5_0"
    )
    second = compiler.compile(
        "float4 mainPS() : SV_Target { return 2; }", "mainPS", "ps_5_0"
    )

    exact, _, _ = compare_bytecodes(first, first, compiler, reflector)
    changed, _, _ = compare_bytecodes(first, second, compiler, reflector)

    assert exact["assembly_exact"]
    assert exact["abi_compatible"]
    assert not changed["assembly_exact"]
    assert changed["abi_compatible"]


def test_bytecode_comparison_detects_signature_change() -> None:
    compiler = D3DCompiler()
    reflector = ShaderReflector()
    first = compiler.compile(
        "float4 mainPS() : SV_Target0 { return 1; }", "mainPS", "ps_5_0"
    )
    second = compiler.compile(
        "float4 mainPS() : SV_Target1 { return 1; }", "mainPS", "ps_5_0"
    )

    changed, _, _ = compare_bytecodes(first, second, compiler, reflector)

    assert not changed["abi_compatible"]
    assert changed["abi_differences"] == ["outputs"]
