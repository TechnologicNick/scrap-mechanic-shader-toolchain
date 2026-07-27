import pytest

from shader_toolchain.hlsl import (
    HlslFormatError,
    hlsl_token_sha256,
    hlsl_tokens,
    render_shared_module,
    resolve_local_includes,
    semantic_module_variants,
)


def test_token_fingerprint_ignores_comments_and_whitespace() -> None:
    first = "float4 main() { return 1; } // first\n"
    second = "/* second */ float4\nmain ( ) { return 1 ; }\n"
    assert hlsl_token_sha256(first) == hlsl_token_sha256(second)


def test_token_fingerprint_detects_meaningful_edit() -> None:
    assert hlsl_token_sha256("return 1;") != hlsl_token_sha256("return 2;")


def test_tokenizer_preserves_strings_and_operators() -> None:
    assert hlsl_tokens('#include "a.hlsl"\nvalue <<= 2;') == [
        "#",
        "include",
        '"a.hlsl"',
        "value",
        "<<=",
        "2",
        ";",
    ]


def test_shared_semantic_module_expands_recovered_definitions() -> None:
    source = render_shared_module(
        "example", "#if defined(FEATURE)\nfloat value = 1;\n#endif"
    )
    variants = semantic_module_variants(
        source,
        {
            "SM_SHADER_0000000000000001": ["PIXEL_SHADER", "FEATURE=2"],
            "SM_SHADER_0000000000000002": ["VERTEX_SHADER"],
        },
    )

    assert "#define PIXEL_SHADER 1" in variants["SM_SHADER_0000000000000001"]
    assert "#define FEATURE 2" in variants["SM_SHADER_0000000000000001"]
    assert "SM_SELECT" not in source
    assert set(variants) == {
        "SM_SHADER_0000000000000001",
        "SM_SHADER_0000000000000002",
    }


def test_local_include_resolver_recursively_inlines_semantic_headers(tmp_path) -> None:
    root = tmp_path / "semantic"
    include = root / "include"
    include.mkdir(parents=True)
    module = root / "shader.hlsl"
    common = include / "common.hlsl"
    nested = include / "nested.hlsl"
    module.write_text('#include "include/common.hlsl"\nmain();\n')
    common.write_text('#include "nested.hlsl"\ncommon();\n')
    nested.write_text("nested();\n")

    assert resolve_local_includes(module.read_text(), module, root) == (
        "nested();\ncommon();\nmain();\n"
    )


def test_local_include_resolver_rejects_escape(tmp_path) -> None:
    root = tmp_path / "semantic"
    root.mkdir()
    module = root / "shader.hlsl"
    outside = tmp_path / "outside.hlsl"
    outside.write_text("outside();\n")

    with pytest.raises(HlslFormatError, match="escapes semantic root"):
        resolve_local_includes('#include "../outside.hlsl"\n', module, root)


def test_local_include_resolver_rejects_cycles(tmp_path) -> None:
    root = tmp_path / "semantic"
    root.mkdir()
    module = root / "shader.hlsl"
    module.write_text('#include "shader.hlsl"\n')

    with pytest.raises(HlslFormatError, match="cyclic semantic include"):
        resolve_local_includes(module.read_text(), module, root)
