from shader_toolchain.hlsl import hlsl_token_sha256, hlsl_tokens


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
